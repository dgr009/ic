#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
try:
    from google.cloud.compute_v1 import (
        ForwardingRulesClient, BackendServicesClient, UrlMapsClient,
        TargetHttpProxiesClient, TargetHttpsProxiesClient, TargetTcpProxiesClient,
        TargetSslProxiesClient, HealthChecksClient, SslCertificatesClient,
        TargetPoolsClient, InstanceReference
    )
    from google.cloud.compute_v1.types import (
        ListTargetHttpProxiesRequest, ListTargetHttpsProxiesRequest,
        ListTargetTcpProxiesRequest, ListTargetSslProxiesRequest,
        ListHealthChecksRequest, ListSslCertificatesRequest,
        AggregatedListForwardingRulesRequest
    )
    from google.api_core import exceptions as gcp_exceptions
    GCP_LB_AVAILABLE = True
except ImportError:
    GCP_LB_AVAILABLE = False
    ForwardingRulesClient: Any = None
    BackendServicesClient: Any = None
    UrlMapsClient: Any = None
    TargetHttpProxiesClient: Any = None
    TargetHttpsProxiesClient: Any = None
    TargetTcpProxiesClient: Any = None
    TargetSslProxiesClient: Any = None
    HealthChecksClient: Any = None
    SslCertificatesClient: Any = None
    TargetPoolsClient: Any = None
    InstanceReference: Any = None
    AggregatedListForwardingRulesRequest: Any = None
    ListTargetHttpProxiesRequest: Any = None
    ListTargetHttpsProxiesRequest: Any = None
    ListTargetTcpProxiesRequest: Any = None
    ListTargetSslProxiesRequest: Any = None
    ListHealthChecksRequest: Any = None
    ListSslCertificatesRequest: Any = None
    gcp_exceptions: Any = None
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree
from rich.rule import Rule

from ic.core.interfaces import BaseCommand, CommandResult

from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    format_gcp_output, get_gcp_resource_labels
)
from common.log import log_info, log_error, log_exception, log_info_non_console

console = Console()


def fetch_load_balancers_direct(project_id: str, region_filter: Optional[str] = None) -> List[Dict]:
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
            log_info_non_console(f"GCP 인증 실패: {project_id}")
            return []
        
        all_load_balancers = []
        
        # Global Load Balancers 수집
        global_lbs = collect_global_load_balancers(credentials, project_id)
        all_load_balancers.extend(global_lbs)
        
        # Regional Load Balancers 수집
        regional_lbs = collect_regional_load_balancers(credentials, project_id, region_filter)
        all_load_balancers.extend(regional_lbs)
        
        log_info_non_console(f"프로젝트 {project_id}에서 {len(all_load_balancers)}개 Load Balancer 발견")
        return all_load_balancers
        
    except gcp_exceptions.PermissionDenied:
        log_info_non_console(f"프로젝트 {project_id}에 대한 Load Balancing 권한이 없습니다")
        return []
    except Exception as e:
        log_info_non_console(f"Load Balancer 조회 실패: {project_id}, Error={e}")
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
                log_info_non_console(f"Global Load Balancer {rule.name} 상세 정보 수집 실패: {e}")
                continue
        
    except gcp_exceptions.Forbidden:
        log_info_non_console(f"Global Load Balancing 접근 권한이 없습니다: {project_id}")
    except Exception as e:
        log_info_non_console(f"Global Load Balancer 조회 실패: {project_id}, Error={e}")
    
    return load_balancers


def collect_regional_load_balancers(credentials, project_id: str, region_filter: Optional[str] = None) -> List[Dict]:
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
        target_pools_client = TargetPoolsClient(credentials=credentials) if TargetPoolsClient else None
        
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
                        backend_client, health_checks_client, target_pools_client
                    )
                    if lb_data:
                        load_balancers.append(lb_data)
                        
                except Exception as e:
                    log_info_non_console(f"Regional Load Balancer {rule.name} 상세 정보 수집 실패: {e}")
                    continue
        
    except gcp_exceptions.Forbidden:
        log_info_non_console(f"Regional Load Balancing 접근 권한이 없습니다: {project_id}")
    except Exception as e:
        log_info_non_console(f"Regional Load Balancer 조회 실패: {project_id}, Error={e}")
    
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
            'ip_address': getattr(rule, 'I_p_address', None) or getattr(rule, 'ip_address', None) or getattr(rule, 'i_p_address', ''),
            'port_range': getattr(rule, 'port_range', ''),
            'ip_protocol': getattr(rule, 'I_p_protocol', None) or getattr(rule, 'ip_protocol', None) or getattr(rule, 'i_p_protocol', ''),
            'load_balancing_scheme': getattr(rule, 'load_balancing_scheme', ''),
            'network_tier': getattr(rule, 'network_tier', 'PREMIUM'),
            'creation_timestamp': rule.creation_timestamp,
            'description': rule.description or '',
            'labels': get_gcp_resource_labels(rule),
            'target': {},
            'target_pool': {},
            'targets': [],
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
                
                # Backend Groups to targets
                for bg in backend_details.get('backend_groups', []):
                    lb_data['targets'].append({
                        'name': bg.get('group', '-'),
                        'zone': '-',
                        'url': bg.get('group_url', ''),
                        'health': 'HEALTHY',
                        'pool': backend_service_name
                    })
        
        return lb_data
        
    except Exception as e:
        log_info_non_console(f"Load Balancer 상세 정보 수집 실패: {rule.name}, Error={e}")
        return None


def collect_regional_load_balancer_details(rule, project_id: str, region: str, credentials,
                                         backend_client, health_checks_client, target_pools_client=None) -> Optional[Dict]:
    """
    Regional Load Balancer의 상세 정보를 수집합니다.
    
    Args:
        rule: Forwarding Rule 객체
        project_id: GCP 프로젝트 ID
        region: 리전명
        credentials: GCP 인증 정보
        backend_client: Backend Services 클라이언트
        health_checks_client: Health Checks 클라이언트
        target_pools_client: Target Pools 클라이언트 (선택사항)
    
    Returns:
        Load Balancer 상세 정보 딕셔너리
    """
    try:
        lb_data = {
            'project_id': project_id,
            'name': rule.name,
            'scope': region,
            'type': determine_lb_type(rule),
            'ip_address': getattr(rule, 'I_p_address', None) or getattr(rule, 'ip_address', None) or getattr(rule, 'i_p_address', ''),
            'port_range': getattr(rule, 'port_range', ''),
            'ip_protocol': getattr(rule, 'I_p_protocol', None) or getattr(rule, 'ip_protocol', None) or getattr(rule, 'i_p_protocol', ''),
            'load_balancing_scheme': getattr(rule, 'load_balancing_scheme', ''),
            'network_tier': getattr(rule, 'network_tier', 'PREMIUM'),
            'creation_timestamp': rule.creation_timestamp,
            'description': rule.description or '',
            'labels': get_gcp_resource_labels(rule),
            'target': {},
            'target_pool': {},
            'targets': [],
            'backend_services': [],
            'url_map': {},
            'health_checks': [],
            'ssl_certificates': [],
            'status': 'ACTIVE'
        }
        
        # Backend Service 정보 수집 (Regional)
        if getattr(rule, 'backend_service', None):
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
                
                # Backend Groups to targets
                for bg in backend_details.get('backend_groups', []):
                    lb_data['targets'].append({
                        'name': bg.get('group', '-'),
                        'zone': '-',
                        'url': bg.get('group_url', ''),
                        'health': 'HEALTHY',
                        'pool': backend_service_name
                    })
        
        # Target Pool 정보 수집 (Regional External TCP/UDP Network LB)
        target_ref = getattr(rule, 'target', '') or ''
        if target_ref:
            target_name = target_ref.split('/')[-1]
            target_type = determine_target_type(target_ref)
            lb_data['target'] = {
                'name': target_name,
                'type': target_type,
                'url': target_ref
            }
            if target_type == 'targetPools' and target_pools_client:
                try:
                    tp = target_pools_client.get(
                        project=project_id,
                        region=region,
                        target_pool=target_name
                    )
                    instances = list(tp.instances) if getattr(tp, 'instances', None) else []
                    tp_hcs = list(tp.health_checks) if getattr(tp, 'health_checks', None) else []
                    
                    target_instances = []
                    for inst_url in instances:
                        inst_name = inst_url.split('/')[-1]
                        zone_name = inst_url.split('/zones/')[-1].split('/')[0] if '/zones/' in inst_url else '-'
                        
                        # Query health state for instance
                        health_state = "HEALTHY"
                        if InstanceReference:
                            try:
                                inst_ref = InstanceReference(instance=inst_url)
                                inst_health = target_pools_client.get_health(
                                    project=project_id,
                                    region=region,
                                    target_pool=target_name,
                                    instance_reference_resource=inst_ref
                                )
                                if inst_health.health_status:
                                    health_state = inst_health.health_status[0].health_state
                            except Exception as he:
                                log_info_non_console(f"Target pool instance health check 실패 ({inst_name}): {he}")
                                health_state = "HEALTHY"
                        
                        target_instances.append({
                            'name': inst_name,
                            'zone': zone_name,
                            'url': inst_url,
                            'health': health_state,
                            'pool': target_name
                        })
                    
                    lb_data['target_pool'] = {
                        'name': target_name,
                        'instances': target_instances,
                        'health_checks': [h.split('/')[-1] for h in tp_hcs],
                        'session_affinity': getattr(tp, 'session_affinity', 'NONE')
                    }
                    lb_data['targets'].extend(target_instances)
                    
                    for hc_url in tp_hcs:
                        hc_name = hc_url.split('/')[-1]
                        lb_data['health_checks'].append({
                            'name': hc_name,
                            'type': 'HTTP' if 'httpHealthChecks' in hc_url else 'TCP',
                            'check_interval_sec': 5
                        })
                except Exception as e:
                    log_info_non_console(f"Target Pool {target_name} 조회 실패: {e}")
        
        return lb_data
        
    except Exception as e:
        log_info_non_console(f"Regional Load Balancer 상세 정보 수집 실패: {rule.name}, Error={e}")
        return None


def determine_lb_type(rule) -> str:
    """
    Forwarding Rule을 기반으로 Load Balancer 타입을 결정합니다.
    
    Args:
        rule: Forwarding Rule 객체
    
    Returns:
        Load Balancer 타입 문자열
    """
    scheme = getattr(rule, 'load_balancing_scheme', '')
    protocol = getattr(rule, 'I_p_protocol', None) or getattr(rule, 'ip_protocol', None) or getattr(rule, 'i_p_protocol', '')
    target = getattr(rule, 'target', '')
    if scheme == 'EXTERNAL':
        if protocol in ['TCP', 'UDP']:
            if target and 'targetTcpProxies' in target:
                return 'TCP_PROXY'
            elif target and 'targetSslProxies' in target:
                return 'SSL_PROXY'
            else:
                return 'NETWORK_TCP_UDP'
        elif protocol == 'HTTP':
            return 'HTTP_HTTPS'
    elif scheme == 'INTERNAL':
        return 'INTERNAL_TCP_UDP'
    elif scheme == 'INTERNAL_MANAGED':
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
    if not target_url:
        return 'unknown'
    if 'targetHttpProxies' in target_url:
        return 'targetHttpProxies'
    elif 'targetHttpsProxies' in target_url:
        return 'targetHttpsProxies'
    elif 'targetTcpProxies' in target_url:
        return 'targetTcpProxies'
    elif 'targetSslProxies' in target_url:
        return 'targetSslProxies'
    elif 'targetPools' in target_url:
        return 'targetPools'
    elif 'targetInstances' in target_url:
        return 'targetInstances'
    elif 'targetGrpcProxies' in target_url:
        return 'targetGrpcProxies'
    elif 'backendServices' in target_url:
        return 'backendServices'
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
        log_info_non_console(f"Target HTTP Proxy {proxy_name} 조회 실패: {e}")
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
        log_info_non_console(f"Target HTTPS Proxy {proxy_name} 조회 실패: {e}")
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
        log_info_non_console(f"Target TCP Proxy {proxy_name} 조회 실패: {e}")
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
        log_info_non_console(f"Target SSL Proxy {proxy_name} 조회 실패: {e}")
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
        log_info_non_console(f"URL Map {url_map_name} 조회 실패: {e}")
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
            
        backend_groups = []
        if getattr(service, 'backends', None):
            for b in service.backends:
                grp = getattr(b, 'group', '')
                grp_name = grp.split('/')[-1] if grp else '-'
                backend_groups.append({
                    'group': grp_name,
                    'group_url': grp,
                    'balancing_mode': getattr(b, 'balancing_mode', ''),
                    'capacity_scaler': getattr(b, 'capacity_scaler', 1.0)
                })

        return {
            'name': service.name,
            'protocol': service.protocol,
            'port': service.port,
            'port_name': service.port_name,
            'timeout_sec': service.timeout_sec,
            'backends': len(service.backends) if service.backends else 0,
            'backend_groups': backend_groups,
            'health_checks': list(service.health_checks) if service.health_checks else [],
            'load_balancing_scheme': service.load_balancing_scheme,
            'session_affinity': service.session_affinity,
            'description': service.description or ''
        }
    except Exception as e:
        log_info_non_console(f"Backend Service {service_name} 조회 실패: {e}")
        return {}


def get_regional_backend_service_details(client, project_id: str, region: str, service_name: str) -> Dict:
    """Regional Backend Service 상세 정보를 가져옵니다."""
    try:
        service = client.get(project=project_id, region=region, backend_service=service_name)
        backend_groups = []
        if getattr(service, 'backends', None):
            for b in service.backends:
                grp = getattr(b, 'group', '')
                grp_name = grp.split('/')[-1] if grp else '-'
                backend_groups.append({
                    'group': grp_name,
                    'group_url': grp,
                    'balancing_mode': getattr(b, 'balancing_mode', ''),
                    'capacity_scaler': getattr(b, 'capacity_scaler', 1.0)
                })

        return {
            'name': service.name,
            'protocol': service.protocol,
            'port': service.port,
            'port_name': service.port_name,
            'timeout_sec': service.timeout_sec,
            'backends': len(service.backends) if service.backends else 0,
            'backend_groups': backend_groups,
            'health_checks': list(service.health_checks) if service.health_checks else [],
            'load_balancing_scheme': service.load_balancing_scheme,
            'session_affinity': service.session_affinity,
            'description': service.description or ''
        }
    except Exception as e:
        log_info_non_console(f"Regional Backend Service {service_name} 조회 실패: {e}")
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
        log_info_non_console(f"Health Check {hc_name} 조회 실패: {e}")
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


def fetch_load_balancers(project_id: str, region_filter: Optional[str] = None) -> List[Dict]:
    """
    GCP Load Balancer를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 리전 필터 (선택사항)
    
    Returns:
        Load Balancer 정보 리스트
    """
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


def format_table_output(load_balancers: List[Dict], verbose: bool = False) -> None:
    """
    GCP Load Balancer 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        load_balancers: Load Balancer 정보 리스트
        verbose: 상세 정보 (-v) 출력 여부
    """
    if not load_balancers:
        console.print("[yellow]표시할 GCP Load Balancer 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 스코프, 이름 순으로 정렬
    load_balancers.sort(key=lambda x: (x.get("project_id", ""), x.get("scope", ""), x.get("name", "")))

    if verbose:
        headers = [
            "Project", "Scope", "LB Name", "Type", "Scheme",
            "IP Address", "Port", "Backend / Pool",
            "Target (Instance)", "Health", "Health Check", "SSL Certs"
        ]
        table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
        table.show_edge = False

        table.add_column("Project", style="bold magenta")
        table.add_column("Scope", style="bold cyan")
        table.add_column("LB Name", style="bold white")
        table.add_column("Type", style="dim")
        table.add_column("Scheme", style="dim")
        table.add_column("IP Address", style="blue")
        table.add_column("Port", justify="center")
        table.add_column("Backend / Pool", style="cyan")
        table.add_column("Target (Instance)")
        table.add_column("Health", justify="center")
        table.add_column("Health Check", style="yellow")
        table.add_column("SSL Certs", style="red")

        last_project = None
        last_scope = None
        last_lb = None

        for i, lb in enumerate(load_balancers):
            project_changed = lb.get("project_id") != last_project
            scope_changed = lb.get("scope") != last_scope
            lb_changed = lb.get("name") != last_lb or project_changed or scope_changed

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

            pool_name = lb.get('target_pool', {}).get('name') or (
                lb.get('backend_services', [{}])[0].get('name') if lb.get('backend_services') else '-'
            )
            hc_names = [h.get('name', '') for h in lb.get('health_checks', []) if isinstance(h, dict)]
            hc_str = ", ".join(hc_names) if hc_names else "-"
            ssl_names = [c.get('name', str(c)) for c in lb.get('ssl_certificates', []) if isinstance(c, dict)]
            ssl_str = ", ".join(ssl_names) if ssl_names else "-"
            port_str = f"{lb.get('ip_protocol', 'TCP')}:{lb.get('port_range', '-')}"
            scheme_str = lb.get('load_balancing_scheme', '-')

            targets = lb.get('targets', [])
            if not targets:
                targets = [{'name': '(No Targets)', 'health': '-', 'pool': pool_name}]

            for t_idx, target in enumerate(targets):
                is_first_target = (t_idx == 0)
                if i > 0 and is_first_target:
                    if project_changed:
                        table.add_row(*[Rule(style="dim") for _ in headers])
                    elif scope_changed:
                        table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
                    elif lb_changed:
                        table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])

                h_raw = str(target.get('health', '-')).upper()
                if h_raw == 'HEALTHY':
                    h_colored = "[bold green]HEALTHY[/bold green]"
                elif h_raw in ('UNHEALTHY', 'DRAINING', 'DOWN'):
                    h_colored = f"[bold red]{h_raw}[/bold red]"
                elif h_raw == '-':
                    h_colored = "-"
                else:
                    h_colored = f"[bold yellow]{h_raw}[/bold yellow]"

                row_vals = [
                    lb.get("project_id", "") if (project_changed and is_first_target) else "",
                    lb.get("scope", "") if ((project_changed or scope_changed) and is_first_target) else "",
                    lb.get("name", "") if (lb_changed and is_first_target) else "",
                    type_colored if (lb_changed and is_first_target) else "",
                    scheme_str if (lb_changed and is_first_target) else "",
                    lb.get("ip_address", "-") if (lb_changed and is_first_target) else "",
                    port_str if (lb_changed and is_first_target) else "",
                    target.get('pool', pool_name) if is_first_target else "",
                    target.get('name', '-'),
                    h_colored,
                    hc_str if is_first_target else "",
                    ssl_str if is_first_target else "",
                ]
                table.add_row(*row_vals)

            last_project = lb.get("project_id")
            last_scope = lb.get("scope")
            last_lb = lb.get("name")

        console.print(table)
        return

    # 일반 모드 (Compact Table)
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
        
        # Backends 표시 (인스턴스 이름 또는 백엔드 서비스)
        targets = lb.get('targets', [])
        if targets:
            tgt_names = [t.get('name', '') for t in targets if t.get('name') and t.get('name') != '(No Targets)']
            if len(tgt_names) == 1:
                backend_info = tgt_names[0]
            elif 1 < len(tgt_names) <= 2:
                backend_info = ", ".join(tgt_names)
            elif len(tgt_names) > 2:
                backend_info = f"{tgt_names[0]} (+{len(tgt_names)-1})"
            else:
                backend_info = "-"
        elif lb.get('backend_services'):
            backend_count = len(lb.get('backend_services', []))
            backend_info = f"{backend_count} svc" if backend_count > 0 else "-"
        else:
            backend_info = "-"
        
        # Health Checks 표시
        hcs = lb.get('health_checks', [])
        if hcs:
            hc_names = [h.get('name', '') for h in hcs if isinstance(h, dict)]
            healthy_count = sum(1 for t in targets if str(t.get('health', '')).upper() == 'HEALTHY')
            total_targets = len([t for t in targets if t.get('name') != '(No Targets)'])
            if hc_names:
                if total_targets > 0:
                    hc_info = f"{hc_names[0]} ({healthy_count}/{total_targets})"
                else:
                    hc_info = hc_names[0]
            else:
                hc_info = f"{len(hcs)}"
        else:
            hc_info = "-"
        
        # SSL Certificates 표시
        ssl_certs = lb.get('ssl_certificates', [])
        if ssl_certs:
            ssl_names = [c.get('name', str(c)) for c in ssl_certs if isinstance(c, dict)]
            ssl_info = ssl_names[0] if len(ssl_names) == 1 else f"{len(ssl_certs)}"
        else:
            ssl_info = "-"
        
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
                        if isinstance(backend, dict):
                            backend_name = backend.get('name', 'N/A')
                            backend_protocol = backend.get('protocol', 'N/A')
                            backend_count = backend.get('backends', 0)
                            backends_node.add(
                                f"• {backend_name} ({backend_protocol}) - {backend_count} backends"
                            )
                        else:
                            backends_node.add(f"• {backend}")
                
                # Health Checks 정보
                health_checks = lb.get('health_checks', [])
                if health_checks:
                    hc_node = lb_node.add(f"❤️ Health Checks ({len(health_checks)})")
                    for hc in health_checks:
                        if isinstance(hc, dict):
                            hc_name = hc.get('name', 'N/A')
                            hc_type = hc.get('type', 'N/A')
                            hc_interval = hc.get('check_interval_sec', 'N/A')
                            hc_node.add(f"• {hc_name} ({hc_type}) - {hc_interval}s interval")
                        else:
                            hc_node.add(f"• {hc}")
                
                # SSL Certificates 정보
                ssl_certs = lb.get('ssl_certificates', [])
                if ssl_certs:
                    ssl_node = lb_node.add(f"🔐 SSL Certificates ({len(ssl_certs)})")
                    for cert in ssl_certs:
                        if isinstance(cert, dict):
                            cert_name = cert.get('name', 'N/A')
                            cert_type = cert.get('type', 'N/A')
                            ssl_node.add(f"• {cert_name} ({cert_type})")
                        else:
                            ssl_node.add(f"• {cert}")
                
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


def format_paste_output(lbs: List[Dict]) -> None:
    """로드 밸런서 목록을 -p (paste) 모드용 CSV로 출력합니다."""
    for lb in lbs:
        targets = lb.get('targets', [])
        targets_str = ";".join(t.get('name', '') for t in targets) if targets else '-'
        hcs = lb.get('health_checks', [])
        hc_str = ";".join(h.get('name', '') for h in hcs if isinstance(h, dict)) if hcs else '-'
        row = [
            lb.get('project_id', '-'),
            lb.get('scope', '-'),
            lb.get('name', '-'),
            lb.get('type', '-'),
            lb.get('ip_address', '-'),
            lb.get('ip_protocol', '-'),
            lb.get('port_range', '-'),
            targets_str,
            hc_str,
        ]
        print(",".join(str(c) for c in row))


class GcpLbInfoCommand(BaseCommand):
    """GCP Load Balancer 정보 조회 커맨드"""

    @classmethod
    def add_arguments(cls, parser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            '-a', '--account', '--project',
            dest='project',
            help='GCP 프로젝트 ID 또는 계정 (콤마 구분으로 복수 지정 가능, 예: my-project-123)'
        )
        parser.add_argument(
            '--all-projects',
            action='store_true',
            help='접근 가능한 모든 GCP 프로젝트 조회 (대규모 환경 주의)'
        )
        parser.add_argument(
            '-n', '--name', '--lb-name', 
            dest='lb_name',
            help='Load Balancer 이름으로 필터링 (콤마 구분 가능, 부분 일치)'
        )
        parser.add_argument(
            '-r', '--region', '--regions', 
            dest='region',
            help='리전으로 필터링 (예: us-central1, global)'
        )
        parser.add_argument(
            '-t', '--lb-type',
            choices=['HTTP_HTTPS', 'TCP_PROXY', 'SSL_PROXY', 'NETWORK_TCP_UDP', 'INTERNAL_TCP_UDP', 'INTERNAL_HTTP_HTTPS'],
            help='Load Balancer 타입으로 필터링'
        )
        parser.add_argument(
            '-p', '--paste',
            nargs='?',
            const=True,
            default=False,
            help='스프레드시트 복사용 콤마(,) 구분 텍스트 출력'
        )
        parser.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='상세 정보 출력'
        )
        parser.add_argument(
            '--mock',
            action='store_true',
            help='Mock 데이터를 사용하여 오프라인으로 실행'
        )

    def execute(self, args, config=None) -> CommandResult:
        if getattr(args, 'mock', False):
            lbs = load_mock_data()
            filtered = []
            name_filter = getattr(args, 'lb_name', None)
            proj_filter = getattr(args, 'project', None)
            region_filter = getattr(args, 'region', None)
            type_filter = getattr(args, 'lb_type', None)

            name_patterns = [p.strip().lower() for p in name_filter.split(',')] if name_filter else []
            proj_patterns = [p.strip().lower() for p in proj_filter.split(',')] if proj_filter else []

            for lb in lbs:
                lb_name = str(lb.get('name', '')).lower()
                lb_proj = str(lb.get('project_id', '')).lower()
                if name_patterns and not any(p in lb_name for p in name_patterns):
                    continue
                if proj_patterns and not any(p in lb_proj for p in proj_patterns):
                    continue
                if region_filter and region_filter.lower() not in str(lb.get('scope', '')).lower():
                    continue
                if type_filter and type_filter.upper() != str(lb.get('type', '')).upper():
                    continue
                filtered.append(lb)
            return CommandResult(
                data=filtered,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )

        if not GCP_LB_AVAILABLE:
            console.print("[red]❌ google-cloud-compute 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   pip install 'ic-cli[gcp]' 또는 pip install google-cloud-compute[/yellow]")
            console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
            return CommandResult(data=[], error="google-cloud-compute is not installed", success=False)

        try:
            log_info_non_console("GCP Load Balancer 조회 시작")
            auth_manager = GCPAuthManager()
            if not auth_manager.validate_credentials():
                console.print("[bold red]GCP 인증에 실패했습니다. 인증 정보를 확인해주세요.[/bold red]")
                console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
                return CommandResult(data=[], error="GCP authentication failed", success=False)

            project_manager = GCPProjectManager(auth_manager)
            resource_collector = GCPResourceCollector(auth_manager)

            if getattr(args, 'project', None):
                projects = [p.strip() for p in args.project.split(',') if p.strip()]
            else:
                projects = project_manager.get_projects(all_projects=getattr(args, 'all_projects', False))

            if not projects:
                console.print("[yellow]⚠️  GCP 프로젝트가 지정되지 않았습니다.[/yellow]")
                console.print("💡 [dim]-a/--project <PROJECT_ID> 옵션을 지정하거나 활성 gcloud 프로필을 설정하세요. (전체 조회를 원하시면 --all-projects 옵션을 사용하세요)[/dim]")
                return CommandResult(data=[], table_renderer=format_table_output, tree_renderer=format_tree_output, paste_renderer=format_paste_output)

            all_load_balancers = resource_collector.parallel_collect(
                projects, 
                fetch_load_balancers,
                getattr(args, 'region', None),
                progress_desc=f"Collecting GCP Load Balancers across {len(projects)} project(s)"
            )

            filters = {}
            if getattr(args, 'lb_name', None):
                filters['name'] = args.lb_name
            if getattr(args, 'project', None):
                filters['project'] = args.project
            if getattr(args, 'region', None):
                filters['scope'] = args.region
            if getattr(args, 'lb_type', None):
                filters['type'] = args.lb_type

            filtered_load_balancers = resource_collector.apply_filters(all_load_balancers, filters)
            return CommandResult(
                data=filtered_load_balancers,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )
        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpLbInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpLbInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Load Balancer 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)