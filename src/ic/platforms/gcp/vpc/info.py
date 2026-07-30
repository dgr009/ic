#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
from google.cloud.compute_v1 import NetworksClient, SubnetworksClient, FirewallsClient, RegionsClient
from google.cloud.compute_v1.types import (
    ListNetworksRequest, ListSubnetworksRequest, ListFirewallsRequest, 
    ListRegionsRequest, GetNetworkRequest, GetSubnetworkRequest
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


def fetch_vpc_networks_via_mcp(mcp_connector, project_id: str, region_filter: str = None) -> List[Dict]:
    """
    MCP 서버를 통해 GCP VPC 네트워크를 가져옵니다.
    
    Args:
        mcp_connector: MCP GCP 커넥터
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        VPC 네트워크 정보 리스트
    """
    try:
        params = {
            'project_id': project_id,
            'region_filter': region_filter
        }
        
        response = mcp_connector.execute_gcp_query('vpc', 'list_networks', params)
        if response.success:
            return response.data.get('networks', [])
        else:
            log_error(f"MCP VPC networks query failed: {response.error}")
            return []
            
    except Exception as e:
        log_error(f"MCP VPC networks fetch failed: {e}")
        return []


def fetch_vpc_networks_direct(project_id: str, region_filter: str = None) -> List[Dict]:
    """
    직접 API를 통해 GCP VPC 네트워크를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        VPC 네트워크 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        networks_client = NetworksClient(credentials=credentials)
        subnets_client = SubnetworksClient(credentials=credentials)
        firewalls_client = FirewallsClient(credentials=credentials)
        regions_client = RegionsClient(credentials=credentials)
        
        # 프로젝트의 모든 네트워크 가져오기
        networks_request = ListNetworksRequest(project=project_id)
        networks = networks_client.list(request=networks_request)
        
        all_networks = []
        
        for network in networks:
            try:
                network_data = collect_network_details(
                    networks_client, subnets_client, firewalls_client, regions_client,
                    project_id, network, region_filter
                )
                if network_data:
                    all_networks.append(network_data)
                    
            except gcp_exceptions.Forbidden:
                log_error(f"네트워크 {network.name}에 대한 접근 권한이 없습니다: {project_id}")
                continue
            except Exception as e:
                log_error(f"네트워크 {network.name} 조회 실패: {project_id}, Error={e}")
                continue
        
        log_info(f"프로젝트 {project_id}에서 {len(all_networks)}개 VPC 네트워크 발견")
        return all_networks
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Compute Engine 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"VPC 네트워크 조회 실패: {project_id}, Error={e}")
        return []


def fetch_vpc_networks(project_id: str, region_filter: str = None) -> List[Dict]:
    """
    GCP VPC 네트워크를 가져옵니다 (MCP 우선, 직접 API 폴백).
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        VPC 네트워크 정보 리스트
    """
    # MCP 서비스 사용 시도
    if MCP_AVAILABLE:
        try:
            mcp_service = MCPGCPService('vpc')
            return mcp_service.execute_with_fallback(
                'list_networks',
                {'project_id': project_id, 'region_filter': region_filter},
                lambda project_id, region_filter: fetch_vpc_networks_direct(project_id, region_filter)
            )
        except Exception as e:
            log_error(f"MCP service failed, using direct API: {e}")
    
    # 직접 API 사용
    return fetch_vpc_networks_direct(project_id, region_filter)


def collect_network_details(networks_client: NetworksClient, subnets_client: SubnetworksClient,
                          firewalls_client: FirewallsClient, regions_client: RegionsClient,
                          project_id: str, network, region_filter: str = None) -> Optional[Dict]:
    """
    네트워크의 상세 정보를 수집합니다.
    
    Args:
        networks_client: Networks 클라이언트
        subnets_client: Subnetworks 클라이언트
        firewalls_client: Firewalls 클라이언트
        regions_client: Regions 클라이언트
        project_id: GCP 프로젝트 ID
        network: 네트워크 객체
        region_filter: 지역 필터
    
    Returns:
        네트워크 상세 정보 딕셔너리
    """
    try:
        # 기본 네트워크 정보
        network_data = {
            'project_id': project_id,
            'name': network.name,
            'description': network.description or '',
            'creation_timestamp': network.creation_timestamp,
            'self_link': network.self_link,
            'auto_create_subnetworks': network.auto_create_subnetworks,
            'routing_mode': network.routing_config.routing_mode if hasattr(network, 'routing_config') and network.routing_config else 'REGIONAL',
            'mtu': network.mtu if hasattr(network, 'mtu') else 1460,
            'labels': get_gcp_resource_labels(network),
            'subnets': [],
            'firewall_rules': [],
            'peerings': [],
            'routes': []
        }
        
        # IPv4 범위 정보 (legacy 네트워크의 경우)
        if hasattr(network, 'i_pv4_range') and network.i_pv4_range:
            network_data['ipv4_range'] = network.i_pv4_range
        
        # 서브넷 정보 수집
        network_data['subnets'] = get_subnet_details(
            subnets_client, regions_client, project_id, network.name, region_filter
        )
        
        # 방화벽 규칙 수집
        network_data['firewall_rules'] = get_firewall_rules(
            firewalls_client, project_id, network.name
        )
        
        # 피어링 연결 정보 수집
        if hasattr(network, 'peerings') and network.peerings:
            for peering in network.peerings:
                peering_info = {
                    'name': peering.name,
                    'network': peering.network,
                    'state': peering.state,
                    'auto_create_routes': peering.auto_create_routes,
                    'exchange_subnet_routes': peering.exchange_subnet_routes
                }
                network_data['peerings'].append(peering_info)
        
        # 통계 정보 추가
        network_data['subnet_count'] = len(network_data['subnets'])
        network_data['firewall_rules_count'] = len(network_data['firewall_rules'])
        network_data['peerings_count'] = len(network_data['peerings'])
        
        return network_data
        
    except Exception as e:
        log_error(f"네트워크 상세 정보 수집 실패: {network.name}, Error={e}")
        return None


def get_subnet_details(subnets_client: SubnetworksClient, regions_client: RegionsClient,
                      project_id: str, network_name: str, region_filter: str = None) -> List[Dict]:
    """
    네트워크의 서브넷 정보를 가져옵니다.
    
    Args:
        subnets_client: Subnetworks 클라이언트
        regions_client: Regions 클라이언트
        project_id: GCP 프로젝트 ID
        network_name: 네트워크 이름
        region_filter: 지역 필터
    
    Returns:
        서브넷 정보 리스트
    """
    subnets = []
    
    try:
        # 모든 지역 가져오기
        regions_request = ListRegionsRequest(project=project_id)
        regions = regions_client.list(request=regions_request)
        
        for region in regions:
            # 지역 필터 적용
            if region_filter and region_filter not in region.name:
                continue
            
            try:
                # 해당 지역의 서브넷 가져오기
                subnets_request = ListSubnetworksRequest(
                    project=project_id,
                    region=region.name
                )
                
                region_subnets = subnets_client.list(request=subnets_request)
                
                for subnet in region_subnets:
                    # 해당 네트워크의 서브넷만 필터링
                    if subnet.network.endswith(f'/networks/{network_name}'):
                        subnet_info = {
                            'name': subnet.name,
                            'region': region.name,
                            'ip_cidr_range': subnet.ip_cidr_range,
                            'gateway_address': subnet.gateway_address,
                            'description': subnet.description or '',
                            'creation_timestamp': subnet.creation_timestamp,
                            'private_ip_google_access': subnet.private_ip_google_access,
                            'enable_flow_logs': subnet.enable_flow_logs if hasattr(subnet, 'enable_flow_logs') else False,
                            'purpose': subnet.purpose if hasattr(subnet, 'purpose') else 'PRIVATE',
                            'role': subnet.role if hasattr(subnet, 'role') else None,
                            'labels': get_gcp_resource_labels(subnet)
                        }
                        
                        # 보조 IP 범위 정보
                        if hasattr(subnet, 'secondary_ip_ranges') and subnet.secondary_ip_ranges:
                            subnet_info['secondary_ip_ranges'] = []
                            for secondary_range in subnet.secondary_ip_ranges:
                                subnet_info['secondary_ip_ranges'].append({
                                    'range_name': secondary_range.range_name,
                                    'ip_cidr_range': secondary_range.ip_cidr_range
                                })
                        
                        subnets.append(subnet_info)
                        
            except gcp_exceptions.Forbidden:
                log_error(f"지역 {region.name}에 대한 접근 권한이 없습니다: {project_id}")
                continue
            except Exception as e:
                log_error(f"지역 {region.name}에서 서브넷 조회 실패: {project_id}, Error={e}")
                continue
    
    except Exception as e:
        log_error(f"서브넷 정보 수집 실패: {network_name}, Error={e}")
    
    return subnets


def get_firewall_rules(firewalls_client: FirewallsClient, project_id: str, network_name: str) -> List[Dict]:
    """
    네트워크의 방화벽 규칙을 가져옵니다.
    
    Args:
        firewalls_client: Firewalls 클라이언트
        project_id: GCP 프로젝트 ID
        network_name: 네트워크 이름
    
    Returns:
        방화벽 규칙 정보 리스트
    """
    firewall_rules = []
    
    try:
        # 모든 방화벽 규칙 가져오기
        firewalls_request = ListFirewallsRequest(project=project_id)
        firewalls = firewalls_client.list(request=firewalls_request)
        
        for firewall in firewalls:
            # 해당 네트워크의 방화벽 규칙만 필터링
            if firewall.network.endswith(f'/networks/{network_name}'):
                firewall_info = {
                    'name': firewall.name,
                    'description': firewall.description or '',
                    'direction': firewall.direction,
                    'priority': firewall.priority,
                    'action': 'ALLOW' if firewall.allowed else 'DENY',
                    'disabled': firewall.disabled if hasattr(firewall, 'disabled') else False,
                    'creation_timestamp': firewall.creation_timestamp,
                    'labels': get_gcp_resource_labels(firewall),
                    'source_ranges': list(firewall.source_ranges) if firewall.source_ranges else [],
                    'destination_ranges': list(firewall.destination_ranges) if firewall.destination_ranges else [],
                    'source_tags': list(firewall.source_tags) if firewall.source_tags else [],
                    'target_tags': list(firewall.target_tags) if firewall.target_tags else [],
                    'source_service_accounts': list(firewall.source_service_accounts) if firewall.source_service_accounts else [],
                    'target_service_accounts': list(firewall.target_service_accounts) if firewall.target_service_accounts else [],
                    'allowed_rules': [],
                    'denied_rules': []
                }
                
                # 허용 규칙
                if firewall.allowed:
                    for rule in firewall.allowed:
                        rule_info = {
                            'ip_protocol': rule.i_p_protocol,
                            'ports': list(rule.ports) if rule.ports else []
                        }
                        firewall_info['allowed_rules'].append(rule_info)
                
                # 거부 규칙
                if firewall.denied:
                    for rule in firewall.denied:
                        rule_info = {
                            'ip_protocol': rule.i_p_protocol,
                            'ports': list(rule.ports) if rule.ports else []
                        }
                        firewall_info['denied_rules'].append(rule_info)
                
                firewall_rules.append(firewall_info)
    
    except Exception as e:
        log_error(f"방화벽 규칙 수집 실패: {network_name}, Error={e}")
    
    return firewall_rules


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


def format_table_output(networks: List[Dict]) -> None:
    """
    GCP VPC 네트워크 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        networks: VPC 네트워크 정보 리스트
    """
    if not networks:
        console.print("[yellow]표시할 GCP VPC 네트워크 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 네트워크 이름 순으로 정렬
    networks.sort(key=lambda x: (x.get("project_id", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Network Name", style="bold white")
    table.add_column("Mode", justify="center")
    table.add_column("Routing", justify="center", style="dim")
    table.add_column("Subnets", justify="center", style="blue")
    table.add_column("Firewall Rules", justify="center", style="red")
    table.add_column("Peerings", justify="center", style="green")
    table.add_column("IPv4 Range", style="cyan")
    table.add_column("Labels", style="dim")

    last_project = None
    
    for i, network in enumerate(networks):
        project_changed = network.get("project_id") != last_project

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", end_section=True)

        # 네트워크 모드 결정
        if network.get('auto_create_subnetworks'):
            network_mode = "[yellow]Auto[/yellow]"
        elif network.get('ipv4_range'):
            network_mode = "[red]Legacy[/red]"
        else:
            network_mode = "[green]Custom[/green]"
        
        # 라우팅 모드
        routing_mode = network.get('routing_mode', 'REGIONAL')
        if routing_mode == 'GLOBAL':
            routing_colored = f"[green]{routing_mode}[/green]"
        else:
            routing_colored = f"[blue]{routing_mode}[/blue]"
        
        # 통계 정보
        subnet_count = network.get('subnet_count', 0)
        firewall_count = network.get('firewall_rules_count', 0)
        peering_count = network.get('peerings_count', 0)
        
        # IPv4 범위 (Legacy 네트워크의 경우)
        ipv4_range = network.get('ipv4_range', '-')
        
        # 라벨 정보 (최대 2개만 표시)
        labels = network.get('labels', {})
        if labels:
            label_items = list(labels.items())[:2]
            label_text = ", ".join([f"{k}={v}" for k, v in label_items])
            if len(labels) > 2:
                label_text += f" (+{len(labels)-2})"
        else:
            label_text = "-"
        
        display_values = [
            network.get("project_id", "") if project_changed else "",
            network.get("name", "N/A"),
            network_mode,
            routing_colored,
            str(subnet_count) if subnet_count > 0 else "-",
            str(firewall_count) if firewall_count > 0 else "-",
            str(peering_count) if peering_count > 0 else "-",
            ipv4_range,
            label_text
        ]
        
        table.add_row(*display_values)

        last_project = network.get("project_id")
    
    console.print(table)


def format_tree_output(networks: List[Dict]) -> None:
    """
    GCP VPC 네트워크 목록을 트리 형식으로 출력합니다 (프로젝트/네트워크 계층).
    
    Args:
        networks: VPC 네트워크 정보 리스트
    """
    if not networks:
        console.print("[yellow]표시할 GCP VPC 네트워크 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for network in networks:
        project_id = network.get("project_id", "unknown")
        
        if project_id not in projects:
            projects[project_id] = []
        
        projects[project_id].append(network)

    # 트리 구조 생성
    tree = Tree("🌐 [bold blue]GCP VPC Networks[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_networks = projects[project_id]
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta] ({len(project_networks)} networks)")
        
        for network in sorted(project_networks, key=lambda x: x.get("name", "")):
            # 네트워크 모드 아이콘
            if network.get('auto_create_subnetworks'):
                mode_icon = "🔄"  # Auto mode
                mode_text = "Auto"
            elif network.get('ipv4_range'):
                mode_icon = "🔒"  # Legacy mode
                mode_text = "Legacy"
            else:
                mode_icon = "⚙️"   # Custom mode
                mode_text = "Custom"
            
            # 네트워크 정보
            network_name = network.get("name", "N/A")
            routing_mode = network.get("routing_mode", "REGIONAL")
            subnet_count = network.get("subnet_count", 0)
            firewall_count = network.get("firewall_rules_count", 0)
            
            network_info = (
                f"{mode_icon} [bold white]{network_name}[/bold white] "
                f"({mode_text}, {routing_mode}) - "
                f"Subnets: [blue]{subnet_count}[/blue], "
                f"Firewalls: [red]{firewall_count}[/red]"
            )
            
            network_node = project_node.add(network_info)
            
            # 서브넷 정보
            if network.get('subnets'):
                subnets_node = network_node.add(f"🔗 [bold cyan]Subnets ({len(network['subnets'])})[/bold cyan]")
                for subnet in network['subnets'][:5]:  # 최대 5개만 표시
                    subnet_info = (
                        f"📍 {subnet['name']} - "
                        f"[cyan]{subnet['ip_cidr_range']}[/cyan] "
                        f"({subnet['region']})"
                    )
                    subnets_node.add(subnet_info)
                
                if len(network['subnets']) > 5:
                    subnets_node.add(f"... and {len(network['subnets']) - 5} more subnets")
            
            # 방화벽 규칙 정보
            if network.get('firewall_rules'):
                fw_node = network_node.add(f"🛡️  [bold red]Firewall Rules ({len(network['firewall_rules'])})[/bold red]")
                for fw in network['firewall_rules'][:3]:  # 최대 3개만 표시
                    action_icon = "✅" if fw['action'] == 'ALLOW' else "❌"
                    fw_info = (
                        f"{action_icon} {fw['name']} - "
                        f"{fw['direction']} (Priority: {fw['priority']})"
                    )
                    fw_node.add(fw_info)
                
                if len(network['firewall_rules']) > 3:
                    fw_node.add(f"... and {len(network['firewall_rules']) - 3} more rules")
            
            # 피어링 정보
            if network.get('peerings'):
                peering_node = network_node.add(f"🔗 [bold green]Peerings ({len(network['peerings'])})[/bold green]")
                for peering in network['peerings']:
                    peering_info = f"🤝 {peering['name']} - {peering['state']}"
                    peering_node.add(peering_info)
            
            # 라벨 정보
            if network.get('labels'):
                labels_text = ", ".join([f"{k}={v}" for k, v in network['labels'].items()])
                network_node.add(f"🏷️  Labels: {labels_text}")

    console.print(tree)


def format_output(networks: List[Dict], output_format: str = 'table') -> str:
    """
    VPC 네트워크 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        networks: VPC 네트워크 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(networks)
        return ""
    elif output_format == 'tree':
        format_tree_output(networks)
        return ""
    elif output_format == 'json':
        return format_gcp_output(networks, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(networks, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(networks)
        return ""


def print_network_table(networks):
    """GCP VPC 네트워크 목록을 계층적 테이블로 출력합니다. (하위 호환성을 위한 래퍼)"""
    format_table_output(networks)


def main(args):
    """
    메인 함수 - GCP VPC 네트워크 정보를 조회하고 출력합니다.
    
    Args:
        args: CLI 인자 객체
    """
    try:
        log_info("GCP VPC 네트워크 조회 시작")
        
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
        
        # 병렬로 VPC 네트워크 수집
        all_networks = resource_collector.parallel_collect(
            projects, 
            fetch_vpc_networks,
            args.region if hasattr(args, 'region') else None
        )
        
        if not all_networks:
            console.print("[yellow]조회된 VPC 네트워크가 없습니다.[/yellow]")
            return
        
        # 필터 적용
        filters = {}
        if hasattr(args, 'name') and args.name:
            filters['name'] = args.name
        if hasattr(args, 'project') and args.project:
            filters['project'] = args.project
        if hasattr(args, 'region') and args.region:
            filters['region'] = args.region
        
        filtered_networks = resource_collector.apply_filters(all_networks, filters)
        
        # 출력 형식 결정
        output_format = getattr(args, 'output', 'table')
        
        # 결과 출력
        if output_format in ['json', 'yaml']:
            output_text = format_output(filtered_networks, output_format)
            console.print(output_text)
        else:
            format_output(filtered_networks, output_format)
        
        log_info(f"총 {len(filtered_networks)}개 VPC 네트워크 조회 완료")
        
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
        '-n', '--name', 
        help='네트워크 이름으로 필터링 (부분 일치)'
    )
    parser.add_argument(
        '-r', '--region', 
        help='지역으로 필터링 (예: us-central1)'
    )
    parser.add_argument(
        '-o', '--output', 
        choices=['table', 'tree', 'json', 'yaml'],
        default='table',
        help='출력 형식 선택 (기본값: table)'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP VPC 네트워크 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)