#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
from google.cloud.compute_v1 import (
    ForwardingRulesClient, BackendServicesClient, UrlMapsClient,
    TargetHttpProxiesClient, TargetHttpsProxiesClient, TargetTcpProxiesClient,
    TargetSslProxiesClient, HealthChecksClient, SslCertificatesClient
)
from google.cloud.compute_v1.types import (
    ListForwardingRulesRequest, ListBackendServicesRequest, ListUrlMapsRequest,
    ListTargetHttpProxiesRequest, ListTargetHttpsProxiesRequest,
    ListTargetTcpProxiesRequest, ListTargetSslProxiesRequest,
    ListHealthChecksRequest, ListSslCertificatesRequest,
    AggregatedListForwardingRulesRequest
)
from google.api_core import exceptions as gcp_exceptions
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule
from rich.tree import Tree

from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    create_gcp_client, format_gcp_output, get_gcp_resource_labels
)
from common.log import log_info, log_error, log_exception

# Import MCP integration
try:
    from mcp.gcp_connector import MCPGCPService
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

console = Console()


def fetch_load_balancers_via_mcp(mcp_connector, project_id: str, region_filter: str = None) -> List[Dict]:
    """
    MCP 서버를 통해 GCP Load Balancer를 가져옵니다.
    
    Args:
        mcp_connector: MCP GCP 커넥터
        project_id: GCP 프로젝트 ID
        region_filter: 리전 필터 (선택사항)
    
    Returns:
        Load Balancer 정보 리스트
    """
    try:
        params = {
            'project_id': project_id,
            'region_filter': region_filter
        }
        
        response = mcp_connector.execute_gcp_query('lb', 'list_load_balancers', params)
        if response.success:
            return response.data.get('load_balancers', [])
        else:
            log_error(f"MCP load balancers query failed: {response.error}")
            return []
            
    except Exception as e:
        log_error(f"MCP load balancers fetch failed: {e}")
        return []


def fetch_load_balancers_direct(project_id: str, region_filter: str = None) -> List[Dict]:
    """
    직접 API를 통해 GCP Load Balancer를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 리전 필터 (선택사항)
    
    Returns:
        Load Balancer 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        all_load_balancers = []
        
        # Global Load Balancers 수집
        global_lbs = collect_global_load_balancers(credentials, project_id)
        all_load_balancers.extend(global_lbs)
        
        # Regional Load Balancers 수집
        regional_lbs = collect_regional_load_balancers(credentials, project_id, region_filter)
        all_load_balancers.extend(regional_lbs)
        
        log_info(f"프로젝트 {project_id}에서 {len(all_load_balancers)}개 Load Balancer 발견")
        return all_load_balancers
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Load Balancing 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Load Balancer 조회 실패: {project_id}, Error={e}")
        return []


def collect_global_load_balancers(credentials, project_id: str) -> List[Dict]:
    """
    Global Load Balancer들을 수집합니다.
    
    Args:
        credentials: GCP 인증 정보
        project_id: GCP 프로젝트 ID
    
    Returns:
        Global Load Balancer 정보 리스트
    """
    load_balancers = []
    
    try:
        # Global Forwarding Rules 클라이언트 (ForwardingRulesClient를 global scope로 사용)
        global_forwarding_client = ForwardingRulesClient(credentials=credentials)
        global_backend_client = BackendServicesClient(credentials=credentials)
        url_maps_client = UrlMapsClient(credentials=credentials)
        target_http_client = TargetHttpProxiesClient(credentials=credentials)
        target_https_client = TargetHttpsProxiesClient(credentials=credentials)
        target_tcp_client = TargetTcpProxiesClient(credentials=credentials)
        target_ssl_client = TargetSslProxiesClient(credentials=credentials)
        health_checks_client = HealthChecksClient(credentials=credentials)
        ssl_certs_client = SslCertificatesClient(credentials=credentials)
        
        # Global Forwarding Rules 가져오기 (aggregated list 사용)
        request = AggregatedListForwardingRulesRequest(project=project_id)
        aggregated_list = global_forwarding_client.aggregated_list(request=request)
        
        # Global scope만 필터링
        forwarding_rules = []
        for location, forwarding_rules_scoped_list in aggregated_list:
            if location == 'global' and forwarding_rules_scoped_list.forwarding_rules:
                forwarding_rules.extend(forwarding_rules_scoped_list.forwarding_rules)
        
        for rule in forwarding_rules:
            try:
                lb_data = collect_load_balancer_details(
                    rule, project_id, 'global', credentials,
                    global_backend_client, url_maps_client,
                    target_http_client, target_https_client,
                    target_tcp_client, target_ssl_client,
                    health_checks_client, ssl_certs_client
                )
                if lb_data:
                    load_balancers.append(lb_data)
                    
            except Exception as e:
                log_error(f"Global Load Balancer {rule.name} 상세 정보 수집 실패: {e}")
                continue
        
    except gcp_exceptions.Forbidden:
        log_error(f"Global Load Balancing 접근 권한이 없습니다: {project_id}")
    except Exception as e:
        log_error(f"Global Load Balancer 조회 실패: {project_id}, Error={e}")
    
    return load_balancers


def collect_regional_load_balancers(credentials, project_id: str, region_filter: str = None) -> List[Dict]:
    """
    Regional Load Balancer들을 수집합니다.
    
    Args:
        credentials: GCP 인증 정보
        project_id: GCP 프로젝트 ID
        region_filter: 리전 필터 (선택사항)
    
    Returns:
        Regional Load Balancer 정보 리스트
    """
    load_balancers = []
    
    try:
        # Regional Forwarding Rules 클라이언트
        forwarding_client = ForwardingRulesClient(credentials=credentials)
        backend_client = BackendServicesClient(credentials=credentials)
        health_checks_client = HealthChecksClient(credentials=credentials)
        
        # Aggregated list로 모든 리전의 Forwarding Rules 가져오기
        request = AggregatedListForwardingRulesRequest(project=project_id)
        aggregated_list = forwarding_client.aggregated_list(request=request)
        
        for location, forwarding_rules_scoped_list in aggregated_list:
            # 리전 필터 적용
            if region_filter and region_filter not in location:
                continue
                
            if not forwarding_rules_scoped_list.forwarding_rules:
                continue
                
            region = location.replace('regions/', '')
            
            for rule in forwarding_rules_scoped_list.forwarding_rules:
                try:
                    lb_data = collect_regional_load_balancer_details(
                        rule, project_id, region, credentials,
                        backend_client, health_checks_client
                    )
                    if lb_data:
                        load_balancers.append(lb_data)
                        
                except Exception as e:
                    log_error(f"Regional Load Balancer {rule.name} 상세 정보 수집 실패: {e}")
                    continue
        
    except gcp_exceptions.Forbidden:
        log_error(f"Regional Load Balancing 접근 권한이 없습니다: {project_id}")
    except Exception as e:
        log_error(f"Regional Load Balancer 조회 실패: {project_id}, Error={e}")
    
    return load_balancers


def collect_load_balancer_details(rule, project_id: str, scope: str, credentials,
                                backend_client, url_maps_client,
                                target_http_client, target_https_client,
                                target_tcp_client, target_ssl_client,
                                health_checks_client, ssl_certs_client) -> Optional[Dict]:
    """
    Global Load Balancer의 상세 정보를 수집합니다.
    
    Args:
        rule: Forwarding Rule 객체
        project_id: GCP 프로젝트 ID
        scope: 'global' 또는 리전명
        credentials: GCP 인증 정보
        *_client: 각종 클라이언트 객체들
    
    Returns:
        Load Balancer 상세 정보 딕셔너리
    """
    try:
        lb_data = {
            'project_id': project_id,
            'name': rule.name,
            'scope': scope,
            'type': determine_lb_type(rule),
            'ip_address': rule.i_p_address,
            'port_range': rule.port_range,
            'ip_protocol': rule.i_p_protocol,
            'load_balancing_scheme': rule.load_balancing_scheme,
            'network_tier': getattr(rule, 'network_tier', 'PREMIUM'),
            'creation_timestamp': rule.creation_timestamp,
            'description': rule.description or '',
            'labels': get_gcp_resource_labels(rule),
            'target': {},
            'backend_services': [],
            'url_map': {},
            'health_checks': [],
            'ssl_certificates': [],
            'status': 'ACTIVE'  # Forwarding rules don't have explicit status
        }
        
        # Target 정보 수집
        if rule.target:
            target_name = rule.target.split('/')[-1]
            target_type = determine_target_type(rule.target)
            
            lb_data['target'] = {
                'name': target_name,
                'type': target_type,
                'url': rule.target
            }
            
            # Target에 따른 추가 정보 수집
            if target_type == 'targetHttpProxies':
                target_details = get_target_http_proxy_details(
                    target_http_client, project_id, target_name
                )
                lb_data['target'].update(target_details)
                
                # URL Map 정보 수집
                if target_details.get('url_map'):
                    url_map_name = target_details['url_map'].split('/')[-1]
                    lb_data['url_map'] = get_url_map_details(
                        url_maps_client, project_id, url_map_name
                    )
                    
            elif target_type == 'targetHttpsProxies':
                target_details = get_target_https_proxy_details(
                    target_https_client, project_id, target_name
                )
                lb_data['target'].update(target_details)
                
                # SSL 인증서 정보 수집
                if target_details.get('ssl_certificates'):
                    for cert_url in target_details['ssl_certificates']:
                        cert_name = cert_url.split('/')[-1]
                        cert_details = get_ssl_certificate_details(
                            ssl_certs_client, project_id, cert_name
                        )
                        if cert_details:
                            lb_data['ssl_certificates'].append(cert_details)
                
                # URL Map 정보 수집
                if target_details.get('url_map'):
                    url_map_name = target_details['url_map'].split('/')[-1]
                    lb_data['url_map'] = get_url_map_details(
                        url_maps_client, project_id, url_map_name
                    )
                    
            elif target_type == 'targetTcpProxies':
                target_details = get_target_tcp_proxy_details(
                    target_tcp_client, project_id, target_name
                )
                lb_data['target'].update(target_details)
                
            elif target_type == 'targetSslProxies':
                target_details = get_target_ssl_proxy_details(
                    target_ssl_client, project_id, target_name
                )
                lb_data['target'].update(target_details)
        
        # Backend Services 정보 수집
        if lb_data['url_map'].get('default_service'):
            backend_service_name = lb_data['url_map']['default_service'].split('/')[-1]
            backend_details = get_backend_service_details(
                backend_client, project_id, backend_service_name, scope
            )
            if backend_details:
                lb_data['backend_services'].append(backend_details)
                
                # Health Checks 정보 수집
                for hc_url in backend_details.get('health_checks', []):
                    hc_name = hc_url.split('/')[-1]
                    hc_details = get_health_check_details(
                        health_checks_client, project_id, hc_name, scope
                    )
                    if hc_details:
                        lb_data['health_checks'].append(hc_details)
        
        return lb_data
        
    except Exception as e:
        log_error(f"Load Balancer 상세 정보 수집 실패: {rule.name}, Error={e}")
        return None


def collect_regional_load_balancer_details(rule, project_id: str, region: str, credentials,
                                         backend_client, health_checks_client) -> Optional[Dict]:
    """
    Regional Load Balancer의 상세 정보를 수집합니다.
    
    Args:
        rule: Forwarding Rule 객체
        project_id: GCP 프로젝트 ID
        region: 리전명
        credentials: GCP 인증 정보
        backend_client: Backend Services 클라이언트
        health_checks_client: Health Checks 클라이언트
    
    Returns:
        Load Balancer 상세 정보 딕셔너리
    """
    try:
        lb_data = {
            'project_id': project_id,
            'name': rule.name,
            'scope': region,
            'type': determine_lb_type(rule),
            'ip_address': rule.i_p_address,
            'port_range': rule.port_range,
            'ip_protocol': rule.i_p_protocol,
            'load_balancing_scheme': rule.load_balancing_scheme,
            'network_tier': getattr(rule, 'network_tier', 'PREMIUM'),
            'creation_timestamp': rule.creation_timestamp,
            'description': rule.description or '',
            'labels': get_gcp_resource_labels(rule),
            'target': {},
            'backend_services': [],
            'url_map': {},
            'health_checks': [],
            'ssl_certificates': [],
            'status': 'ACTIVE'
        }
        
        # Backend Service 정보 수집 (Regional)
        if rule.backend_service:
            backend_service_name = rule.backend_service.split('/')[-1]
            backend_details = get_regional_backend_service_details(
                backend_client, project_id, region, backend_service_name
            )
            if backend_details:
                lb_data['backend_services'].append(backend_details)
                
                # Health Checks 정보 수집
                for hc_url in backend_details.get('health_checks', []):
                    hc_name = hc_url.split('/')[-1]
                    hc_details = get_regional_health_check_details(
                        health_checks_client, project_id, region, hc_name
                    )
                    if hc_details:
                        lb_data['health_checks'].append(hc_details)
        
        return lb_data
        
    except Exception as e:
        log_error(f"Regional Load Balancer 상세 정보 수집 실패: {rule.name}, Error={e}")
        return None


def determine_lb_type(rule) -> str:
    """
    Forwarding Rule을 기반으로 Load Balancer 타입을 결정합니다.
    
    Args:
        rule: Forwarding Rule 객체
    
    Returns:
        Load Balancer 타입 문자열
    """
    if rule.load_balancing_scheme == 'EXTERNAL':
        if rule.i_p_protocol in ['TCP', 'UDP']:
            if rule.target and 'targetTcpProxies' in rule.target:
                return 'TCP_PROXY'
            elif rule.target and 'targetSslProxies' in rule.target:
                return 'SSL_PROXY'
            else:
                return 'NETWORK_TCP_UDP'
        elif rule.i_p_protocol == 'HTTP':
            return 'HTTP_HTTPS'
    elif rule.load_balancing_scheme == 'INTERNAL':
        return 'INTERNAL_TCP_UDP'
    elif rule.load_balancing_scheme == 'INTERNAL_MANAGED':
        return 'INTERNAL_HTTP_HTTPS'
    
    return 'UNKNOWN'


def determine_target_type(target_url: str) -> str:
    """
    Target URL에서 타입을 추출합니다.
    
    Args:
        target_url: Target URL
    
    Returns:
        Target 타입
    """
    if 'targetHttpProxies' in target_url:
        return 'targetHttpProxies'
    elif 'targetHttpsProxies' in target_url:
        return 'targetHttpsProxies'
    elif 'targetTcpProxies' in target_url:
        return 'targetTcpProxies'
    elif 'targetSslProxies' in target_url:
        return 'targetSslProxies'
    else:
        return 'unknown'


def get_target_http_proxy_details(client, project_id: str, proxy_name: str) -> Dict:
    """Target HTTP Proxy 상세 정보를 가져옵니다."""
    try:
        proxy = client.get(project=project_id, target_http_proxy=proxy_name)
        return {
            'url_map': proxy.url_map,
            'description': proxy.description or ''
        }
    except Exception as e:
        log_error(f"Target HTTP Proxy {proxy_name} 조회 실패: {e}")
        return {}


def get_target_https_proxy_details(client, project_id: str, proxy_name: str) -> Dict:
    """Target HTTPS Proxy 상세 정보를 가져옵니다."""
    try:
        proxy = client.get(project=project_id, target_https_proxy=proxy_name)
        return {
            'url_map': proxy.url_map,
            'ssl_certificates': list(proxy.ssl_certificates) if proxy.ssl_certificates else [],
            'description': proxy.description or ''
        }
    except Exception as e:
        log_error(f"Target HTTPS Proxy {proxy_name} 조회 실패: {e}")
        return {}


def get_target_tcp_proxy_details(client, project_id: str, proxy_name: str) -> Dict:
    """Target TCP Proxy 상세 정보를 가져옵니다."""
    try:
        proxy = client.get(project=project_id, target_tcp_proxy=proxy_name)
        return {
            'service': proxy.service,
            'proxy_header': proxy.proxy_header,
            'description': proxy.description or ''
        }
    except Exception as e:
        log_error(f"Target TCP Proxy {proxy_name} 조회 실패: {e}")
        return {}


def get_target_ssl_proxy_details(client, project_id: str, proxy_name: str) -> Dict:
    """Target SSL Proxy 상세 정보를 가져옵니다."""
    try:
        proxy = client.get(project=project_id, target_ssl_proxy=proxy_name)
        return {
            'service': proxy.service,
            'ssl_certificates': list(proxy.ssl_certificates) if proxy.ssl_certificates else [],
            'proxy_header': proxy.proxy_header,
            'description': proxy.description or ''
        }
    except Exception as e:
        log_error(f"Target SSL Proxy {proxy_name} 조회 실패: {e}")
        return {}


def get_url_map_details(client, project_id: str, url_map_name: str) -> Dict:
    """URL Map 상세 정보를 가져옵니다."""
    try:
        url_map = client.get(project=project_id, url_map=url_map_name)
        return {
            'name': url_map.name,
            'default_service': url_map.default_service,
            'host_rules': len(url_map.host_rules) if url_map.host_rules else 0,
            'path_matchers': len(url_map.path_matchers) if url_map.path_matchers else 0,
            'description': url_map.description or ''
        }
    except Exception as e:
        log_error(f"URL Map {url_map_name} 조회 실패: {e}")
        return {}


def get_backend_service_details(client, project_id: str, service_name: str, scope: str = 'global') -> Dict:
    """Backend Service 상세 정보를 가져옵니다."""
    try:
        if scope == 'global':
            # Global backend service
            service = client.get(project=project_id, backend_service=service_name)
        else:
            # Regional backend service
            service = client.get(project=project_id, region=scope, backend_service=service_name)
            
        return {
            'name': service.name,
            'protocol': service.protocol,
            'port': service.port,
            'port_name': service.port_name,
            'timeout_sec': service.timeout_sec,
            'backends': len(service.backends) if service.backends else 0,
            'health_checks': list(service.health_checks) if service.health_checks else [],
            'load_balancing_scheme': service.load_balancing_scheme,
            'session_affinity': service.session_affinity,
            'description': service.description or ''
        }
    except Exception as e:
        log_error(f"Backend Service {service_name} 조회 실패: {e}")
        return {}


def get_regional_backend_service_details(client, project_id: str, region: str, service_name: str) -> Dict:
    """Regional Backend Service 상세 정보를 가져옵니다."""
    try:
        service = client.get(project=project_id, region=region, backend_service=service_name)
        return {
            'name': service.name,
            'protocol': service.protocol,
            'port': service.port,
            'port_name': service.port_name,
            'timeout_sec': service.timeout_sec,
            'backends': len(service.backends) if service.backends else 0,
            'health_checks': list(service.health_checks) if service.health_checks else [],
            'load_balancing_scheme': service.load_balancing_scheme,
            'session_affinity': service.session_affinity,
            'description': service.description or ''
        }
    except Exception as e:
        log_error(f"Regional Backend Service {service_name} 조회 실패: {e}")
        return {}


def get_health_check_details(client, project_id: str, hc_name: str, scope: str = 'global') -> Dict:
    """Health Check 상세 정보를 가져옵니다."""
    try:
        if scope == 'global':
            # Global health check
            hc = client.get(project=project_id, health_check=hc_name)
        else:
            # Regional health check
            hc = client.get(project=project_id, region=scope, health_check=hc_name)
            
        return {
            'name': hc.name,
            'type': hc.type_,
            'check_interval_sec': hc.check_interval_sec,
            'timeout_sec': hc.timeout_sec,
            'healthy_threshold': hc.healthy_threshold,
            'unhealthy_threshold': hc.unhealthy_threshold,
            'description': hc.description or ''
        }
    except Exception as e:
        log_error(f"Health Check {hc_name} 조회 실패: {e}")
        return {}


def get_regional_health_check_details(client, project_id: str, region: str, hc_name: str) -> Dict:
    """Regional Health Check 상세 정보를 가져옵니다."""
    try:
        hc = client.get(project=project_id, region=region, health_check=hc_name)
        return {
            'name': hc.name,
            'type': hc.type_,
            'check_interval_sec': hc.check_interval_sec,
            'timeout_sec': hc.timeout_sec,
            'healthy_threshold': hc.healthy_threshold,
            'unhealthy_threshold': hc.unhealthy_threshold,
            'description': hc.description or ''
        }
    except Exception as e:
        log_error(f"Regional Health Check {hc_name} 조회 실패: {e}")
        return {}


def get_ssl_certificate_details(client, project_id: str, cert_name: str) -> Dict:
    """SSL Certificate 상세 정보를 가져옵니다."""
    try:
        cert = client.get(project=project_id, ssl_certificate=cert_name)
        return {
            'name': cert.name,
            'type': cert.type_,
            'creation_timestamp': cert.creation_timestamp,
            'expire_time': cert.expire_time,
            'subject_alternative_names': list(cert.subject_alternative_names) if cert.subject_alternative_names else [],
            'description': cert.description or ''
        }
    except Exception as e:
        log_error(f"SSL Certificate {cert_name} 조회 실패: {e}")
        return {}


def fetch_load_balancers(project_id: str, region_filter: str = None) -> List[Dict]:
    """
    GCP Load Balancer를 가져옵니다 (MCP 우선, 직접 API 폴백).
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 리전 필터 (선택사항)
    
    Returns:
        Load Balancer 정보 리스트
    """
    # MCP 서비스 사용 시도
    if MCP_AVAILABLE:
        try:
            mcp_service = MCPGCPService('lb')
            return mcp_service.execute_with_fallback(
                'list_load_balancers',
                {'project_id': project_id, 'region_filter': region_filter},
                lambda project_id, region_filter: fetch_load_balancers_direct(project_id, region_filter)
            )
        except Exception as e:
            log_error(f"MCP service failed, using direct API: {e}")
    
    # 직접 API 사용
    return fetch_load_balancers_direct(project_id, region_filter)

def load_mock_data():
    """mock_data.json에서 데이터를 로드합니다."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    mock_file = os.path.join(dir_path, 'mock_data.json')

    try:
        with open(mock_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[bold red]에러: Mock 데이터 파일을 찾을 수 없습니다: {mock_file}[/bold red]")
        return []
    except json.JSONDecodeError:
        console.print(f"[bold red]에러: Mock 데이터 파일의 형식이 올바르지 않습니다: {mock_file}[/bold red]")
        return []


def format_table_output(load_balancers: List[Dict]) -> None:
    """
    GCP Load Balancer 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        load_balancers: Load Balancer 정보 리스트
    """
    if not load_balancers:
        console.print("[yellow]표시할 GCP Load Balancer 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 스코프, 이름 순으로 정렬
    load_balancers.sort(key=lambda x: (x.get("project_id", ""), x.get("scope", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Scope", style="bold cyan")
    table.add_column("LB Name", style="bold white")
    table.add_column("Type", style="dim")
    table.add_column("IP Address", style="blue")
    table.add_column("Protocol", justify="center")
    table.add_column("Port Range", justify="center")
    table.add_column("Backends", justify="center", style="green")
    table.add_column("Health Checks", justify="center", style="yellow")
    table.add_column("SSL Certs", justify="center", style="red")

    last_project = None
    last_scope = None
    
    for i, lb in enumerate(load_balancers):
        project_changed = lb.get("project_id") != last_project
        scope_changed = lb.get("scope") != last_scope

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", "", end_section=True)

        # Load Balancer 타입에 따른 색상 적용
        lb_type = lb.get('type', 'UNKNOWN')
        if lb_type == 'HTTP_HTTPS':
            type_colored = f"[green]{lb_type}[/green]"
        elif lb_type in ['TCP_PROXY', 'SSL_PROXY']:
            type_colored = f"[blue]{lb_type}[/blue]"
        elif lb_type == 'NETWORK_TCP_UDP':
            type_colored = f"[yellow]{lb_type}[/yellow]"
        elif lb_type.startswith('INTERNAL'):
            type_colored = f"[cyan]{lb_type}[/cyan]"
        else:
            type_colored = f"[dim]{lb_type}[/dim]"
        
        # Backend Services 개수
        backend_count = len(lb.get('backend_services', []))
        backend_info = f"{backend_count}" if backend_count > 0 else "-"
        
        # Health Checks 개수
        hc_count = len(lb.get('health_checks', []))
        hc_info = f"{hc_count}" if hc_count > 0 else "-"
        
        # SSL Certificates 개수
        ssl_count = len(lb.get('ssl_certificates', []))
        ssl_info = f"{ssl_count}" if ssl_count > 0 else "-"
        
        display_values = [
            lb.get("project_id", "") if project_changed else "",
            lb.get("scope", "") if project_changed or scope_changed else "",
            lb.get("name", "N/A"),
            type_colored,
            lb.get("ip_address", "-"),
            lb.get("ip_protocol", "-"),
            lb.get("port_range", "-"),
            backend_info,
            hc_info,
            ssl_info
        ]
        
        table.add_row(*display_values)

        last_project = lb.get("project_id")
        last_scope = lb.get("scope")
    
    console.print(table)


def format_tree_output(load_balancers: List[Dict]) -> None:
    """
    GCP Load Balancer 목록을 트리 형식으로 출력합니다 (프로젝트/스코프 계층).
    
    Args:
        load_balancers: Load Balancer 정보 리스트
    """
    if not load_balancers:
        console.print("[yellow]표시할 GCP Load Balancer 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for lb in load_balancers:
        project_id = lb.get("project_id", "unknown")
        scope = lb.get("scope", "unknown")
        
        if project_id not in projects:
            projects[project_id] = {}
        if scope not in projects[project_id]:
            projects[project_id][scope] = []
        
        projects[project_id][scope].append(lb)

    # 트리 구조 생성
    tree = Tree("⚖️ [bold blue]GCP Load Balancers[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        
        for scope in sorted(projects[project_id].keys()):
            scope_lbs = projects[project_id][scope]
            scope_icon = "🌐" if scope == "global" else "🌍"
            scope_node = project_node.add(
                f"{scope_icon} [bold cyan]{scope}[/bold cyan] ({len(scope_lbs)} load balancers)"
            )
            
            for lb in sorted(scope_lbs, key=lambda x: x.get("name", "")):
                # Load Balancer 타입 아이콘
                lb_type = lb.get('type', 'UNKNOWN')
                if lb_type == 'HTTP_HTTPS':
                    type_icon = "🌐"
                elif lb_type in ['TCP_PROXY', 'SSL_PROXY']:
                    type_icon = "🔒"
                elif lb_type == 'NETWORK_TCP_UDP':
                    type_icon = "🔌"
                elif lb_type.startswith('INTERNAL'):
                    type_icon = "🏠"
                else:
                    type_icon = "⚖️"
                
                # Load Balancer 정보
                lb_name = lb.get("name", "N/A")
                ip_address = lb.get("ip_address", "N/A")
                protocol = lb.get("ip_protocol", "N/A")
                port_range = lb.get("port_range", "N/A")
                
                lb_info = (
                    f"{type_icon} [bold white]{lb_name}[/bold white] "
                    f"({lb_type}) - "
                    f"IP: [blue]{ip_address}[/blue], "
                    f"Protocol: {protocol}"
                )
                
                if port_range and port_range != "-":
                    lb_info += f", Ports: {port_range}"
                
                lb_node = scope_node.add(lb_info)
                
                # Backend Services 정보
                backend_services = lb.get('backend_services', [])
                if backend_services:
                    backends_node = lb_node.add(f"🔧 Backend Services ({len(backend_services)})")
                    for backend in backend_services:
                        backend_name = backend.get('name', 'N/A')
                        backend_protocol = backend.get('protocol', 'N/A')
                        backend_count = backend.get('backends', 0)
                        backends_node.add(
                            f"• {backend_name} ({backend_protocol}) - {backend_count} backends"
                        )
                
                # Health Checks 정보
                health_checks = lb.get('health_checks', [])
                if health_checks:
                    hc_node = lb_node.add(f"❤️ Health Checks ({len(health_checks)})")
                    for hc in health_checks:
                        hc_name = hc.get('name', 'N/A')
                        hc_type = hc.get('type', 'N/A')
                        hc_interval = hc.get('check_interval_sec', 'N/A')
                        hc_node.add(f"• {hc_name} ({hc_type}) - {hc_interval}s interval")
                
                # SSL Certificates 정보
                ssl_certs = lb.get('ssl_certificates', [])
                if ssl_certs:
                    ssl_node = lb_node.add(f"🔐 SSL Certificates ({len(ssl_certs)})")
                    for cert in ssl_certs:
                        cert_name = cert.get('name', 'N/A')
                        cert_type = cert.get('type', 'N/A')
                        ssl_node.add(f"• {cert_name} ({cert_type})")
                
                # URL Map 정보
                url_map = lb.get('url_map', {})
                if url_map and url_map.get('name'):
                    url_map_name = url_map.get('name', 'N/A')
                    host_rules = url_map.get('host_rules', 0)
                    path_matchers = url_map.get('path_matchers', 0)
                    lb_node.add(
                        f"🗺️ URL Map: {url_map_name} "
                        f"({host_rules} host rules, {path_matchers} path matchers)"
                    )

    console.print(tree)


def format_output(load_balancers: List[Dict], output_format: str = 'table') -> str:
    """
    Load Balancer 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        load_balancers: Load Balancer 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(load_balancers)
        return ""
    elif output_format == 'tree':
        format_tree_output(load_balancers)
        return ""
    elif output_format == 'json':
        return format_gcp_output(load_balancers, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(load_balancers, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(load_balancers)
        return ""


def main(args):
    """
    메인 함수 - GCP Load Balancer 정보를 조회하고 출력합니다.
    
    Args:
        args: CLI 인자 객체
    """
    try:
        log_info("GCP Load Balancer 조회 시작")
        
        # GCP 인증 및 프로젝트 관리자 초기화
        auth_manager = GCPAuthManager()
        if not auth_manager.validate_credentials():
            console.print("[bold red]GCP 인증에 실패했습니다. 인증 정보를 확인해주세요.[/bold red]")
            return
        
        project_manager = GCPProjectManager(auth_manager)
        resource_collector = GCPResourceCollector(auth_manager)
        
        # 프로젝트 목록 가져오기
        if args.project:
            # 특정 프로젝트 지정된 경우
            projects = [args.project]
        else:
            # 모든 접근 가능한 프로젝트 사용
            projects = project_manager.get_projects()
        
        if not projects:
            console.print("[yellow]접근 가능한 GCP 프로젝트가 없습니다.[/yellow]")
            return
        
        log_info(f"조회할 프로젝트: {len(projects)}개")
        
        # 병렬로 Load Balancer 수집
        all_load_balancers = resource_collector.parallel_collect(
            projects, 
            fetch_load_balancers,
            getattr(args, 'region', None)
        )
        
        if not all_load_balancers:
            console.print("[yellow]조회된 Load Balancer가 없습니다.[/yellow]")
            return
        
        # 필터 적용
        filters = {}
        if hasattr(args, 'lb_name') and args.lb_name:
            filters['name'] = args.lb_name
        if hasattr(args, 'project') and args.project:
            filters['project'] = args.project
        if hasattr(args, 'region') and args.region:
            filters['scope'] = args.region
        if hasattr(args, 'lb_type') and args.lb_type:
            filters['type'] = args.lb_type
        
        filtered_load_balancers = resource_collector.apply_filters(all_load_balancers, filters)
        
        # 출력 형식 결정
        output_format = getattr(args, 'output', 'table')
        
        # 결과 출력
        if output_format in ['json', 'yaml']:
            output_text = format_output(filtered_load_balancers, output_format)
            console.print(output_text)
        else:
            format_output(filtered_load_balancers, output_format)
        
        log_info(f"총 {len(filtered_load_balancers)}개 Load Balancer 조회 완료")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자에 의해 중단되었습니다.[/yellow]")
    except Exception as e:
        log_exception(e)
        console.print(f"[bold red]오류 발생: {e}[/bold red]")


def add_arguments(parser):
    """
    CLI 인자를 추가합니다.
    
    Args:
        parser: argparse.ArgumentParser 객체
    """
    parser.add_argument(
        '-p', '--project', 
        help='GCP 프로젝트 ID로 필터링 (예: my-project-123)'
    )
    parser.add_argument(
        '-n', '--lb-name', 
        help='Load Balancer 이름으로 필터링 (부분 일치)'
    )
    parser.add_argument(
        '-r', '--region', 
        help='리전으로 필터링 (예: us-central1, global)'
    )
    parser.add_argument(
        '-t', '--lb-type',
        choices=['HTTP_HTTPS', 'TCP_PROXY', 'SSL_PROXY', 'NETWORK_TCP_UDP', 'INTERNAL_TCP_UDP', 'INTERNAL_HTTP_HTTPS'],
        help='Load Balancer 타입으로 필터링'
    )
    parser.add_argument(
        '-o', '--output', 
        choices=['table', 'tree', 'json', 'yaml'],
        default='table',
        help='출력 형식 선택 (기본값: table)'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Load Balancer 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)