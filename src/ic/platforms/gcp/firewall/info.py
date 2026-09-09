#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
try:
    from google.cloud.compute_v1 import FirewallsClient, NetworksClient, InstancesClient
    from google.cloud.compute_v1.types import ListFirewallsRequest, ListNetworksRequest, GetFirewallRequest
    from google.api_core import exceptions as gcp_exceptions
    GCP_FIREWALL_AVAILABLE = True
except ImportError:
    GCP_FIREWALL_AVAILABLE = False
    FirewallsClient: Any = None
    NetworksClient: Any = None
    InstancesClient: Any = None
    ListFirewallsRequest: Any = None
    ListNetworksRequest: Any = None
    GetFirewallRequest: Any = None
    gcp_exceptions: Any = None
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from ic.core.interfaces import BaseCommand, CommandResult
from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    format_gcp_output, get_gcp_resource_labels
)
from common.log import log_info, log_error, log_exception, log_info_non_console

console = Console()


def fetch_firewall_rules_direct(project_id: str, network_filter: Optional[str] = None, verbose: bool = False) -> List[Dict]:
    """
    직접 API를 통해 GCP 방화벽 규칙을 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        network_filter: 네트워크 필터 (선택사항)
        verbose: 상세 모드 여부 (인스턴스 매핑 포함)
    
    Returns:
        방화벽 규칙 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        firewalls_client = FirewallsClient(credentials=credentials)
        networks_client = NetworksClient(credentials=credentials)
        
        # 프로젝트의 모든 방화벽 규칙 가져오기
        # 네트워크 캐시 (규칙마다 networks_client.list를 반복 호출하는 것을 방지)
        networks_cache: Dict[str, Any] = {}
        try:
            for net in networks_client.list(request=ListNetworksRequest(project=project_id)):
                networks_cache[net.name] = net
        except Exception as e:
            log_info_non_console(f"네트워크 목록 캐시 실패: {project_id}, Error={e}")

        # 프로젝트의 모든 방화벽 규칙 가져오기
        firewalls_request = ListFirewallsRequest(project=project_id)
        firewalls = firewalls_client.list(request=firewalls_request)

        all_firewall_rules = []
        
        for firewall in firewalls:
            try:
                firewall_data = collect_firewall_rule_details(
                    firewalls_client, networks_client, project_id, firewall, network_filter,
                    networks_cache=networks_cache
                )
                if firewall_data:
                    all_firewall_rules.append(firewall_data)
                    
            except gcp_exceptions.Forbidden:
                log_error(f"방화벽 규칙 {firewall.name}에 대한 접근 권한이 없습니다: {project_id}")
                continue
            except Exception as e:
                log_error(f"방화벽 규칙 {firewall.name} 조회 실패: {project_id}, Error={e}")
                continue
        
        # verbose 모드인 경우 방화벽 규칙을 적용받는 Compute Engine 인스턴스 매핑
        if verbose and InstancesClient and all_firewall_rules:
            try:
                instances: List[Dict[str, Any]] = []
                instances_client = InstancesClient(credentials=credentials)
                pager = instances_client.aggregated_list(project=project_id)
                for _loc, scoped_list in pager:
                    instances_seq = getattr(scoped_list, 'instances', None)
                    if not instances_seq:
                        continue
                    for inst in instances_seq:
                        instances.append({
                            'name': inst.name,
                            'status': getattr(inst, 'status', ''),
                            'tags': set(inst.tags.items) if getattr(inst, 'tags', None) and getattr(inst.tags, 'items', None) else set(),
                            'networks': set(ni.network.split('/')[-1] for ni in getattr(inst, 'network_interfaces', []) if getattr(ni, 'network', None)),
                            'sa': set(sa.email for sa in getattr(inst, 'service_accounts', [])) if getattr(inst, 'service_accounts', None) else set()
                        })

                if instances:
                    for rule_data in all_firewall_rules:
                        rule_net = rule_data.get('network', '')
                        tgt_tags = set(rule_data.get('target_tags', []))
                        tgt_sa = set(rule_data.get('target_service_accounts', []))

                        if tgt_tags or tgt_sa:
                            rule_data['target_type'] = 'TAG' if tgt_tags else 'SA'
                            matched = []
                            for inst in instances:
                                if rule_net and rule_net not in inst['networks']:
                                    continue
                                if tgt_tags and tgt_tags.intersection(inst['tags']):
                                    matched.append(inst['name'])
                                elif tgt_sa and tgt_sa.intersection(inst['sa']):
                                    matched.append(inst['name'])
                            rule_data['applied_instances'] = matched
                        else:
                            rule_data['target_type'] = 'ALL'
                            rule_data['applied_instances'] = []
            except Exception as e:
                log_info_non_console(f"인스턴스 정보 수집 스킵: {project_id}, Error={e}")

        log_info(f"프로젝트 {project_id}에서 {len(all_firewall_rules)}개 방화벽 규칙 발견")
        return all_firewall_rules
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Compute Engine 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"방화벽 규칙 조회 실패: {project_id}, Error={e}")
        return []


def fetch_firewall_rules(project_id: str, network_filter: Optional[str] = None, verbose: bool = False) -> List[Dict]:
    """
    GCP 방화벽 규칙을 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        network_filter: 네트워크 필터 (선택사항)
        verbose: 상세 모드 여부 (인스턴스 매핑 포함)
    
    Returns:
        방화벽 규칙 정보 리스트
    """
    return fetch_firewall_rules_direct(project_id, network_filter, verbose=verbose)


def collect_firewall_rule_details(firewalls_client: Any, networks_client: Any,
                                 project_id: str, firewall, network_filter: Optional[str] = None,
                                 networks_cache: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
    """
    방화벽 규칙의 상세 정보를 수집합니다.
    
    Args:
        firewalls_client: Firewalls 클라이언트
        networks_client: Networks 클라이언트
        project_id: GCP 프로젝트 ID
        firewall: 방화벽 규칙 객체
        network_filter: 네트워크 필터
    
    Returns:
        방화벽 규칙 상세 정보 딕셔너리
    """
    try:
        # 네트워크 이름 추출
        network_name = firewall.network.split('/')[-1] if firewall.network else 'default'
        
        # 네트워크 필터 적용
        if network_filter and network_filter not in network_name:
            return None
        
        # 기본 방화벽 규칙 정보
        firewall_data = {
            'project_id': project_id,
            'name': firewall.name,
            'description': firewall.description or '',
            'network': network_name,
            'network_url': firewall.network,
            'direction': firewall.direction,
            'priority': firewall.priority,
            'action': 'ALLOW' if firewall.allowed else 'DENY',
            'disabled': firewall.disabled if hasattr(firewall, 'disabled') else False,
            'creation_timestamp': firewall.creation_timestamp,
            'self_link': firewall.self_link,
            'labels': get_gcp_resource_labels(firewall),
            'source_ranges': list(firewall.source_ranges) if firewall.source_ranges else [],
            'destination_ranges': list(firewall.destination_ranges) if firewall.destination_ranges else [],
            'source_tags': list(firewall.source_tags) if firewall.source_tags else [],
            'target_tags': list(firewall.target_tags) if firewall.target_tags else [],
            'source_service_accounts': list(firewall.source_service_accounts) if firewall.source_service_accounts else [],
            'target_service_accounts': list(firewall.target_service_accounts) if firewall.target_service_accounts else [],
            'allowed_rules': [],
            'denied_rules': [],
            'log_config': {}
        }
        
        allowed_rules: List[Dict[str, Any]] = []
        denied_rules: List[Dict[str, Any]] = []

        # 허용 규칙 수집
        if firewall.allowed:
            for rule in firewall.allowed:
                rule_info = {
                    'ip_protocol': getattr(rule, 'I_p_protocol', None) or getattr(rule, 'ip_protocol', None) or getattr(rule, 'i_p_protocol', '') or '',
                    'ports': list(rule.ports) if getattr(rule, 'ports', None) else []
                }
                allowed_rules.append(rule_info)
        
        # 거부 규칙 수집
        if firewall.denied:
            for rule in firewall.denied:
                rule_info = {
                    'ip_protocol': getattr(rule, 'I_p_protocol', None) or getattr(rule, 'ip_protocol', None) or getattr(rule, 'i_p_protocol', '') or '',
                    'ports': list(rule.ports) if getattr(rule, 'ports', None) else []
                }
                denied_rules.append(rule_info)
        
        firewall_data['allowed_rules'] = allowed_rules
        firewall_data['denied_rules'] = denied_rules

        # 로그 설정 수집
        if hasattr(firewall, 'log_config') and firewall.log_config:
            firewall_data['log_config'] = {
                'enable': firewall.log_config.enable,
                'metadata': firewall.log_config.metadata if hasattr(firewall.log_config, 'metadata') else None
            }
        else:
            firewall_data['log_config'] = {'enable': False}
        
        # 네트워크 연결 정보 수집
        firewall_data['network_associations'] = get_network_associations(
            networks_client, project_id, network_name, networks_cache=networks_cache
        )
        
        # 규칙 대상 정보 수집
        firewall_data['rule_targets'] = get_rule_targets(firewall_data)
        
        # 통계 정보 추가
        firewall_data['allowed_rules_count'] = len(allowed_rules)
        firewall_data['denied_rules_count'] = len(denied_rules)
        firewall_data['total_rules_count'] = len(allowed_rules) + len(denied_rules)
        
        return firewall_data
        
    except Exception as e:
        log_error(f"방화벽 규칙 상세 정보 수집 실패: {firewall.name}, Error={e}")
        return None


def get_network_associations(networks_client: Any, project_id: str, network_name: str,
                             networks_cache: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    방화벽 규칙과 연결된 네트워크 정보를 가져옵니다.
    
    Args:
        networks_client: Networks 클라이언트
        project_id: GCP 프로젝트 ID
        network_name: 네트워크 이름
        networks_cache: 네트워크 객체 캐시 딕셔너리
    
    Returns:
        네트워크 연결 정보 리스트
    """
    associations = []
    
    try:
        if networks_cache is not None:
            network = networks_cache.get(network_name)
            if network:
                association_info = {
                    'network_name': network.name,
                    'network_description': network.description or '',
                    'auto_create_subnetworks': network.auto_create_subnetworks,
                    'routing_mode': network.routing_config.routing_mode if hasattr(network, 'routing_config') and network.routing_config else 'REGIONAL',
                    'mtu': network.mtu if hasattr(network, 'mtu') else 1460
                }
                associations.append(association_info)
            return associations

        # 캐시가 없는 경우 직접 요청
        networks_request = ListNetworksRequest(project=project_id)
        networks = networks_client.list(request=networks_request)
        
        for network in networks:
            if network.name == network_name:
                association_info = {
                    'network_name': network.name,
                    'network_description': network.description or '',
                    'auto_create_subnetworks': network.auto_create_subnetworks,
                    'routing_mode': network.routing_config.routing_mode if hasattr(network, 'routing_config') and network.routing_config else 'REGIONAL',
                    'mtu': network.mtu if hasattr(network, 'mtu') else 1460
                }
                associations.append(association_info)
                break
    
    except Exception as e:
        log_error(f"네트워크 연결 정보 수집 실패: {network_name}, Error={e}")
    
    return associations


def get_rule_targets(firewall_data: Dict) -> Dict[str, Any]:
    """
    방화벽 규칙의 대상 정보를 분석합니다.
    
    Args:
        firewall_data: 방화벽 규칙 데이터
    
    Returns:
        규칙 대상 정보 딕셔너리
    """
    targets = {
        'has_source_ranges': bool(firewall_data.get('source_ranges')),
        'has_destination_ranges': bool(firewall_data.get('destination_ranges')),
        'has_source_tags': bool(firewall_data.get('source_tags')),
        'has_target_tags': bool(firewall_data.get('target_tags')),
        'has_service_accounts': bool(firewall_data.get('source_service_accounts') or firewall_data.get('target_service_accounts')),
        'source_count': len(firewall_data.get('source_ranges', [])) + len(firewall_data.get('source_tags', [])) + len(firewall_data.get('source_service_accounts', [])),
        'target_count': len(firewall_data.get('destination_ranges', [])) + len(firewall_data.get('target_tags', [])) + len(firewall_data.get('target_service_accounts', [])),
        'applies_to_all': not any([
            firewall_data.get('source_ranges'),
            firewall_data.get('destination_ranges'),
            firewall_data.get('source_tags'),
            firewall_data.get('target_tags'),
            firewall_data.get('source_service_accounts'),
            firewall_data.get('target_service_accounts')
        ])
    }
    
    return targets


def get_firewall_rule_metadata(project_id: str, rule_name: str) -> Optional[Dict]:
    """
    특정 방화벽 규칙의 메타데이터를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        rule_name: 방화벽 규칙 이름
    
    Returns:
        방화벽 규칙 메타데이터 딕셔너리
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            return None
        
        firewalls_client = FirewallsClient(credentials=credentials)
        networks_client = NetworksClient(credentials=credentials)
        
        request = GetFirewallRequest(
            project=project_id,
            firewall=rule_name
        )
        
        firewall = firewalls_client.get(request=request)
        return collect_firewall_rule_details(firewalls_client, networks_client, project_id, firewall)
        
    except Exception as e:
        log_error(f"방화벽 규칙 메타데이터 조회 실패: {rule_name}, Error={e}")
        return None


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

def _print_verbose_firewall_table(firewall_rules: List[Dict]) -> None:
    """방화벽 규칙 목록을 소스/타겟 IP 라인별 분리 및 적용 인스턴스를 포함하여 상세 출력합니다."""
    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")

    table.add_column("Project", style="bold magenta")
    table.add_column("Network", style="bold cyan")
    table.add_column("Rule Name", style="bold white")
    table.add_column("Dir", justify="center")
    table.add_column("Action", justify="center")
    table.add_column("Priority", justify="center", style="dim")
    table.add_column("Protocols", style="blue")
    table.add_column("Destination/Source", style="green")
    table.add_column("Applied Instances", style="cyan")
    table.add_column("Log", justify="center", style="yellow")
    table.add_column("Status", justify="center")

    last_project = None
    last_network = None

    for i, rule in enumerate(firewall_rules):
        project_changed = rule.get("project_id") != last_project
        network_changed = rule.get("network") != last_network

        direction = rule.get('direction', 'INGRESS')
        direction_colored = f"[green]⬇️ {direction}[/green]" if direction == 'INGRESS' else f"[blue]⬆️ {direction}[/blue]"

        action = rule.get('action', 'ALLOW')
        action_colored = f"[green]✅ {action}[/green]" if action == 'ALLOW' else f"[red]❌ {action}[/red]"

        protocols = []
        for allowed_rule in rule.get('allowed_rules', []):
            protocol = allowed_rule.get('ip_protocol', 'all')
            ports = allowed_rule.get('ports', [])
            if ports:
                protocols.append(f"{protocol}:{','.join(ports)}")
            else:
                protocols.append(protocol)

        for denied_rule in rule.get('denied_rules', []):
            protocol = denied_rule.get('ip_protocol', 'all')
            ports = denied_rule.get('ports', [])
            if ports:
                protocols.append(f"!{protocol}:{','.join(ports)}")
            else:
                protocols.append(f"!{protocol}")

        protocols_text = ", ".join(protocols) if protocols else "all"

        # 모든 소스/타겟 목록 (라인별 분리 대상)
        targets = []
        if rule.get('source_ranges'):
            targets.extend([f"IP:{r}" for r in rule['source_ranges']])
        if rule.get('destination_ranges'):
            targets.extend([f"DST:{r}" for r in rule['destination_ranges']])
        if rule.get('source_tags'):
            targets.extend([f"SRC:{t}" for t in rule['source_tags']])
        if rule.get('target_tags'):
            targets.extend([f"TGT:{t}" for t in rule['target_tags']])
        if rule.get('source_service_accounts'):
            targets.extend([f"SRC_SA:{sa}" for sa in rule['source_service_accounts']])
        if rule.get('target_service_accounts'):
            targets.extend([f"TGT_SA:{sa}" for sa in rule['target_service_accounts']])
        if not targets:
            targets = ["all"]

        # 적용 인스턴스 목록
        applied = rule.get('applied_instances', [])
        target_type = rule.get('target_type', 'ALL')
        inst_lines = []
        if target_type == 'ALL':
            inst_lines.append("[dim]ALL[/dim]")
        else:
            if applied:
                for name in applied:
                    inst_lines.append(f"[cyan]{name}[/cyan]")
            else:
                inst_lines.append("[dim](No VMs with tag)[/dim]")

        # 로깅 및 상태
        log_enabled = rule.get('log_config', {}).get('enable', False)
        logging_status = "[green]ON[/green]" if log_enabled else "[dim]OFF[/dim]"
        disabled = rule.get('disabled', False)
        status_colored = "[red]DISABLED[/red]" if disabled else "[green]ENABLED[/green]"

        num_lines = max(len(targets), len(inst_lines), 1)

        for line_idx in range(num_lines):
            tgt_cell = targets[line_idx] if line_idx < len(targets) else ""
            inst_cell = inst_lines[line_idx] if line_idx < len(inst_lines) else ""
            is_last_line = (line_idx == num_lines - 1)

            if line_idx == 0:
                table.add_row(
                    rule.get("project_id", "") if project_changed else "",
                    rule.get("network", "") if (project_changed or network_changed) else "",
                    rule.get("name", "N/A"),
                    direction_colored,
                    action_colored,
                    str(rule.get("priority", "N/A")),
                    protocols_text,
                    tgt_cell,
                    inst_cell,
                    logging_status,
                    status_colored,
                    end_section=is_last_line
                )
            else:
                table.add_row(
                    "", "", "", "", "", "", "",
                    tgt_cell,
                    inst_cell,
                    "", "",
                    end_section=is_last_line
                )

        last_project = rule.get("project_id")
        last_network = rule.get("network")

    console.print(table)


def format_table_output(firewall_rules: List[Dict], verbose: bool = False) -> None:
    """
    GCP 방화벽 규칙 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        firewall_rules: 방화벽 규칙 정보 리스트
        verbose: 상세 모드 여부 (-v 옵션 시 True, 소스/타겟 및 인스턴스를 라인별 분리 출력)
    """
    if not firewall_rules:
        console.print("[yellow]표시할 GCP 방화벽 규칙 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 네트워크, 우선순위, 이름 순으로 정렬
    firewall_rules.sort(key=lambda x: (
        x.get("project_id", ""), 
        x.get("network", ""), 
        x.get("priority", 1000), 
        x.get("name", "")
    ))

    if verbose:
        _print_verbose_firewall_table(firewall_rules)
        return

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Network", style="bold cyan")
    table.add_column("Rule Name", style="bold white")
    table.add_column("Direction", justify="center")
    table.add_column("Action", justify="center")
    table.add_column("Priority", justify="center", style="dim")
    table.add_column("Protocols", style="blue")
    table.add_column("Sources/Targets", style="green")
    table.add_column("Logging", justify="center", style="yellow")
    table.add_column("Status", justify="center")

    last_project = None
    last_network = None
    
    for i, rule in enumerate(firewall_rules):
        project_changed = rule.get("project_id") != last_project
        network_changed = rule.get("network") != last_network

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", "", end_section=True)

        # 방향에 따른 색상 적용
        direction = rule.get('direction', 'INGRESS')
        if direction == 'INGRESS':
            direction_colored = f"[green]⬇️ {direction}[/green]"
        else:
            direction_colored = f"[blue]⬆️ {direction}[/blue]"
        
        # 액션에 따른 색상 적용
        action = rule.get('action', 'ALLOW')
        if action == 'ALLOW':
            action_colored = f"[green]✅ {action}[/green]"
        else:
            action_colored = f"[red]❌ {action}[/red]"
        
        # 프로토콜 정보 요약
        protocols = []
        for allowed_rule in rule.get('allowed_rules', []):
            protocol = allowed_rule.get('ip_protocol', 'all')
            ports = allowed_rule.get('ports', [])
            if ports:
                protocols.append(f"{protocol}:{','.join(ports[:2])}")
            else:
                protocols.append(protocol)
        
        for denied_rule in rule.get('denied_rules', []):
            protocol = denied_rule.get('ip_protocol', 'all')
            ports = denied_rule.get('ports', [])
            if ports:
                protocols.append(f"!{protocol}:{','.join(ports[:2])}")
            else:
                protocols.append(f"!{protocol}")
        
        protocols_text = ", ".join(protocols[:3])
        if len(protocols) > 3:
            protocols_text += f" (+{len(protocols)-3})"
        if not protocols_text:
            protocols_text = "all"
        
        # 소스/타겟 정보 요약
        sources_targets = []
        if rule.get('source_ranges'):
            sources_targets.extend([f"IP:{r}" for r in rule['source_ranges'][:2]])
        if rule.get('destination_ranges'):
            sources_targets.extend([f"DST:{r}" for r in rule['destination_ranges'][:2]])
        if rule.get('source_tags'):
            sources_targets.extend([f"SRC:{t}" for t in rule['source_tags'][:2]])
        if rule.get('target_tags'):
            sources_targets.extend([f"TGT:{t}" for t in rule['target_tags'][:2]])
        
        sources_targets_text = ", ".join(sources_targets[:2])
        total_targets = (len(rule.get('source_ranges', [])) + 
                        len(rule.get('destination_ranges', [])) + 
                        len(rule.get('source_tags', [])) + 
                        len(rule.get('target_tags', [])))
        if total_targets > 2:
            sources_targets_text += f" (+{total_targets-2})"
        if not sources_targets_text:
            sources_targets_text = "all"
        
        # 로깅 상태
        log_enabled = rule.get('log_config', {}).get('enable', False)
        logging_status = "[green]ON[/green]" if log_enabled else "[dim]OFF[/dim]"
        
        # 규칙 상태
        disabled = rule.get('disabled', False)
        if disabled:
            status_colored = "[red]DISABLED[/red]"
        else:
            status_colored = "[green]ENABLED[/green]"
        
        display_values = [
            rule.get("project_id", "") if project_changed else "",
            rule.get("network", "") if project_changed or network_changed else "",
            rule.get("name", "N/A"),
            direction_colored,
            action_colored,
            str(rule.get("priority", "N/A")),
            protocols_text,
            sources_targets_text,
            logging_status,
            status_colored
        ]
        
        table.add_row(*display_values)

        last_project = rule.get("project_id")
        last_network = rule.get("network")
    
    console.print(table)


def format_tree_output(firewall_rules: List[Dict]) -> None:
    """
    GCP 방화벽 규칙 목록을 트리 형식으로 출력합니다 (프로젝트/네트워크/방향 계층).
    
    Args:
        firewall_rules: 방화벽 규칙 정보 리스트
    """
    if not firewall_rules:
        console.print("[yellow]표시할 GCP 방화벽 규칙 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for rule in firewall_rules:
        project_id = rule.get("project_id", "unknown")
        network = rule.get("network", "default")
        direction = rule.get("direction", "INGRESS")
        
        if project_id not in projects:
            projects[project_id] = {}
        if network not in projects[project_id]:
            projects[project_id][network] = {}
        if direction not in projects[project_id][network]:
            projects[project_id][network][direction] = []
        
        projects[project_id][network][direction].append(rule)

    # 트리 구조 생성
    tree = Tree("🛡️ [bold blue]GCP Firewall Rules[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_networks = projects[project_id]
        total_rules = sum(len(rules) for network in project_networks.values() 
                         for rules in network.values())
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta] ({total_rules} rules)")
        
        for network in sorted(project_networks.keys()):
            network_directions = project_networks[network]
            network_rules = sum(len(rules) for rules in network_directions.values())
            network_node = project_node.add(f"🌐 [bold cyan]{network}[/bold cyan] ({network_rules} rules)")
            
            for direction in sorted(network_directions.keys()):
                direction_rules = network_directions[direction]
                direction_icon = "⬇️" if direction == "INGRESS" else "⬆️"
                direction_color = "green" if direction == "INGRESS" else "blue"
                direction_node = network_node.add(
                    f"{direction_icon} [bold {direction_color}]{direction}[/bold {direction_color}] ({len(direction_rules)} rules)"
                )
                
                # 우선순위 순으로 정렬
                sorted_rules = sorted(direction_rules, key=lambda x: x.get("priority", 1000))
                
                for rule in sorted_rules[:10]:  # 최대 10개만 표시
                    # 액션 아이콘
                    action = rule.get('action', 'ALLOW')
                    action_icon = "✅" if action == 'ALLOW' else "❌"
                    
                    # 규칙 정보
                    rule_name = rule.get("name", "N/A")
                    priority = rule.get("priority", "N/A")
                    disabled = rule.get("disabled", False)
                    status_text = " [red](DISABLED)[/red]" if disabled else ""
                    
                    rule_info = (
                        f"{action_icon} [bold white]{rule_name}[/bold white] "
                        f"(Priority: [dim]{priority}[/dim]){status_text}"
                    )
                    
                    rule_node = direction_node.add(rule_info)
                    
                    # 프로토콜 정보
                    protocols = []
                    for allowed_rule in rule.get('allowed_rules', []):
                        protocol = allowed_rule.get('ip_protocol', 'all')
                        ports = allowed_rule.get('ports', [])
                        if ports:
                            protocols.append(f"{protocol}:{','.join(ports)}")
                        else:
                            protocols.append(protocol)
                    
                    if protocols:
                        protocols_text = ", ".join(protocols[:3])
                        if len(protocols) > 3:
                            protocols_text += f" (+{len(protocols)-3} more)"
                        rule_node.add(f"🔌 Protocols: {protocols_text}")
                    
                    # 소스/타겟 정보
                    if rule.get('source_ranges'):
                        sources_text = ", ".join(rule['source_ranges'][:3])
                        if len(rule['source_ranges']) > 3:
                            sources_text += f" (+{len(rule['source_ranges'])-3} more)"
                        rule_node.add(f"📍 Sources: {sources_text}")
                    
                    if rule.get('target_tags'):
                        targets_text = ", ".join(rule['target_tags'][:3])
                        if len(rule['target_tags']) > 3:
                            targets_text += f" (+{len(rule['target_tags'])-3} more)"
                        rule_node.add(f"🎯 Targets: {targets_text}")
                    
                    # 로깅 상태
                    log_enabled = rule.get('log_config', {}).get('enable', False)
                    if log_enabled:
                        rule_node.add("📝 [green]Logging: ENABLED[/green]")
                
                if len(direction_rules) > 10:
                    direction_node.add(f"... and {len(direction_rules) - 10} more rules")

    console.print(tree)


def format_output(firewall_rules: List[Dict], output_format: str = 'table') -> str:
    """
    방화벽 규칙 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        firewall_rules: 방화벽 규칙 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(firewall_rules)
        return ""
    elif output_format == 'tree':
        format_tree_output(firewall_rules)
        return ""
    elif output_format == 'json':
        return format_gcp_output(firewall_rules, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(firewall_rules, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(firewall_rules)
        return ""


def print_firewall_table(firewall_rules):
    """GCP 방화벽 규칙 목록을 계층적 테이블로 출력합니다. (하위 호환성을 위한 래퍼)"""
    format_table_output(firewall_rules)


def format_paste_output(rules: List[Dict]) -> None:
    """방화벽 규칙 목록을 -p (paste) 모드용 CSV로 출력합니다."""
    for r in rules:
        row = [
            r.get('project_id', '-'),
            r.get('network', '-'),
            r.get('name', '-'),
            r.get('direction', '-'),
            r.get('priority', '-'),
            r.get('action', '-'),
        ]
        print(",".join(str(c) for c in row))


class GcpFirewallInfoCommand(BaseCommand):
    """GCP 방화벽 규칙 정보 조회 커맨드"""

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
            '-n', '--name', '-r', '--rule-name',
            dest='rule_name',
            help='방화벽 규칙 이름으로 필터링 (콤마 구분 가능, 부분 일치)'
        )
        parser.add_argument(
            '--network', 
            help='네트워크 이름으로 필터링 (예: default, custom-vpc)'
        )
        parser.add_argument(
            '-d', '--direction', 
            choices=['INGRESS', 'EGRESS'],
            help='방화벽 규칙 방향으로 필터링'
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
            help='상세 정보 출력 (소스/타겟 IP 라인별 분리 및 적용 인스턴스 표시)'
        )
        parser.add_argument(
            '--mock',
            action='store_true',
            help='Mock 데이터를 사용하여 오프라인으로 실행'
        )

    def execute(self, args, config=None) -> CommandResult:
        verbose = getattr(args, 'verbose', False)
        if getattr(args, 'mock', False):
            rules = load_mock_data()
            filtered = []
            name_filter = getattr(args, 'rule_name', None)
            proj_filter = getattr(args, 'project', None)
            net_filter = getattr(args, 'network', None)
            dir_filter = getattr(args, 'direction', None)

            name_patterns = [p.strip().lower() for p in name_filter.split(',')] if name_filter else []
            proj_patterns = [p.strip().lower() for p in proj_filter.split(',')] if proj_filter else []

            for r in rules:
                r_name = str(r.get('name', '')).lower()
                r_proj = str(r.get('project_id', '')).lower()
                if name_patterns and not any(p in r_name for p in name_patterns):
                    continue
                if proj_patterns and not any(p in r_proj for p in proj_patterns):
                    continue
                if net_filter and net_filter.lower() not in str(r.get('network', '')).lower():
                    continue
                if dir_filter and dir_filter.upper() != str(r.get('direction', '')).upper():
                    continue
                filtered.append(r)
            return CommandResult(
                data=filtered,
                table_renderer=lambda data, v=False: format_table_output(data, verbose=v or verbose),
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )

        if not GCP_FIREWALL_AVAILABLE:
            console.print("[red]❌ google-cloud-compute 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   pip install 'ic-cli[gcp]' 또는 pip install google-cloud-compute[/yellow]")
            console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
            return CommandResult(data=[], error="google-cloud-compute is not installed", success=False)

        try:
            log_info_non_console("GCP 방화벽 규칙 조회 시작")
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
                return CommandResult(data=[], table_renderer=lambda data, v=False: format_table_output(data, verbose=v or verbose), tree_renderer=format_tree_output, paste_renderer=format_paste_output)

            all_firewall_rules = resource_collector.parallel_collect(
                projects, 
                fetch_firewall_rules,
                getattr(args, 'network', None),
                verbose=verbose
            )

            filters = {}
            if getattr(args, 'rule_name', None):
                filters['name'] = args.rule_name
            if getattr(args, 'project', None):
                filters['project'] = args.project
            if getattr(args, 'network', None):
                filters['network'] = args.network
            if getattr(args, 'direction', None):
                filters['direction'] = args.direction

            filtered_rules = resource_collector.apply_filters(all_firewall_rules, filters)
            return CommandResult(
                data=filtered_rules,
                table_renderer=lambda data, v=False: format_table_output(data, verbose=v or verbose),
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )
        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpFirewallInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpFirewallInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP 방화벽 규칙 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)