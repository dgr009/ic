#!/usr/bin/env python3
import os
import json
import time
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from google.auth import default
from google.auth.credentials import Credentials
from google.oauth2 import service_account
from google.cloud.resourcemanager_v3 import ProjectsClient
from google.cloud.resourcemanager_v3.types import SearchProjectsRequest, GetProjectRequest
from google.api_core import exceptions as gcp_exceptions
from google.api_core import retry
from ic.config.manager import ConfigManager

from common.log import log_info, log_error, log_exception

# Import MCP connector with fallback handling
try:
    from mcp.gcp_connector import MCPGCPConnector, create_mcp_connector
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    log_info("MCP connector not available, using direct API access only")

# Import configuration validator
try:
    from common.gcp_config_validator import GCPConfigValidator
    CONFIG_VALIDATOR_AVAILABLE = True
except ImportError:
    CONFIG_VALIDATOR_AVAILABLE = False

# Import monitoring utilities
try:
    from common.gcp_monitoring import (
        monitor_gcp_operation, update_gcp_service_health, 
        update_mcp_connection_status, log_gcp_structured_event
    )
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

# Initialize config manager
_config_manager = ConfigManager()

def _get_env_var(key: str, default: str = '') -> str:
    """환경변수를 동적으로 가져옵니다."""
    config = _config_manager.get_config()
    gcp_config = config.get('gcp', {})
    return gcp_config.get(key, os.getenv(key, default))

def _get_env_list(key: str, default: str = '') -> List[str]:
    """환경변수를 리스트로 가져옵니다."""
    config = _config_manager.get_config()
    gcp_config = config.get('gcp', {})
    value = gcp_config.get(key, os.getenv(key, default))
    return [item.strip() for item in value.split(',') if item.strip()] if value else []

def _get_env_int(key: str, default: int) -> int:
    """환경변수를 정수로 가져옵니다."""
    try:
        config = _config_manager.get_config()
        gcp_config = config.get('gcp', {})
        value = gcp_config.get(key, os.getenv(key, str(default)))
        return int(value)
    except (ValueError, TypeError):
        return default


@dataclass
class GCPProject:
    """GCP 프로젝트 정보를 담는 데이터 클래스"""
    project_id: str
    project_name: str
    project_number: str
    lifecycle_state: str
    labels: Dict[str, str]


class GCPAuthManager:
    """GCP 인증을 관리하는 클래스 (MCP 우선, 직접 API 폴백)"""
    
    def __init__(self, prefer_mcp: bool = True, validate_config: bool = True):
        self._credentials = None
        self._project_id = None
        self.prefer_mcp = prefer_mcp and MCP_AVAILABLE
        self.mcp_connector = None
        
        # Validate configuration if requested
        if validate_config and CONFIG_VALIDATOR_AVAILABLE:
            self._validate_configuration()
        
        if self.prefer_mcp:
            try:
                self.mcp_connector = create_mcp_connector()
                log_info("MCP connector initialized for GCP authentication")
            except Exception as e:
                log_error(f"Failed to initialize MCP connector: {e}")
                self.prefer_mcp = False
    
    def _validate_configuration(self):
        """GCP 설정을 검증합니다."""
        try:
            validator = GCPConfigValidator()
            is_valid, errors, warnings = validator.validate_config()
            
            if errors:
                log_error("GCP configuration errors found:")
                for error in errors:
                    log_error(f"  - {error}")
            
            if warnings:
                log_info("GCP configuration warnings:")
                for warning in warnings:
                    log_info(f"  - {warning}")
            
            if not is_valid:
                log_error("GCP configuration validation failed. Please check your environment variables.")
                
        except Exception as e:
            log_error(f"Configuration validation failed: {e}")
    
    def get_credentials(self) -> Optional[Credentials]:
        """GCP 인증 정보를 가져옵니다."""
        if self._credentials:
            return self._credentials
        
        try:
            # Method 1: Service Account Key (JSON string)
            gcp_service_account_key = _get_env_var('GCP_SERVICE_ACCOUNT_KEY')
            if gcp_service_account_key:
                log_info("Service Account Key (JSON) 인증 사용")
                service_account_info = json.loads(gcp_service_account_key)
                self._credentials = service_account.Credentials.from_service_account_info(
                    service_account_info
                )
                self._project_id = service_account_info.get('project_id')
                return self._credentials
            
            # Method 2: Service Account Key Path
            gcp_service_account_key_path = _get_env_var('GCP_SERVICE_ACCOUNT_KEY_PATH')
            if gcp_service_account_key_path and os.path.exists(gcp_service_account_key_path):
                log_info("Service Account Key Path 인증 사용")
                self._credentials = service_account.Credentials.from_service_account_file(
                    gcp_service_account_key_path
                )
                with open(gcp_service_account_key_path, 'r') as f:
                    service_account_info = json.load(f)
                    self._project_id = service_account_info.get('project_id')
                return self._credentials
            
            # Method 3: Application Default Credentials
            log_info("Application Default Credentials 인증 사용")
            self._credentials, self._project_id = default()
            return self._credentials
            
        except Exception as e:
            log_error(f"GCP 인증 실패: {e}")
            return None
    
    def get_default_project_id(self) -> Optional[str]:
        """기본 프로젝트 ID를 가져옵니다."""
        gcp_default_project = _get_env_var('GCP_DEFAULT_PROJECT')
        if gcp_default_project:
            return gcp_default_project
        
        if not self._credentials:
            self.get_credentials()
        
        return self._project_id
    
    def validate_credentials(self) -> bool:
        """인증 정보가 유효한지 확인합니다."""
        # Try MCP first if available
        if self.use_mcp_if_available():
            try:
                is_valid = self.mcp_connector.validate_connection()
                if MONITORING_AVAILABLE:
                    update_mcp_connection_status(is_valid)
                    log_gcp_structured_event('credential_validation', {
                        'method': 'mcp',
                        'success': is_valid
                    })
                return is_valid
            except Exception as e:
                log_error(f"MCP credential validation failed: {e}")
                if MONITORING_AVAILABLE:
                    update_mcp_connection_status(False)
                # Fall back to direct validation
        
        # Direct API validation
        try:
            credentials = self.get_credentials()
            if not credentials:
                if MONITORING_AVAILABLE:
                    log_gcp_structured_event('credential_validation', {
                        'method': 'direct',
                        'success': False,
                        'error': 'No credentials available'
                    })
                return False
            
            # Resource Manager API를 사용하여 인증 테스트
            if MONITORING_AVAILABLE:
                with monitor_gcp_operation('resourcemanager', 'search_projects', 
                                         self.get_default_project_id() or 'unknown', via_mcp=False):
                    client = ProjectsClient(credentials=credentials)
                    # 간단한 API 호출로 인증 확인
                    request = SearchProjectsRequest(
                        query="",
                        page_size=1
                    )
                    client.search_projects(request=request)
            else:
                client = ProjectsClient(credentials=credentials)
                request = SearchProjectsRequest(
                    query="",
                    page_size=1
                )
                client.search_projects(request=request)
            
            if MONITORING_AVAILABLE:
                log_gcp_structured_event('credential_validation', {
                    'method': 'direct',
                    'success': True
                })
            return True
            
        except Exception as e:
            log_error(f"GCP 인증 검증 실패: {e}")
            if MONITORING_AVAILABLE:
                log_gcp_structured_event('credential_validation', {
                    'method': 'direct',
                    'success': False,
                    'error': str(e)
                })
            return False
    
    def use_mcp_if_available(self) -> bool:
        """MCP를 사용할 수 있는지 확인합니다."""
        return (self.prefer_mcp and 
                self.mcp_connector and 
                self.mcp_connector.is_available())


class GCPProjectManager:
    """GCP 프로젝트 관리 클래스 (MCP 우선, 직접 API 폴백)"""
    
    def __init__(self, auth_manager: GCPAuthManager):
        self.auth_manager = auth_manager
        self._projects_cache = None
    
    def discover_projects(self) -> List[GCPProject]:
        """사용 가능한 모든 GCP 프로젝트를 발견합니다."""
        if self._projects_cache:
            return self._projects_cache
        
        # Try MCP first if available
        if self.auth_manager.use_mcp_if_available():
            try:
                if MONITORING_AVAILABLE:
                    with monitor_gcp_operation('resourcemanager', 'get_projects', 'all', via_mcp=True):
                        response = self.auth_manager.mcp_connector.get_projects()
                else:
                    response = self.auth_manager.mcp_connector.get_projects()
                
                if response.success:
                    projects = []
                    for project_data in response.data.get('projects', []):
                        projects.append(GCPProject(
                            project_id=project_data['project_id'],
                            project_name=project_data.get('name', project_data['project_id']),
                            project_number=project_data.get('project_number', ''),
                            lifecycle_state=project_data.get('lifecycle_state', 'ACTIVE'),
                            labels=project_data.get('labels', {})
                        ))
                    
                    log_info(f"MCP를 통해 발견된 GCP 프로젝트: {len(projects)}개")
                    if MONITORING_AVAILABLE:
                        log_gcp_structured_event('project_discovery', {
                            'method': 'mcp',
                            'project_count': len(projects),
                            'success': True
                        })
                    self._projects_cache = projects
                    return projects
            except Exception as e:
                log_error(f"MCP project discovery failed: {e}")
                if MONITORING_AVAILABLE:
                    log_gcp_structured_event('project_discovery', {
                        'method': 'mcp',
                        'success': False,
                        'error': str(e)
                    })
                # Fall back to direct API
        
        # Direct API fallback
        try:
            credentials = self.auth_manager.get_credentials()
            if not credentials:
                return []
            
            client = ProjectsClient(credentials=credentials)
            projects = []
            
            # 활성 프로젝트만 조회
            request = SearchProjectsRequest(
                query="lifecycleState:ACTIVE"
            )
            
            for project in client.search_projects(request=request):
                projects.append(GCPProject(
                    project_id=project.project_id,
                    project_name=project.display_name,
                    project_number=project.name.split('/')[-1],  # projects/123456789 -> 123456789
                    lifecycle_state=project.state.name,
                    labels=dict(project.labels) if project.labels else {}
                ))
            
            log_info(f"직접 API를 통해 발견된 GCP 프로젝트: {len(projects)}개")
            self._projects_cache = projects
            return projects
            
        except Exception as e:
            log_error(f"GCP 프로젝트 발견 실패: {e}")
            return []
    
    def get_projects(self) -> List[str]:
        """환경변수 또는 발견된 프로젝트 ID 목록을 가져옵니다."""
        # 환경변수에 지정된 프로젝트가 있으면 사용
        gcp_projects = _get_env_list('GCP_PROJECTS')
        if gcp_projects:
            return gcp_projects
        
        # 없으면 모든 접근 가능한 프로젝트 사용
        discovered_projects = self.discover_projects()
        return [p.project_id for p in discovered_projects]
    
    def validate_project_access(self, project_id: str) -> bool:
        """프로젝트 접근 권한을 확인합니다."""
        try:
            credentials = self.auth_manager.get_credentials()
            if not credentials:
                return False
            
            client = ProjectsClient(credentials=credentials)
            request = GetProjectRequest(
                name=f"projects/{project_id}"
            )
            
            project = client.get_project(request=request)
            return project.state.name == "ACTIVE"
            
        except gcp_exceptions.NotFound:
            log_error(f"프로젝트를 찾을 수 없음: {project_id}")
            return False
        except gcp_exceptions.PermissionDenied:
            log_error(f"프로젝트 접근 권한 없음: {project_id}")
            return False
        except Exception as e:
            log_error(f"프로젝트 접근 검증 실패: {project_id}, Error={e}")
            return False
    
    def get_project_info(self, project_id: str) -> Optional[Dict[str, Any]]:
        """프로젝트 상세 정보를 가져옵니다."""
        try:
            credentials = self.auth_manager.get_credentials()
            if not credentials:
                return None
            
            client = ProjectsClient(credentials=credentials)
            request = GetProjectRequest(
                name=f"projects/{project_id}"
            )
            
            project = client.get_project(request=request)
            return {
                'project_id': project.project_id,
                'project_name': project.display_name,
                'project_number': project.name.split('/')[-1],
                'lifecycle_state': project.state.name,
                'labels': dict(project.labels) if project.labels else {},
                'create_time': project.create_time,
                'update_time': project.update_time
            }
            
        except Exception as e:
            log_error(f"프로젝트 정보 조회 실패: {project_id}, Error={e}")
            return None


class GCPResourceCollector:
    """GCP 리소스 수집 및 처리 클래스 (MCP 우선, 직접 API 폴백)"""
    
    def __init__(self, auth_manager: GCPAuthManager):
        self.auth_manager = auth_manager
    
    def collect_via_mcp(self, service: str, operation: str, params: Dict) -> List[Any]:
        """MCP 서버를 통해 리소스를 수집합니다."""
        if not self.auth_manager.use_mcp_if_available():
            return []
        
        try:
            response = self.auth_manager.mcp_connector.execute_gcp_query(service, operation, params)
            if response.success:
                return response.data.get('resources', [])
            else:
                log_error(f"MCP query failed: {response.error}")
                return []
        except Exception as e:
            log_error(f"MCP resource collection failed: {e}")
            return []
    
    def collect_direct(self, projects: List[str], collect_func: Callable) -> List[Any]:
        """직접 API를 통해 리소스를 수집합니다."""
        return self.parallel_collect(projects, collect_func)
    
    def parallel_collect(self, projects: List[str], collect_func: Callable, *args, **kwargs) -> List[Any]:
        """여러 프로젝트에서 병렬로 리소스를 수집합니다."""
        results = []
        
        with ThreadPoolExecutor(max_workers=_get_env_int('GCP_MAX_WORKERS', 10)) as executor:
            futures = []
            
            for project_id in projects:
                future = executor.submit(
                    self._safe_collect, collect_func, project_id, *args, **kwargs
                )
                futures.append((future, project_id))
            
            for future, project_id in futures:
                try:
                    result = future.result(timeout=_get_env_int('GCP_REQUEST_TIMEOUT', 30))
                    if result:
                        if isinstance(result, list):
                            results.extend(result)
                        else:
                            results.append(result)
                except Exception as e:
                    log_error(f"프로젝트 {project_id}에서 리소스 수집 실패: {e}")
        
        return results
    
    def _safe_collect(self, collect_func: Callable, project_id: str, *args, **kwargs) -> Any:
        """안전한 리소스 수집 (에러 핸들링 포함)"""
        try:
            return self.handle_api_errors(lambda: collect_func(project_id, *args, **kwargs))
        except Exception as e:
            log_error(f"리소스 수집 중 오류 발생: Project={project_id}, Error={e}")
            return None
    
    def handle_api_errors(self, func: Callable) -> Any:
        """GCP API 에러를 처리하고 재시도 로직을 적용합니다."""
        @retry.Retry(
            predicate=retry.if_exception_type(
                gcp_exceptions.TooManyRequests,
                gcp_exceptions.InternalServerError,
                gcp_exceptions.ServiceUnavailable,
                gcp_exceptions.DeadlineExceeded
            ),
            initial=1.0,
            maximum=60.0,
            multiplier=2.0,
            deadline=300.0
        )
        def _retry_func():
            return func()
        
        try:
            return _retry_func()
        except gcp_exceptions.PermissionDenied as e:
            log_error(f"권한 거부: {e}")
            raise
        except gcp_exceptions.NotFound as e:
            log_error(f"리소스를 찾을 수 없음: {e}")
            return None
        except gcp_exceptions.Forbidden as e:
            log_error(f"API가 비활성화되었거나 접근 금지: {e}")
            return None
        except gcp_exceptions.TooManyRequests as e:
            log_error(f"API 요청 한도 초과: {e}")
            raise
        except Exception as e:
            log_error(f"예상치 못한 API 오류: {e}")
            raise
    
    def apply_filters(self, resources: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """리소스에 필터를 적용합니다."""
        if not filters:
            return resources
        
        filtered_resources = []
        
        for resource in resources:
            match = True
            
            # 이름 필터 (부분 일치)
            if 'name' in filters and filters['name']:
                resource_name = resource.get('name', '').lower()
                filter_name = filters['name'].lower()
                if filter_name not in resource_name:
                    match = False
            
            # 프로젝트 필터
            if 'project' in filters and filters['project']:
                if resource.get('project_id') != filters['project']:
                    match = False
            
            # 지역 필터
            if 'region' in filters and filters['region']:
                resource_region = resource.get('region', resource.get('location', ''))
                if filters['region'] not in resource_region:
                    match = False
            
            # 존 필터
            if 'zone' in filters and filters['zone']:
                resource_zone = resource.get('zone', '')
                if filters['zone'] not in resource_zone:
                    match = False
            
            # 라벨 필터
            if 'labels' in filters and filters['labels']:
                resource_labels = resource.get('labels', {})
                for key, value in filters['labels'].items():
                    if key not in resource_labels or resource_labels[key] != value:
                        match = False
                        break
            
            # 빌링 계정 필터 (부분 일치)
            if 'billing_account' in filters and filters['billing_account']:
                billing_account_name = resource.get('billing_account_display_name', '').lower()
                filter_account = filters['billing_account'].lower()
                if filter_account not in billing_account_name:
                    match = False
            
            if match:
                filtered_resources.append(resource)
        
        return filtered_resources


def get_gcp_regions() -> List[str]:
    """GCP 지역 목록을 가져옵니다."""
    return _get_env_list('GCP_REGIONS', 'us-central1,us-east1,europe-west1')


def get_gcp_zones() -> List[str]:
    """GCP 존 목록을 가져옵니다."""
    return _get_env_list('GCP_ZONES', 'us-central1-a,us-central1-b,europe-west1-a')


def create_gcp_client(client_class, credentials: Credentials = None, **kwargs):
    """GCP 클라이언트를 생성합니다."""
    try:
        if not credentials:
            auth_manager = GCPAuthManager()
            credentials = auth_manager.get_credentials()
        
        if not credentials:
            log_error(f"GCP 클라이언트 생성 실패: 인증 정보 없음")
            return None
        
        return client_class(credentials=credentials, **kwargs)
        
    except Exception as e:
        log_error(f"GCP 클라이언트 생성 실패: {client_class.__name__}, Error={e}")
        return None


def format_gcp_output(data: Any, output_format: str = 'table') -> str:
    """GCP 데이터를 지정된 형식으로 포맷합니다."""
    if output_format == 'json':
        return json.dumps(data, indent=2, default=str, ensure_ascii=False)
    elif output_format == 'yaml':
        import yaml
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        # table 형식은 각 서비스에서 개별 구현
        return str(data)


def get_gcp_resource_labels(resource) -> Dict[str, str]:
    """GCP 리소스에서 라벨을 추출합니다."""
    if hasattr(resource, 'labels') and resource.labels:
        return dict(resource.labels)
    return {}


def check_gcp_label_compliance(labels: Dict[str, str], required_labels: List[str], 
                              optional_labels: List[str] = None) -> Dict[str, Any]:
    """GCP 리소스 라벨 규정 준수를 확인합니다."""
    result = {
        'compliant': True,
        'missing_required': [],
        'missing_optional': [],
        'present_labels': list(labels.keys()),
        'label_count': len(labels)
    }
    
    # 필수 라벨 확인
    for required_label in required_labels:
        if required_label not in labels:
            result['missing_required'].append(required_label)
            result['compliant'] = False
    
    # 선택적 라벨 확인
    if optional_labels:
        for optional_label in optional_labels:
            if optional_label not in labels:
                result['missing_optional'].append(optional_label)
    
    return result


def ensure_directory_exists(directory):
    """지정된 경로에 디렉터리가 없으면 생성합니다."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        log_info(f"Created directory: {directory}")


def save_json(data, file_path):
    """데이터를 JSON 파일로 저장합니다."""
    try:
        ensure_directory_exists(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False, default=str)
        log_info(f"Data saved to JSON: {file_path}")
    except Exception as e:
        log_exception(e)
        log_error(f"Error saving JSON to {file_path}")


def load_json(file_path):
    """JSON 파일을 로드합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log_info(f"Loaded JSON from {file_path}")
        return data
    except FileNotFoundError as e:
        log_error(f"JSON file not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        log_error(f"JSON decoding error in {file_path}: {e}")
        return None


# GCP 서비스별 기본 API 버전
GCP_API_VERSIONS = {
    'compute': 'v1',
    'container': 'v1',
    'storage': 'v1',
    'sqladmin': 'v1',
    'cloudfunctions': 'v1',
    'run': 'v1',
    'cloudbilling': 'v1'
}


def get_api_version(service: str) -> str:
    """GCP 서비스의 API 버전을 가져옵니다."""
    return GCP_API_VERSIONS.get(service, 'v1')