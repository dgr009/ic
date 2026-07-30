#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from google.cloud import billing_v1
from google.cloud.billing_v1 import CloudBillingClient, CloudCatalogClient
from google.cloud.billing_v1.types import (
    ListBillingAccountsRequest, GetBillingAccountRequest,
    ListProjectBillingInfoRequest, GetProjectBillingInfoRequest,
    ListServicesRequest, ListSkusRequest
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


def fetch_billing_info_via_mcp(mcp_connector, project_id: str) -> List[Dict]:
    """
    MCP 서버를 통해 GCP Billing 정보를 가져옵니다.
    
    Args:
        mcp_connector: MCP GCP 커넥터
        project_id: GCP 프로젝트 ID
    
    Returns:
        Billing 정보 리스트
    """
    try:
        params = {
            'project_id': project_id
        }
        
        response = mcp_connector.execute_gcp_query('billing', 'list_billing_info', params)
        if response.success:
            return response.data.get('billing_info', [])
        else:
            log_error(f"MCP billing info query failed: {response.error}")
            return []
            
    except Exception as e:
        log_error(f"MCP billing info fetch failed: {e}")
        return []


def fetch_billing_info_direct(project_id: str) -> List[Dict]:
    """
    직접 API를 통해 GCP Billing 정보를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
    
    Returns:
        Billing 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        billing_client = CloudBillingClient(credentials=credentials)
        catalog_client = CloudCatalogClient(credentials=credentials)
        
        all_billing_info = []
        
        try:
            # 프로젝트의 빌링 정보 가져오기
            project_billing_request = GetProjectBillingInfoRequest(
                name=f"projects/{project_id}"
            )
            project_billing_info = billing_client.get_project_billing_info(request=project_billing_request)
            
            if project_billing_info.billing_enabled:
                billing_account_name = project_billing_info.billing_account_name
                
                # 빌링 계정 상세 정보 가져오기
                billing_account_request = GetBillingAccountRequest(
                    name=billing_account_name
                )
                billing_account = billing_client.get_billing_account(request=billing_account_request)
                
                billing_data = collect_billing_details(
                    billing_client, catalog_client, project_id, billing_account, project_billing_info
                )
                if billing_data:
                    all_billing_info.append(billing_data)
            else:
                # 빌링이 비활성화된 프로젝트도 기록
                billing_data = {
                    'project_id': project_id,
                    'billing_enabled': False,
                    'billing_account_name': None,
                    'billing_account_display_name': 'N/A',
                    'billing_account_open': False,
                    'currency_code': 'N/A',
                    'master_billing_account': None,
                    'subaccounts': [],
                    'services': [],
                    'current_month_cost': 0.0,
                    'cost_by_service': {},
                    'budgets': [],
                    'alerts': []
                }
                all_billing_info.append(billing_data)
                    
        except gcp_exceptions.Forbidden:
            log_error(f"프로젝트 {project_id}에 대한 Billing 접근 권한이 없습니다. "
                     f"Cloud Billing API가 활성화되어 있고 적절한 IAM 권한이 있는지 확인하세요.")
            return []
        except gcp_exceptions.NotFound:
            log_error(f"프로젝트 {project_id}의 빌링 정보를 찾을 수 없습니다. "
                     f"프로젝트 ID가 올바른지 확인하세요.")
            return []
        except gcp_exceptions.ServiceUnavailable:
            log_error(f"Cloud Billing API가 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도하세요.")
            return []
        except gcp_exceptions.TooManyRequests:
            log_error(f"API 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요.")
            return []
        except gcp_exceptions.Unauthenticated:
            log_error(f"GCP 인증이 필요합니다. 인증 정보를 확인하세요.")
            return []
        except Exception as e:
            log_error(f"Billing 정보 조회 실패: {project_id}, Error={e}")
            return []
        
        log_info(f"프로젝트 {project_id}에서 {len(all_billing_info)}개 Billing 정보 발견")
        return all_billing_info
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Billing 권한이 없습니다. "
                 f"billing.accounts.get, billing.resourceAssociations.list 권한이 필요합니다.")
        return []
    except gcp_exceptions.Unauthenticated:
        log_error(f"GCP 인증이 필요합니다. 서비스 계정 키 또는 ADC를 설정하세요.")
        return []
    except Exception as e:
        log_error(f"Billing 정보 조회 실패: {project_id}, Error={e}")
        return []


def fetch_billing_info(project_id: str) -> List[Dict]:
    """
    GCP Billing 정보를 가져옵니다 (MCP 우선, 직접 API 폴백).
    
    Args:
        project_id: GCP 프로젝트 ID
    
    Returns:
        Billing 정보 리스트
    """
    # MCP 서비스 사용 시도
    if MCP_AVAILABLE:
        try:
            mcp_service = MCPGCPService('billing')
            return mcp_service.execute_with_fallback(
                'list_billing_info',
                {'project_id': project_id},
                lambda project_id: fetch_billing_info_direct(project_id)
            )
        except Exception as e:
            log_error(f"MCP service failed, using direct API: {e}")
    
    # 직접 API 사용
    return fetch_billing_info_direct(project_id)


def collect_billing_details(billing_client: CloudBillingClient, 
                          catalog_client: CloudCatalogClient,
                          project_id: str, billing_account, project_billing_info) -> Optional[Dict]:
    """
    빌링 계정의 상세 정보를 수집합니다.
    
    Args:
        billing_client: Cloud Billing 클라이언트
        catalog_client: Cloud Catalog 클라이언트
        project_id: GCP 프로젝트 ID
        billing_account: 빌링 계정 객체
        project_billing_info: 프로젝트 빌링 정보 객체
    
    Returns:
        빌링 상세 정보 딕셔너리
    """
    try:
        # 기본 빌링 정보
        billing_data = {
            'project_id': project_id,
            'billing_enabled': project_billing_info.billing_enabled,
            'billing_account_name': billing_account.name,
            'billing_account_display_name': billing_account.display_name,
            'billing_account_open': billing_account.open_,
            'currency_code': billing_account.currency_code,
            'master_billing_account': billing_account.master_billing_account,
            'subaccounts': [],
            'services': [],
            'current_month_cost': 0.0,  # 실제 비용 데이터는 별도 API 필요
            'cost_by_service': {},
            'budgets': [],  # Budget API는 별도 라이브러리 필요
            'alerts': []
        }
        
        # 서브 계정 정보 수집
        if hasattr(billing_account, 'subaccounts') and billing_account.subaccounts:
            for subaccount in billing_account.subaccounts:
                subaccount_info = {
                    'name': subaccount.name,
                    'display_name': subaccount.display_name,
                    'open': subaccount.open_
                }
                billing_data['subaccounts'].append(subaccount_info)
        
        # 사용 가능한 서비스 목록 수집
        try:
            services_request = ListServicesRequest()
            services_response = catalog_client.list_services(request=services_request)
            
            for service in services_response:
                service_info = {
                    'name': service.name,
                    'service_id': service.service_id,
                    'display_name': service.display_name,
                    'business_entity_name': service.business_entity_name
                }
                billing_data['services'].append(service_info)
                
                # 서비스별 비용 정보는 실제 사용량 데이터가 필요하므로 여기서는 0으로 설정
                billing_data['cost_by_service'][service.service_id] = 0.0
                
        except Exception as e:
            log_error(f"서비스 목록 수집 실패: {billing_account.name}, Error={e}")
        
        # 현재 월 비용 계산 (실제로는 Cloud Billing Reports API 필요)
        # 여기서는 시뮬레이션된 데이터 사용
        billing_data['current_month_cost'] = sum(billing_data['cost_by_service'].values())
        
        # 예산 및 알림 정보 (실제로는 Cloud Billing Budget API 필요)
        # 여기서는 기본 구조만 제공
        billing_data['budgets'] = []
        billing_data['alerts'] = []
        
        return billing_data
        
    except Exception as e:
        log_error(f"빌링 상세 정보 수집 실패: {billing_account.name}, Error={e}")
        return None


def get_cost_details(billing_client: CloudBillingClient, billing_account_id: str, 
                    date_range: Dict) -> Dict:
    """
    빌링 계정의 비용 상세 정보를 가져옵니다.
    
    Args:
        billing_client: Cloud Billing 클라이언트
        billing_account_id: 빌링 계정 ID
        date_range: 날짜 범위 딕셔너리
    
    Returns:
        비용 상세 정보 딕셔너리
    """
    try:
        # 실제로는 Cloud Billing Reports API를 사용해야 함
        # 여기서는 기본 구조만 제공
        cost_details = {
            'billing_account_id': billing_account_id,
            'date_range': date_range,
            'total_cost': 0.0,
            'cost_by_service': {},
            'cost_by_project': {},
            'cost_by_location': {},
            'cost_trend': []
        }
        
        return cost_details
        
    except Exception as e:
        log_error(f"비용 상세 정보 조회 실패: {billing_account_id}, Error={e}")
        return {}


def get_budget_alerts(billing_client: CloudBillingClient, billing_account_id: str) -> List[Dict]:
    """
    빌링 계정의 예산 알림을 가져옵니다.
    
    Args:
        billing_client: Cloud Billing 클라이언트
        billing_account_id: 빌링 계정 ID
    
    Returns:
        예산 알림 리스트
    """
    try:
        # 실제로는 Cloud Billing Budget API를 사용해야 함
        # 여기서는 기본 구조만 제공
        budget_alerts = []
        
        return budget_alerts
        
    except Exception as e:
        log_error(f"예산 알림 조회 실패: {billing_account_id}, Error={e}")
        return []


def get_spending_by_service(billing_client: CloudBillingClient, 
                          billing_account_id: str, project_id: str) -> Dict:
    """
    서비스별 지출 정보를 가져옵니다.
    
    Args:
        billing_client: Cloud Billing 클라이언트
        billing_account_id: 빌링 계정 ID
        project_id: GCP 프로젝트 ID
    
    Returns:
        서비스별 지출 정보 딕셔너리
    """
    try:
        # 실제로는 Cloud Billing Reports API를 사용해야 함
        # 여기서는 기본 구조만 제공
        spending_by_service = {
            'billing_account_id': billing_account_id,
            'project_id': project_id,
            'services': {},
            'total_spending': 0.0,
            'currency': 'USD'
        }
        
        return spending_by_service
        
    except Exception as e:
        log_error(f"서비스별 지출 조회 실패: {billing_account_id}, Error={e}")
        return {}


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


def format_table_output(billing_info: List[Dict], date_range: Optional[Dict] = None) -> None:
    """
    GCP Billing 정보 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        billing_info: 빌링 정보 리스트
        date_range: 날짜 범위 정보 (선택적)
    """
    if not billing_info:
        console.print("[yellow]표시할 GCP Billing 정보가 없습니다.[/yellow]")
        return

    # 날짜 범위 정보 표시
    if date_range:
        start_date = date_range.get('start_date', 'N/A')
        end_date = date_range.get('end_date', 'N/A')
        console.print(f"[dim]Cost data for period: {start_date} to {end_date}[/dim]")
        console.print()

    # 프로젝트, 빌링 계정 순으로 정렬
    billing_info.sort(key=lambda x: (x.get("project_id", ""), x.get("billing_account_display_name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Billing Account", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Currency", justify="center", style="cyan")
    table.add_column("Current Cost", justify="right", style="green")
    table.add_column("Services", justify="center", style="blue")
    table.add_column("Budgets", justify="center", style="yellow")
    table.add_column("Budget Status", justify="center", style="yellow")
    table.add_column("Master Account", style="dim")

    last_project = None
    
    for i, billing in enumerate(billing_info):
        project_changed = billing.get("project_id") != last_project

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", end_section=True)

        # 빌링 상태에 따른 색상 적용
        billing_enabled = billing.get('billing_enabled', False)
        account_open = billing.get('billing_account_open', False)
        
        if billing_enabled and account_open:
            status = "✓ Active"
            status_colored = f"[green]{status}[/green]"
        elif billing_enabled and not account_open:
            status = "⚠ Closed"
            status_colored = f"[yellow]{status}[/yellow]"
        else:
            status = "✗ Disabled"
            status_colored = f"[red]{status}[/red]"
        
        # 현재 비용 포맷팅
        current_cost = billing.get('current_month_cost', 0.0)
        currency = billing.get('currency_code', 'USD')
        if isinstance(current_cost, (int, float)) and current_cost > 0:
            cost_str = f"{current_cost:.2f} {currency}"
        else:
            cost_str = f"0.00 {currency}"
        
        # 서비스 수
        services_count = len(billing.get('services', []))
        services_str = str(services_count) if services_count > 0 else "-"
        
        # 예산 수 및 상태
        budgets = billing.get('budgets', [])
        budgets_count = len(budgets)
        budgets_str = str(budgets_count) if budgets_count > 0 else "-"
        
        # 예산 임계값 상태 확인
        budget_status = "-"
        if budgets:
            # 예산 초과 여부 확인
            over_budget = any(
                budget.get('current_spend', 0) > budget.get('threshold_amount', float('inf'))
                for budget in budgets
            )
            near_budget = any(
                budget.get('current_spend', 0) > budget.get('threshold_amount', float('inf')) * 0.8
                for budget in budgets
            )
            
            if over_budget:
                budget_status = "[red]⚠ Over[/red]"
            elif near_budget:
                budget_status = "[yellow]⚠ Near[/yellow]"
            else:
                budget_status = "[green]✓ OK[/green]"
        
        # 마스터 계정
        master_account = billing.get('master_billing_account', '')
        if master_account:
            # 계정 이름에서 ID 부분만 추출
            master_display = master_account.split('/')[-1] if '/' in master_account else master_account
        else:
            master_display = "-"
        
        display_values = [
            billing.get("project_id", "") if project_changed else "",
            billing.get("billing_account_display_name", "N/A"),
            status_colored,
            billing.get("currency_code", "N/A"),
            cost_str,
            services_str,
            budgets_str,
            budget_status,
            master_display
        ]
        
        table.add_row(*display_values)

        last_project = billing.get("project_id")
    
    console.print(table)


def format_tree_output(billing_info: List[Dict], date_range: Optional[Dict] = None) -> None:
    """
    GCP Billing 정보 목록을 트리 형식으로 출력합니다 (빌링 계정/서비스/프로젝트 계층).
    
    Args:
        billing_info: 빌링 정보 리스트
        date_range: 날짜 범위 정보 (선택적)
    """
    if not billing_info:
        console.print("[yellow]표시할 GCP Billing 정보가 없습니다.[/yellow]")
        return

    # 날짜 범위 정보 표시
    if date_range:
        start_date = date_range.get('start_date', 'N/A')
        end_date = date_range.get('end_date', 'N/A')
        console.print(f"[dim]Cost data for period: {start_date} to {end_date}[/dim]")
        console.print()

    # 빌링 계정별로 그룹화
    billing_accounts = {}
    for billing in billing_info:
        account_name = billing.get("billing_account_display_name", "Unknown")
        if account_name not in billing_accounts:
            billing_accounts[account_name] = []
        billing_accounts[account_name].append(billing)

    # 트리 구조 생성
    tree = Tree("💰 [bold blue]GCP Billing Information[/bold blue]")
    
    for account_name in sorted(billing_accounts.keys()):
        account_billings = billing_accounts[account_name]
        
        # 계정 상태 확인
        account_open = any(b.get('billing_account_open', False) for b in account_billings)
        account_icon = "🟢" if account_open else "🔴"
        
        # 총 비용 계산
        total_cost = sum(b.get('current_month_cost', 0.0) for b in account_billings)
        currency = account_billings[0].get('currency_code', 'USD') if account_billings else 'USD'
        
        account_node = tree.add(
            f"{account_icon} [bold cyan]{account_name}[/bold cyan] "
            f"({len(account_billings)} projects) - "
            f"Total: [green]{total_cost:.2f} {currency}[/green]"
        )
        
        # 서비스별로 비용 집계
        service_costs = {}
        for billing in account_billings:
            cost_by_service = billing.get('cost_by_service', {})
            for service_id, cost in cost_by_service.items():
                if cost > 0:
                    if service_id not in service_costs:
                        service_costs[service_id] = {'cost': 0.0, 'projects': set()}
                    service_costs[service_id]['cost'] += cost
                    service_costs[service_id]['projects'].add(billing.get('project_id', 'Unknown'))
        
        # 서비스별 비용 표시 (상위 5개)
        if service_costs:
            sorted_services = sorted(service_costs.items(), key=lambda x: x[1]['cost'], reverse=True)[:5]
            services_node = account_node.add("🔧 [bold yellow]Top Services by Cost[/bold yellow]")
            
            for service_id, service_data in sorted_services:
                service_cost = service_data['cost']
                project_count = len(service_data['projects'])
                services_node.add(
                    f"💸 {service_id}: [green]{service_cost:.2f} {currency}[/green] "
                    f"({project_count} projects)"
                )
        
        # 프로젝트별 상세 정보
        projects_node = account_node.add("📁 [bold magenta]Projects[/bold magenta]")
        
        for billing in sorted(account_billings, key=lambda x: x.get("project_id", "")):
            # 프로젝트 상태 아이콘
            billing_enabled = billing.get('billing_enabled', False)
            project_icon = "🟢" if billing_enabled else "🔴"
            
            # 프로젝트 정보
            project_id = billing.get("project_id", "N/A")
            project_cost = billing.get("current_month_cost", 0.0)
            
            project_info = (
                f"{project_icon} [bold white]{project_id}[/bold white] - "
                f"Cost: [green]{project_cost:.2f} {currency}[/green]"
            )
            
            project_node = projects_node.add(project_info)
            
            # 추가 세부 정보
            if not billing_enabled:
                project_node.add("⚠️  Billing Disabled")
            
            # 예산 정보 및 임계값 상태
            budgets = billing.get('budgets', [])
            if budgets:
                budget_node = project_node.add(f"📊 Budgets: {len(budgets)} configured")
                for budget in budgets[:3]:  # 상위 3개 예산만 표시
                    budget_name = budget.get('name', 'Unnamed Budget')
                    threshold = budget.get('threshold_amount', 0)
                    current_spend = budget.get('current_spend', 0)
                    
                    if current_spend > threshold:
                        status_icon = "🔴"
                        status_text = "Over Budget"
                    elif current_spend > threshold * 0.8:
                        status_icon = "🟡"
                        status_text = "Near Limit"
                    else:
                        status_icon = "🟢"
                        status_text = "Within Budget"
                    
                    budget_node.add(
                        f"{status_icon} {budget_name}: "
                        f"[green]{current_spend:.2f}[/green] / "
                        f"[cyan]{threshold:.2f} {currency}[/cyan] - {status_text}"
                    )
            
            # 서비스별 비용 (프로젝트 내)
            cost_by_service = billing.get('cost_by_service', {})
            if cost_by_service and any(cost > 0 for cost in cost_by_service.values()):
                # 비용이 있는 서비스만 표시
                costly_services = [(service, cost) for service, cost in cost_by_service.items() if cost > 0]
                if costly_services:
                    costly_services.sort(key=lambda x: x[1], reverse=True)
                    top_costly = costly_services[:3]  # 상위 3개만 표시
                    cost_text = ", ".join([f"{service}: {cost:.2f}" for service, cost in top_costly])
                    project_node.add(f"💸 Top Costs: {cost_text}")

    console.print(tree)


def format_output(billing_info: List[Dict], output_format: str = 'table', 
                 date_range: Optional[Dict] = None) -> str:
    """
    빌링 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        billing_info: 빌링 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
        date_range: 날짜 범위 정보 (선택적)
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(billing_info, date_range)
        return ""
    elif output_format == 'tree':
        format_tree_output(billing_info, date_range)
        return ""
    elif output_format == 'json':
        # JSON 출력에 날짜 범위 정보 포함
        output_data = {
            'date_range': date_range,
            'billing_info': billing_info
        }
        return format_gcp_output(output_data, 'json')
    elif output_format == 'yaml':
        # YAML 출력에 날짜 범위 정보 포함
        output_data = {
            'date_range': date_range,
            'billing_info': billing_info
        }
        return format_gcp_output(output_data, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(billing_info, date_range)
        return ""


def main(args):
    """
    메인 함수 - GCP Billing 정보를 조회하고 출력합니다.
    
    Args:
        args: CLI 인자 객체
    """
    try:
        log_info("GCP Billing 정보 조회 시작")
        
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
        
        # 병렬로 빌링 정보 수집
        all_billing_info = resource_collector.parallel_collect(
            projects, 
            fetch_billing_info
        )
        
        if not all_billing_info:
            console.print("[yellow]조회된 Billing 정보가 없습니다.[/yellow]")
            return
        
        # 필터 적용
        filters = {}
        if hasattr(args, 'billing_account') and args.billing_account:
            filters['billing_account'] = args.billing_account
        if hasattr(args, 'project') and args.project:
            filters['project'] = args.project
        
        filtered_billing_info = resource_collector.apply_filters(all_billing_info, filters)
        
        # 날짜 범위 처리
        date_range = None
        if hasattr(args, 'start_date') and args.start_date:
            date_range = {'start_date': args.start_date}
            if hasattr(args, 'end_date') and args.end_date:
                date_range['end_date'] = args.end_date
            else:
                # 종료 날짜가 없으면 현재 날짜 사용
                date_range['end_date'] = datetime.now().strftime('%Y-%m-%d')
        
        # 출력 형식 결정
        output_format = getattr(args, 'output', 'table')
        
        # 결과 출력
        if output_format in ['json', 'yaml']:
            output_text = format_output(filtered_billing_info, output_format, date_range)
            console.print(output_text)
        else:
            format_output(filtered_billing_info, output_format, date_range)
        
        log_info(f"총 {len(filtered_billing_info)}개 빌링 정보 조회 완료")
        
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
        '-b', '--billing-account', 
        help='빌링 계정 이름으로 필터링 (부분 일치)'
    )
    parser.add_argument(
        '--start-date',
        help='비용 조회 시작 날짜 (YYYY-MM-DD 형식)'
    )
    parser.add_argument(
        '--end-date',
        help='비용 조회 종료 날짜 (YYYY-MM-DD 형식)'
    )
    parser.add_argument(
        '-o', '--output', 
        choices=['table', 'tree', 'json', 'yaml'],
        default='table',
        help='출력 형식 선택 (기본값: table)'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Billing 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)