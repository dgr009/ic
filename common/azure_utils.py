#!/usr/bin/env python3
import os
import json
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient
from ic.config.manager import ConfigManager

from common.log import log_info, log_error, log_exception

# Initialize config manager
_config_manager = ConfigManager()

# Azure 기본 설정
def _get_azure_config():
    """Azure 설정을 가져옵니다."""
    config = _config_manager.get_config()
    return config.get('azure', {})

def _get_azure_subscriptions():
    """Azure 구독 목록을 가져옵니다."""
    azure_config = _get_azure_config()
    subscriptions = azure_config.get('subscriptions', os.getenv('AZURE_SUBSCRIPTIONS', ''))
    return subscriptions.split(',') if subscriptions else []

def _get_azure_locations():
    """Azure 위치 목록을 가져옵니다."""
    azure_config = _get_azure_config()
    locations = azure_config.get('locations', os.getenv('AZURE_LOCATIONS', 'East US,West US 2,Korea Central,Southeast Asia'))
    return locations.split(',')

def _get_azure_tenant_id():
    """Azure 테넌트 ID를 가져옵니다."""
    azure_config = _get_azure_config()
    return azure_config.get('tenant_id', os.getenv('AZURE_TENANT_ID'))

def _get_azure_client_id():
    """Azure 클라이언트 ID를 가져옵니다."""
    azure_config = _get_azure_config()
    return azure_config.get('client_id', os.getenv('AZURE_CLIENT_ID'))

def _get_azure_client_secret():
    """Azure 클라이언트 시크릿을 가져옵니다."""
    azure_config = _get_azure_config()
    return azure_config.get('client_secret', os.getenv('AZURE_CLIENT_SECRET'))

# 호환성을 위한 변수들
AZURE_SUBSCRIPTIONS = _get_azure_subscriptions()
AZURE_LOCATIONS = _get_azure_locations()
AZURE_TENANT_ID = _get_azure_tenant_id()
AZURE_CLIENT_ID = _get_azure_client_id()
AZURE_CLIENT_SECRET = _get_azure_client_secret()

def get_azure_credential():
    """Azure 인증 정보를 가져옵니다."""
    try:
        # Service Principal 인증 (우선순위)
        if AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET:
            log_info("Service Principal 인증 사용")
            return ClientSecretCredential(
                tenant_id=AZURE_TENANT_ID,
                client_id=AZURE_CLIENT_ID,
                client_secret=AZURE_CLIENT_SECRET
            )
        
        # Default 인증 (Azure CLI, Managed Identity 등)
        log_info("Default Azure 인증 사용")
        return DefaultAzureCredential()
        
    except Exception as e:
        log_error(f"Azure 인증 실패: {e}")
        return None

def get_azure_subscriptions() -> List[str]:
    """환경변수에서 Azure 구독 ID 목록을 가져옵니다."""
    if AZURE_SUBSCRIPTIONS and AZURE_SUBSCRIPTIONS[0]:
        return AZURE_SUBSCRIPTIONS
    
    # 환경변수가 없으면 사용 가능한 모든 구독 조회
    try:
        credential = get_azure_credential()
        if not credential:
            return []
        
        subscription_client = SubscriptionClient(credential)
        subscriptions = []
        
        for subscription in subscription_client.subscriptions.list():
            if subscription.state == 'Enabled':
                subscriptions.append(subscription.subscription_id)
        
        log_info(f"발견된 Azure 구독: {len(subscriptions)}개")
        return subscriptions
        
    except Exception as e:
        log_error(f"Azure 구독 목록 조회 실패: {e}")
        return []

def get_azure_locations() -> List[str]:
    """Azure 위치 목록을 가져옵니다."""
    return AZURE_LOCATIONS

def create_azure_client(client_class, subscription_id: str):
    """Azure 클라이언트를 생성합니다."""
    try:
        credential = get_azure_credential()
        if not credential:
            return None
        
        return client_class(credential, subscription_id)
        
    except Exception as e:
        log_error(f"Azure 클라이언트 생성 실패: {client_class.__name__}, Error={e}")
        return None

def get_resource_groups(subscription_id: str) -> List[Dict[str, Any]]:
    """구독의 리소스 그룹 목록을 가져옵니다."""
    try:
        resource_client = create_azure_client(ResourceManagementClient, subscription_id)
        if not resource_client:
            return []
        
        resource_groups = []
        for rg in resource_client.resource_groups.list():
            resource_groups.append({
                'name': rg.name,
                'location': rg.location,
                'id': rg.id,
                'tags': rg.tags or {},
                'subscription_id': subscription_id
            })
        
        return resource_groups
        
    except Exception as e:
        log_error(f"리소스 그룹 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def filter_resources_by_tags(resources: List[Dict], tag_filters: Dict[str, str] = None) -> List[Dict]:
    """태그로 리소스를 필터링합니다."""
    if not tag_filters:
        return resources
    
    filtered_resources = []
    for resource in resources:
        resource_tags = resource.get('tags', {})
        
        # 모든 필터 조건을 만족하는지 확인
        match = True
        for key, value in tag_filters.items():
            if key not in resource_tags or resource_tags[key] != value:
                match = False
                break
        
        if match:
            filtered_resources.append(resource)
    
    return filtered_resources

def format_azure_output(data: Any, output_format: str = 'table') -> str:
    """Azure 데이터를 지정된 형식으로 포맷합니다."""
    if output_format == 'json':
        return json.dumps(data, indent=2, default=str, ensure_ascii=False)
    elif output_format == 'yaml':
        import yaml
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        # table 형식은 각 서비스에서 개별 구현
        return str(data)

def get_azure_resource_tags(resource) -> Dict[str, str]:
    """Azure 리소스에서 태그를 추출합니다."""
    if hasattr(resource, 'tags') and resource.tags:
        return dict(resource.tags)
    return {}

def check_azure_tag_compliance(tags: Dict[str, str], required_tags: List[str], optional_tags: List[str] = None) -> Dict[str, Any]:
    """Azure 리소스 태그 규정 준수를 확인합니다."""
    result = {
        'compliant': True,
        'missing_required': [],
        'missing_optional': [],
        'present_tags': list(tags.keys()),
        'tag_count': len(tags)
    }
    
    # 필수 태그 확인
    for required_tag in required_tags:
        if required_tag not in tags:
            result['missing_required'].append(required_tag)
            result['compliant'] = False
    
    # 선택적 태그 확인
    if optional_tags:
        for optional_tag in optional_tags:
            if optional_tag not in tags:
                result['missing_optional'].append(optional_tag)
    
    return result

def parallel_azure_operation(operation_func, subscription_ids: List[str], *args, **kwargs) -> List[Any]:
    """여러 Azure 구독에서 병렬로 작업을 수행합니다."""
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        
        for subscription_id in subscription_ids:
            future = executor.submit(operation_func, subscription_id, *args, **kwargs)
            futures.append(future)
        
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.extend(result if isinstance(result, list) else [result])
            except Exception as e:
                log_error(f"병렬 작업 실패: {e}")
    
    return results

def get_azure_resource_by_id(resource_id: str, subscription_id: str) -> Optional[Dict[str, Any]]:
    """리소스 ID로 Azure 리소스 정보를 가져옵니다."""
    try:
        resource_client = create_azure_client(ResourceManagementClient, subscription_id)
        if not resource_client:
            return None
        
        # 리소스 ID에서 정보 추출
        parts = resource_id.split('/')
        if len(parts) < 8:
            return None
        
        resource_group_name = parts[4]
        resource_provider = parts[6]
        resource_type = parts[7]
        resource_name = parts[8]
        
        # 리소스 정보 조회
        resource = resource_client.resources.get(
            resource_group_name=resource_group_name,
            resource_provider_namespace=resource_provider,
            resource_type=resource_type,
            resource_name=resource_name,
            api_version='2021-04-01'
        )
        
        return {
            'id': resource.id,
            'name': resource.name,
            'type': resource.type,
            'location': resource.location,
            'tags': resource.tags or {},
            'subscription_id': subscription_id
        }
        
    except Exception as e:
        log_error(f"Azure 리소스 조회 실패: ResourceId={resource_id}, Error={e}")
        return None

# Azure 서비스별 기본 API 버전
AZURE_API_VERSIONS = {
    'compute': '2023-03-01',
    'network': '2023-04-01',
    'storage': '2023-01-01',
    'containerservice': '2023-03-01',
    'containerinstance': '2023-05-01',
    'sql': '2021-11-01',
    'eventhub': '2021-11-01'
}

def get_api_version(service: str) -> str:
    """Azure 서비스의 API 버전을 가져옵니다."""
    return AZURE_API_VERSIONS.get(service, '2021-04-01')

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