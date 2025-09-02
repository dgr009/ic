#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
from google.cloud.container_v1 import ClusterManagerClient
from google.cloud.container_v1.types import ListClustersRequest, GetClusterRequest
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


def fetch_gke_clusters_via_mcp(mcp_connector, project_id: str, location_filter: str = None) -> List[Dict]:
    """
    MCP 서버를 통해 GCP GKE 클러스터를 가져옵니다.
    
    Args:
        mcp_connector: MCP GCP 커넥터
        project_id: GCP 프로젝트 ID
        location_filter: 위치 필터 (존 또는 지역, 선택사항)
    
    Returns:
        GKE 클러스터 정보 리스트
    """
    try:
        params = {
            'project_id': project_id,
            'location_filter': location_filter
        }
        
        response = mcp_connector.execute_gcp_query('gke', 'list_clusters', params)
        if response.success:
            return response.data.get('clusters', [])
        else:
            log_error(f"MCP GKE clusters query failed: {response.error}")
            return []
            
    except Exception as e:
        log_error(f"MCP GKE clusters fetch failed: {e}")
        return []


def fetch_gke_clusters_direct(project_id: str, location_filter: str = None) -> List[Dict]:
    """
    직접 API를 통해 GCP GKE 클러스터를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        location_filter: 위치 필터 (존 또는 지역, 선택사항)
    
    Returns:
        GKE 클러스터 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        cluster_client = ClusterManagerClient(credentials=credentials)
        
        all_clusters = []
        
        # 모든 위치에서 클러스터 조회 (location_filter가 없는 경우)
        if not location_filter:
            # 프로젝트의 모든 클러스터 가져오기 (모든 위치)
            parent = f"projects/{project_id}/locations/-"
        else:
            # 특정 위치의 클러스터만 가져오기
            parent = f"projects/{project_id}/locations/{location_filter}"
        
        try:
            request = ListClustersRequest(parent=parent)
            response = cluster_client.list_clusters(request=request)
            
            for cluster in response.clusters:
                cluster_data = collect_cluster_details(
                    cluster_client, project_id, cluster
                )
                if cluster_data:
                    all_clusters.append(cluster_data)
                    
        except gcp_exceptions.Forbidden:
            log_error(f"프로젝트 {project_id}에 대한 GKE 접근 권한이 없습니다")
            return []
        except Exception as e:
            log_error(f"GKE 클러스터 조회 실패: {project_id}, Error={e}")
            return []
        
        log_info(f"프로젝트 {project_id}에서 {len(all_clusters)}개 GKE 클러스터 발견")
        return all_clusters
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Container Engine 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"GKE 클러스터 조회 실패: {project_id}, Error={e}")
        return []


def fetch_gke_clusters(project_id: str, location_filter: str = None) -> List[Dict]:
    """
    GCP GKE 클러스터를 가져옵니다 (MCP 우선, 직접 API 폴백).
    
    Args:
        project_id: GCP 프로젝트 ID
        location_filter: 위치 필터 (존 또는 지역, 선택사항)
    
    Returns:
        GKE 클러스터 정보 리스트
    """
    # MCP 서비스 사용 시도
    if MCP_AVAILABLE:
        try:
            mcp_service = MCPGCPService('gke')
            return mcp_service.execute_with_fallback(
                'list_clusters',
                {'project_id': project_id, 'location_filter': location_filter},
                lambda project_id, location_filter: fetch_gke_clusters_direct(project_id, location_filter)
            )
        except Exception as e:
            log_error(f"MCP service failed, using direct API: {e}")
    
    # 직접 API 사용
    return fetch_gke_clusters_direct(project_id, location_filter)


def collect_cluster_details(cluster_client: ClusterManagerClient, 
                          project_id: str, cluster) -> Optional[Dict]:
    """
    클러스터의 상세 정보를 수집합니다.
    
    Args:
        cluster_client: Container 클러스터 클라이언트
        project_id: GCP 프로젝트 ID
        cluster: 클러스터 객체
    
    Returns:
        클러스터 상세 정보 딕셔너리
    """
    try:
        # 기본 클러스터 정보
        cluster_data = {
            'project_id': project_id,
            'name': cluster.name,
            'location': cluster.location,
            'location_type': cluster.location_type.name if hasattr(cluster, 'location_type') else 'UNKNOWN',
            'status': cluster.status.name if hasattr(cluster, 'status') else 'UNKNOWN',
            'description': cluster.description or '',
            'initial_cluster_version': cluster.initial_cluster_version,
            'current_master_version': cluster.current_master_version,
            'current_node_version': cluster.current_node_version,
            'create_time': cluster.create_time,
            'endpoint': cluster.endpoint,
            'initial_node_count': cluster.initial_node_count,
            'current_node_count': cluster.current_node_count,
            'labels': get_gcp_resource_labels(cluster),
            'node_pools': [],
            'addons_config': {},
            'network_config': {},
            'master_auth': {},
            'logging_config': {},
            'monitoring_config': {},
            'maintenance_policy': {},
            'autopilot': {}
        }
        
        # 네트워크 구성 정보
        if hasattr(cluster, 'network_config') and cluster.network_config:
            network_config = cluster.network_config
            cluster_data['network_config'] = {
                'network': network_config.network if hasattr(network_config, 'network') else '',
                'subnetwork': network_config.subnetwork if hasattr(network_config, 'subnetwork') else '',
                'enable_intra_node_visibility': getattr(network_config, 'enable_intra_node_visibility', False),
                'default_snat_status': getattr(network_config, 'default_snat_status', {}),
                'enable_l4_ilb_subsetting': getattr(network_config, 'enable_l4_ilb_subsetting', False)
            }
        
        # 기본 네트워크 정보 (legacy)
        if hasattr(cluster, 'network') and cluster.network:
            cluster_data['network'] = cluster.network
        if hasattr(cluster, 'subnetwork') and cluster.subnetwork:
            cluster_data['subnetwork'] = cluster.subnetwork
        if hasattr(cluster, 'cluster_ipv4_cidr') and cluster.cluster_ipv4_cidr:
            cluster_data['cluster_ipv4_cidr'] = cluster.cluster_ipv4_cidr
        if hasattr(cluster, 'services_ipv4_cidr') and cluster.services_ipv4_cidr:
            cluster_data['services_ipv4_cidr'] = cluster.services_ipv4_cidr
        
        # 노드 풀 정보 수집
        if hasattr(cluster, 'node_pools') and cluster.node_pools:
            cluster_data['node_pools'] = get_node_pool_details(cluster.node_pools)
        
        # 애드온 구성 정보
        if hasattr(cluster, 'addons_config') and cluster.addons_config:
            addons = cluster.addons_config
            cluster_data['addons_config'] = {
                'http_load_balancing': getattr(addons.http_load_balancing, 'disabled', True) if hasattr(addons, 'http_load_balancing') else True,
                'horizontal_pod_autoscaling': getattr(addons.horizontal_pod_autoscaling, 'disabled', True) if hasattr(addons, 'horizontal_pod_autoscaling') else True,
                'kubernetes_dashboard': getattr(addons.kubernetes_dashboard, 'disabled', True) if hasattr(addons, 'kubernetes_dashboard') else True,
                'network_policy_config': getattr(addons.network_policy_config, 'disabled', True) if hasattr(addons, 'network_policy_config') else True,
                'istio_config': getattr(addons.istio_config, 'disabled', True) if hasattr(addons, 'istio_config') else True,
                'cloud_run_config': getattr(addons.cloud_run_config, 'disabled', True) if hasattr(addons, 'cloud_run_config') else True
            }
        
        # 마스터 인증 정보
        if hasattr(cluster, 'master_auth') and cluster.master_auth:
            master_auth = cluster.master_auth
            cluster_data['master_auth'] = {
                'username': getattr(master_auth, 'username', ''),
                'client_certificate_config': getattr(master_auth, 'client_certificate_config', {}),
                'cluster_ca_certificate': bool(getattr(master_auth, 'cluster_ca_certificate', ''))
            }
        
        # 로깅 구성
        if hasattr(cluster, 'logging_config') and cluster.logging_config:
            logging_config = cluster.logging_config
            cluster_data['logging_config'] = {
                'component_config': getattr(logging_config, 'component_config', {})
            }
        elif hasattr(cluster, 'logging_service') and cluster.logging_service:
            cluster_data['logging_service'] = cluster.logging_service
        
        # 모니터링 구성
        if hasattr(cluster, 'monitoring_config') and cluster.monitoring_config:
            monitoring_config = cluster.monitoring_config
            cluster_data['monitoring_config'] = {
                'component_config': getattr(monitoring_config, 'component_config', {})
            }
        elif hasattr(cluster, 'monitoring_service') and cluster.monitoring_service:
            cluster_data['monitoring_service'] = cluster.monitoring_service
        
        # 유지보수 정책
        if hasattr(cluster, 'maintenance_policy') and cluster.maintenance_policy:
            maintenance_policy = cluster.maintenance_policy
            cluster_data['maintenance_policy'] = {
                'window': getattr(maintenance_policy, 'window', {}),
                'resource_version': getattr(maintenance_policy, 'resource_version', '')
            }
        
        # Autopilot 정보
        if hasattr(cluster, 'autopilot') and cluster.autopilot:
            autopilot = cluster.autopilot
            cluster_data['autopilot'] = {
                'enabled': getattr(autopilot, 'enabled', False)
            }
        
        # 보안 관련 정보
        if hasattr(cluster, 'master_authorized_networks_config'):
            cluster_data['master_authorized_networks_enabled'] = bool(cluster.master_authorized_networks_config)
        
        if hasattr(cluster, 'private_cluster_config'):
            cluster_data['private_cluster'] = bool(cluster.private_cluster_config)
        
        if hasattr(cluster, 'ip_allocation_policy'):
            cluster_data['ip_alias_enabled'] = bool(cluster.ip_allocation_policy)
        
        # 통계 정보 추가
        cluster_data['node_pools_count'] = len(cluster_data['node_pools'])
        cluster_data['total_nodes'] = sum(pool.get('node_count', 0) for pool in cluster_data['node_pools'])
        
        return cluster_data
        
    except Exception as e:
        log_error(f"클러스터 상세 정보 수집 실패: {cluster.name}, Error={e}")
        return None


def get_node_pool_details(node_pools) -> List[Dict]:
    """
    노드 풀의 상세 정보를 수집합니다.
    
    Args:
        node_pools: 노드 풀 리스트
    
    Returns:
        노드 풀 상세 정보 리스트
    """
    node_pool_details = []
    
    try:
        for pool in node_pools:
            pool_info = {
                'name': pool.name,
                'status': pool.status.name if hasattr(pool, 'status') else 'UNKNOWN',
                'initial_node_count': pool.initial_node_count,
                'node_count': getattr(pool, 'node_count', pool.initial_node_count),
                'version': pool.version,
                'config': {},
                'autoscaling': {},
                'management': {},
                'max_pods_constraint': {},
                'conditions': [],
                'locations': []
            }
            
            # 노드 구성 정보
            if hasattr(pool, 'config') and pool.config:
                config = pool.config
                pool_info['config'] = {
                    'machine_type': getattr(config, 'machine_type', ''),
                    'disk_size_gb': getattr(config, 'disk_size_gb', 0),
                    'disk_type': getattr(config, 'disk_type', ''),
                    'image_type': getattr(config, 'image_type', ''),
                    'labels': dict(getattr(config, 'labels', {})),
                    'tags': list(getattr(config, 'tags', [])),
                    'preemptible': getattr(config, 'preemptible', False),
                    'spot': getattr(config, 'spot', False),
                    'oauth_scopes': list(getattr(config, 'oauth_scopes', [])),
                    'service_account': getattr(config, 'service_account', ''),
                    'metadata': dict(getattr(config, 'metadata', {})),
                    'local_ssd_count': getattr(config, 'local_ssd_count', 0),
                    'boot_disk_kms_key': getattr(config, 'boot_disk_kms_key', ''),
                    'min_cpu_platform': getattr(config, 'min_cpu_platform', '')
                }
                
                # 타인트 정보
                if hasattr(config, 'taints') and config.taints:
                    pool_info['config']['taints'] = []
                    for taint in config.taints:
                        pool_info['config']['taints'].append({
                            'key': getattr(taint, 'key', ''),
                            'value': getattr(taint, 'value', ''),
                            'effect': getattr(taint, 'effect', '')
                        })
                
                # 샌드박스 구성
                if hasattr(config, 'sandbox_config') and config.sandbox_config:
                    pool_info['config']['sandbox_config'] = {
                        'type': getattr(config.sandbox_config, 'type', '')
                    }
                
                # 노드 그룹 정보
                if hasattr(config, 'node_group') and config.node_group:
                    pool_info['config']['node_group'] = getattr(config, 'node_group', '')
                
                # 리소스 라벨
                if hasattr(config, 'resource_labels') and config.resource_labels:
                    pool_info['config']['resource_labels'] = dict(config.resource_labels)
            
            # 자동 스케일링 정보
            if hasattr(pool, 'autoscaling') and pool.autoscaling:
                autoscaling = pool.autoscaling
                pool_info['autoscaling'] = {
                    'enabled': getattr(autoscaling, 'enabled', False),
                    'min_node_count': getattr(autoscaling, 'min_node_count', 0),
                    'max_node_count': getattr(autoscaling, 'max_node_count', 0),
                    'total_min_node_count': getattr(autoscaling, 'total_min_node_count', 0),
                    'total_max_node_count': getattr(autoscaling, 'total_max_node_count', 0),
                    'location_policy': getattr(autoscaling, 'location_policy', '')
                }
            
            # 관리 정보
            if hasattr(pool, 'management') and pool.management:
                management = pool.management
                pool_info['management'] = {
                    'auto_upgrade': getattr(management, 'auto_upgrade', False),
                    'auto_repair': getattr(management, 'auto_repair', False),
                    'upgrade_options': getattr(management, 'upgrade_options', {})
                }
            
            # 최대 파드 제약
            if hasattr(pool, 'max_pods_constraint') and pool.max_pods_constraint:
                max_pods = pool.max_pods_constraint
                pool_info['max_pods_constraint'] = {
                    'max_pods_per_node': getattr(max_pods, 'max_pods_per_node', 0)
                }
            
            # 조건 정보
            if hasattr(pool, 'conditions') and pool.conditions:
                for condition in pool.conditions:
                    pool_info['conditions'].append({
                        'code': getattr(condition, 'code', ''),
                        'message': getattr(condition, 'message', ''),
                        'canonical_code': getattr(condition, 'canonical_code', '')
                    })
            
            # 위치 정보
            if hasattr(pool, 'locations') and pool.locations:
                pool_info['locations'] = list(pool.locations)
            
            node_pool_details.append(pool_info)
    
    except Exception as e:
        log_error(f"노드 풀 상세 정보 수집 실패: Error={e}")
    
    return node_pool_details


def load_mock_data():
    """Mock 데이터를 로드합니다."""
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


def format_table_output(clusters: List[Dict]) -> None:
    """
    GCP GKE 클러스터 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        clusters: GKE 클러스터 정보 리스트
    """
    if not clusters:
        console.print("[yellow]표시할 GCP GKE 클러스터 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 위치, 클러스터 이름 순으로 정렬
    clusters.sort(key=lambda x: (x.get("project_id", ""), x.get("location", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Location", style="bold cyan")
    table.add_column("Cluster Name", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Version", style="dim")
    table.add_column("Node Pools", justify="center", style="blue")
    table.add_column("Total Nodes", justify="center", style="green")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Autopilot", justify="center", style="yellow")
    table.add_column("Labels", style="dim")

    last_project = None
    last_location = None
    
    for i, cluster in enumerate(clusters):
        project_changed = cluster.get("project_id") != last_project
        location_changed = cluster.get("location") != last_location

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", "", end_section=True)

        # 상태에 따른 색상 적용
        status = cluster.get('status', 'UNKNOWN')
        if status == "RUNNING":
            status_colored = f"[green]{status}[/green]"
        elif status == "ERROR":
            status_colored = f"[red]{status}[/red]"
        elif status == "PROVISIONING":
            status_colored = f"[yellow]{status}[/yellow]"
        elif status == "STOPPING":
            status_colored = f"[orange1]{status}[/orange1]"
        else:
            status_colored = f"[dim]{status}[/dim]"
        
        # 버전 정보
        master_version = cluster.get('current_master_version', 'N/A')
        if master_version != 'N/A':
            # 버전에서 주요 부분만 표시 (예: 1.27.3-gke.100 -> 1.27.3)
            version_parts = master_version.split('-')
            version_display = version_parts[0] if version_parts else master_version
        else:
            version_display = master_version
        
        # 노드 풀 및 노드 수
        node_pools_count = cluster.get('node_pools_count', 0)
        total_nodes = cluster.get('total_nodes', 0)
        
        # 엔드포인트 (IP만 표시)
        endpoint = cluster.get('endpoint', 'N/A')
        if endpoint and endpoint != 'N/A':
            # HTTPS URL에서 IP만 추출
            if endpoint.startswith('https://'):
                endpoint = endpoint.replace('https://', '')
        
        # Autopilot 여부
        autopilot_enabled = cluster.get('autopilot', {}).get('enabled', False)
        autopilot_display = "✓" if autopilot_enabled else "-"
        
        # 라벨 정보 (최대 2개만 표시)
        labels = cluster.get('labels', {})
        if labels:
            label_items = list(labels.items())[:2]
            label_text = ", ".join([f"{k}={v}" for k, v in label_items])
            if len(labels) > 2:
                label_text += f" (+{len(labels)-2})"
        else:
            label_text = "-"
        
        display_values = [
            cluster.get("project_id", "") if project_changed else "",
            cluster.get("location", "") if project_changed or location_changed else "",
            cluster.get("name", "N/A"),
            status_colored,
            version_display,
            str(node_pools_count) if node_pools_count > 0 else "-",
            str(total_nodes) if total_nodes > 0 else "-",
            endpoint,
            autopilot_display,
            label_text
        ]
        
        table.add_row(*display_values)

        last_project = cluster.get("project_id")
        last_location = cluster.get("location")
    
    console.print(table)


def format_tree_output(clusters: List[Dict]) -> None:
    """
    GCP GKE 클러스터 목록을 트리 형식으로 출력합니다 (프로젝트/위치/클러스터 계층).
    
    Args:
        clusters: GKE 클러스터 정보 리스트
    """
    if not clusters:
        console.print("[yellow]표시할 GCP GKE 클러스터 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for cluster in clusters:
        project_id = cluster.get("project_id", "unknown")
        location = cluster.get("location", "unknown")
        
        if project_id not in projects:
            projects[project_id] = {}
        if location not in projects[project_id]:
            projects[project_id][location] = []
        
        projects[project_id][location].append(cluster)

    # 트리 구조 생성
    tree = Tree("🚢 [bold blue]GCP GKE Clusters[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        
        for location in sorted(projects[project_id].keys()):
            location_clusters = projects[project_id][location]
            location_node = project_node.add(
                f"🌍 [bold cyan]{location}[/bold cyan] ({len(location_clusters)} clusters)"
            )
            
            for cluster in sorted(location_clusters, key=lambda x: x.get("name", "")):
                # 상태 아이콘
                status = cluster.get('status', 'UNKNOWN')
                if status == "RUNNING":
                    status_icon = "🟢"
                elif status == "ERROR":
                    status_icon = "🔴"
                elif status == "PROVISIONING":
                    status_icon = "🟡"
                elif status == "STOPPING":
                    status_icon = "🟠"
                else:
                    status_icon = "⚪"
                
                # Autopilot 아이콘
                autopilot_enabled = cluster.get('autopilot', {}).get('enabled', False)
                autopilot_icon = "🤖" if autopilot_enabled else "⚙️"
                
                # 클러스터 정보
                cluster_name = cluster.get("name", "N/A")
                master_version = cluster.get("current_master_version", "N/A")
                node_pools_count = cluster.get("node_pools_count", 0)
                total_nodes = cluster.get("total_nodes", 0)
                
                # 버전 단순화
                if master_version != "N/A":
                    version_parts = master_version.split('-')
                    version_display = version_parts[0] if version_parts else master_version
                else:
                    version_display = master_version
                
                cluster_info = (
                    f"{status_icon} {autopilot_icon} [bold white]{cluster_name}[/bold white] "
                    f"(v{version_display}) - "
                    f"Pools: [blue]{node_pools_count}[/blue], "
                    f"Nodes: [green]{total_nodes}[/green]"
                )
                
                cluster_node = location_node.add(cluster_info)
                
                # 네트워크 정보
                network = cluster.get('network', cluster.get('network_config', {}).get('network', ''))
                subnetwork = cluster.get('subnetwork', cluster.get('network_config', {}).get('subnetwork', ''))
                if network or subnetwork:
                    network_info = f"🔗 Network: {network.split('/')[-1] if network else 'default'}"
                    if subnetwork:
                        network_info += f", Subnet: {subnetwork.split('/')[-1]}"
                    cluster_node.add(network_info)
                
                # 노드 풀 상세 정보
                if cluster.get('node_pools'):
                    pools_node = cluster_node.add(f"🔧 [bold blue]Node Pools ({len(cluster['node_pools'])})[/bold blue]")
                    for pool in cluster['node_pools'][:3]:  # 최대 3개만 표시
                        pool_name = pool.get('name', 'N/A')
                        machine_type = pool.get('config', {}).get('machine_type', 'N/A')
                        node_count = pool.get('node_count', 0)
                        preemptible = pool.get('config', {}).get('preemptible', False)
                        spot = pool.get('config', {}).get('spot', False)
                        
                        pool_type = ""
                        if spot:
                            pool_type = " (Spot)"
                        elif preemptible:
                            pool_type = " (Preemptible)"
                        
                        pool_info = (
                            f"💻 {pool_name} - "
                            f"{machine_type}{pool_type} "
                            f"({node_count} nodes)"
                        )
                        pools_node.add(pool_info)
                        
                        # 자동 스케일링 정보
                        autoscaling = pool.get('autoscaling', {})
                        if autoscaling.get('enabled'):
                            min_nodes = autoscaling.get('min_node_count', 0)
                            max_nodes = autoscaling.get('max_node_count', 0)
                            pools_node.add(f"📈 Autoscaling: {min_nodes}-{max_nodes} nodes")
                    
                    if len(cluster['node_pools']) > 3:
                        pools_node.add(f"... and {len(cluster['node_pools']) - 3} more pools")
                
                # 애드온 정보
                addons = cluster.get('addons_config', {})
                enabled_addons = []
                if not addons.get('http_load_balancing', True):
                    enabled_addons.append("HTTP LB")
                if not addons.get('horizontal_pod_autoscaling', True):
                    enabled_addons.append("HPA")
                if not addons.get('network_policy_config', True):
                    enabled_addons.append("Network Policy")
                if not addons.get('istio_config', True):
                    enabled_addons.append("Istio")
                if not addons.get('cloud_run_config', True):
                    enabled_addons.append("Cloud Run")
                
                if enabled_addons:
                    cluster_node.add(f"🔌 Addons: {', '.join(enabled_addons)}")
                
                # 라벨 정보
                if cluster.get('labels'):
                    labels_text = ", ".join([f"{k}={v}" for k, v in cluster['labels'].items()])
                    cluster_node.add(f"🏷️  Labels: {labels_text}")

    console.print(tree)


def format_output(clusters: List[Dict], output_format: str = 'table') -> str:
    """
    GKE 클러스터 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        clusters: GKE 클러스터 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(clusters)
        return ""
    elif output_format == 'tree':
        format_tree_output(clusters)
        return ""
    elif output_format == 'json':
        return format_gcp_output(clusters, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(clusters, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(clusters)
        return ""


def print_cluster_table(clusters):
    """GCP GKE 클러스터 목록을 계층적 테이블로 출력합니다. (하위 호환성을 위한 래퍼)"""
    format_table_output(clusters)


def main(args):
    """
    메인 함수 - GCP GKE 클러스터 정보를 조회하고 출력합니다.
    
    Args:
        args: CLI 인자 객체
    """
    try:
        log_info("GCP GKE 클러스터 조회 시작")
        
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
        
        # 병렬로 GKE 클러스터 수집
        all_clusters = resource_collector.parallel_collect(
            projects, 
            fetch_gke_clusters,
            args.location if hasattr(args, 'location') else None
        )
        
        if not all_clusters:
            console.print("[yellow]조회된 GKE 클러스터가 없습니다.[/yellow]")
            return
        
        # 필터 적용
        filters = {}
        if hasattr(args, 'cluster') and args.cluster:
            filters['name'] = args.cluster
        if hasattr(args, 'project') and args.project:
            filters['project'] = args.project
        if hasattr(args, 'location') and args.location:
            filters['zone'] = args.location  # location을 zone 필터로 사용
        
        filtered_clusters = resource_collector.apply_filters(all_clusters, filters)
        
        # 출력 형식 결정
        output_format = getattr(args, 'output', 'table')
        
        # 결과 출력
        if output_format in ['json', 'yaml']:
            output_text = format_output(filtered_clusters, output_format)
            console.print(output_text)
        else:
            format_output(filtered_clusters, output_format)
        
        log_info(f"총 {len(filtered_clusters)}개 GKE 클러스터 조회 완료")
        
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
        '-c', '--cluster', 
        help='클러스터 이름으로 필터링 (부분 일치)'
    )
    parser.add_argument(
        '-l', '--location', 
        help='위치로 필터링 (존 또는 지역, 예: us-central1-a 또는 us-central1)'
    )
    parser.add_argument(
        '-o', '--output', 
        choices=['table', 'tree', 'json', 'yaml'],
        default='table',
        help='출력 형식 선택 (기본값: table)'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP GKE 클러스터 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)