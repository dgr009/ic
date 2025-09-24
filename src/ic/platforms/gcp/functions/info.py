#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
from google.cloud.functions_v1 import CloudFunctionsServiceClient
from google.cloud.functions_v1.types import ListFunctionsRequest, GetFunctionRequest
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


def fetch_functions_via_mcp(mcp_connector, project_id: str, region_filter: str = None) -> List[Dict]:
    """
    MCP 서버를 통해 GCP Cloud Functions를 가져옵니다.
    
    Args:
        mcp_connector: MCP GCP 커넥터
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        Cloud Functions 정보 리스트
    """
    try:
        params = {
            'project_id': project_id,
            'region_filter': region_filter
        }
        
        response = mcp_connector.execute_gcp_query('functions', 'list_functions', params)
        if response.success:
            return response.data.get('functions', [])
        else:
            log_error(f"MCP functions query failed: {response.error}")
            return []
            
    except Exception as e:
        log_error(f"MCP functions fetch failed: {e}")
        return []


def fetch_functions_direct(project_id: str, region_filter: str = None) -> List[Dict]:
    """
    직접 API를 통해 GCP Cloud Functions를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        Cloud Functions 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        functions_client = CloudFunctionsServiceClient(credentials=credentials)
        
        all_functions = []
        
        # 일반적인 GCP 지역 목록 (region_filter가 없는 경우)
        regions = [
            'us-central1', 'us-east1', 'us-east4', 'us-west1', 'us-west2', 'us-west3', 'us-west4',
            'europe-west1', 'europe-west2', 'europe-west3', 'europe-west4', 'europe-west6',
            'europe-central2', 'europe-north1',
            'asia-east1', 'asia-east2', 'asia-northeast1', 'asia-northeast2', 'asia-northeast3',
            'asia-south1', 'asia-southeast1', 'asia-southeast2',
            'australia-southeast1',
            'northamerica-northeast1', 'southamerica-east1'
        ]
        
        if region_filter:
            regions = [region_filter]
        
        for region in regions:
            try:
                # 해당 지역의 함수 가져오기
                parent = f"projects/{project_id}/locations/{region}"
                request = ListFunctionsRequest(parent=parent)
                
                response = functions_client.list_functions(request=request)
                
                for function in response:
                    function_data = collect_function_details(
                        functions_client, project_id, region, function
                    )
                    if function_data:
                        all_functions.append(function_data)
                        
            except gcp_exceptions.Forbidden:
                # 지역에 대한 접근 권한이 없는 경우 무시
                continue
            except gcp_exceptions.NotFound:
                # 지역에 함수가 없는 경우 무시
                continue
            except Exception as e:
                log_error(f"지역 {region}에서 함수 조회 실패: {project_id}, Error={e}")
                continue
        
        log_info(f"프로젝트 {project_id}에서 {len(all_functions)}개 Cloud Functions 발견")
        return all_functions
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Cloud Functions 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Cloud Functions 조회 실패: {project_id}, Error={e}")
        return []


def fetch_functions(project_id: str, region_filter: str = None) -> List[Dict]:
    """
    GCP Cloud Functions를 가져옵니다 (MCP 우선, 직접 API 폴백).
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        Cloud Functions 정보 리스트
    """
    # MCP 서비스 사용 시도
    if MCP_AVAILABLE:
        try:
            mcp_service = MCPGCPService('functions')
            return mcp_service.execute_with_fallback(
                'list_functions',
                {'project_id': project_id, 'region_filter': region_filter},
                lambda project_id, region_filter: fetch_functions_direct(project_id, region_filter)
            )
        except Exception as e:
            log_error(f"MCP service failed, using direct API: {e}")
    
    # 직접 API 사용
    return fetch_functions_direct(project_id, region_filter)


def collect_function_details(functions_client: CloudFunctionsServiceClient,
                           project_id: str, region: str, function) -> Optional[Dict]:
    """
    함수의 상세 정보를 수집합니다.
    
    Args:
        functions_client: Cloud Functions 클라이언트
        project_id: GCP 프로젝트 ID
        region: 지역
        function: 함수 객체
    
    Returns:
        함수 상세 정보 딕셔너리
    """
    try:
        # 기본 함수 정보
        function_data = {
            'project_id': project_id,
            'name': function.name.split('/')[-1],  # projects/PROJECT/locations/REGION/functions/NAME -> NAME
            'full_name': function.name,
            'region': region,
            'description': function.description or '',
            'status': function.status.name if hasattr(function.status, 'name') else str(function.status),
            'entry_point': function.entry_point,
            'runtime': function.runtime,
            'timeout': function.timeout.seconds if function.timeout else 0,
            'available_memory_mb': function.available_memory_mb,
            'max_instances': function.max_instances,
            'min_instances': function.min_instances,
            'vpc_connector': function.vpc_connector,
            'vpc_connector_egress_settings': function.vpc_connector_egress_settings.name if hasattr(function.vpc_connector_egress_settings, 'name') else str(function.vpc_connector_egress_settings),
            'ingress_settings': function.ingress_settings.name if hasattr(function.ingress_settings, 'name') else str(function.ingress_settings),
            'kms_key_name': function.kms_key_name,
            'build_id': function.build_id,
            'build_name': function.build_name,
            'source_archive_url': function.source_archive_url,
            'source_repository': {},
            'source_upload_url': function.source_upload_url,
            'environment_variables': dict(function.environment_variables) if function.environment_variables else {},
            'build_environment_variables': dict(function.build_environment_variables) if function.build_environment_variables else {},
            'labels': dict(function.labels) if function.labels else {},
            'event_trigger': {},
            'https_trigger': {},
            'service_account_email': function.service_account_email,
            'update_time': function.update_time,
            'version_id': function.version_id,
            'docker_registry': function.docker_registry.name if hasattr(function.docker_registry, 'name') else str(function.docker_registry),
            'docker_repository': function.docker_repository
        }
        
        # 소스 저장소 정보
        if function.source_repository:
            function_data['source_repository'] = {
                'url': function.source_repository.url,
                'deployed_url': function.source_repository.deployed_url
            }
        
        # 이벤트 트리거 정보
        if function.event_trigger:
            trigger = function.event_trigger
            function_data['event_trigger'] = {
                'event_type': trigger.event_type,
                'resource': trigger.resource,
                'service': trigger.service,
                'failure_policy': {}
            }
            
            if trigger.failure_policy:
                function_data['event_trigger']['failure_policy'] = {
                    'retry': trigger.failure_policy.retry is not None
                }
        
        # HTTPS 트리거 정보
        if function.https_trigger:
            trigger = function.https_trigger
            function_data['https_trigger'] = {
                'url': trigger.url,
                'security_level': trigger.security_level.name if hasattr(trigger.security_level, 'name') else str(trigger.security_level)
            }
        
        # 편의를 위한 추가 필드
        function_data['trigger_type'] = 'HTTP' if function.https_trigger else 'Event' if function.event_trigger else 'Unknown'
        function_data['memory_mb'] = function_data['available_memory_mb']
        function_data['timeout_seconds'] = function_data['timeout']
        function_data['env_var_count'] = len(function_data['environment_variables'])
        
        return function_data
        
    except Exception as e:
        log_error(f"함수 상세 정보 수집 실패: {function.name}, Error={e}")
        return None


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


def format_table_output(functions: List[Dict]) -> None:
    """
    GCP Cloud Functions 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        functions: 함수 정보 리스트
    """
    if not functions:
        console.print("[yellow]표시할 GCP Cloud Functions 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 지역, 이름 순으로 정렬
    functions.sort(key=lambda x: (x.get("project_id", ""), x.get("region", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Function Name", style="bold white")
    table.add_column("Runtime", style="dim")
    table.add_column("Trigger", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Memory", justify="right", style="blue")
    table.add_column("Timeout", justify="right", style="green")
    table.add_column("Env Vars", justify="center", style="dim")

    last_project = None
    last_region = None
    
    for i, function in enumerate(functions):
        project_changed = function.get("project_id") != last_project
        region_changed = function.get("region") != last_region

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", end_section=True)

        # 상태에 따른 색상 적용
        status = function.get('status', 'N/A')
        if status == "ACTIVE":
            status_colored = f"[green]{status}[/green]"
        elif status in ["OFFLINE", "DEPLOY_IN_PROGRESS"]:
            status_colored = f"[yellow]{status}[/yellow]"
        elif status in ["CLOUD_FUNCTION_STATUS_UNSPECIFIED", "DELETE_IN_PROGRESS"]:
            status_colored = f"[red]{status}[/red]"
        else:
            status_colored = f"[dim]{status}[/dim]"
        
        # 트리거 타입
        trigger_type = function.get('trigger_type', 'Unknown')
        if trigger_type == 'HTTP':
            trigger_colored = f"[green]{trigger_type}[/green]"
        elif trigger_type == 'Event':
            trigger_colored = f"[blue]{trigger_type}[/blue]"
        else:
            trigger_colored = f"[dim]{trigger_type}[/dim]"
        
        # 메모리 포맷팅
        memory_mb = function.get('memory_mb', 0)
        memory_str = f"{memory_mb} MB" if memory_mb > 0 else "N/A"
        
        # 타임아웃 포맷팅
        timeout_seconds = function.get('timeout_seconds', 0)
        if timeout_seconds >= 60:
            timeout_str = f"{timeout_seconds // 60}m {timeout_seconds % 60}s"
        else:
            timeout_str = f"{timeout_seconds}s" if timeout_seconds > 0 else "N/A"
        
        # 환경 변수 수
        env_var_count = function.get('env_var_count', 0)
        env_var_str = str(env_var_count) if env_var_count > 0 else "-"
        
        display_values = [
            function.get("project_id", "") if project_changed else "",
            function.get("region", "") if project_changed or region_changed else "",
            function.get("name", "N/A"),
            function.get("runtime", "N/A"),
            trigger_colored,
            status_colored,
            memory_str,
            timeout_str,
            env_var_str
        ]
        
        table.add_row(*display_values)

        last_project = function.get("project_id")
        last_region = function.get("region")
    
    console.print(table)


def format_tree_output(functions: List[Dict]) -> None:
    """
    GCP Cloud Functions 목록을 트리 형식으로 출력합니다 (프로젝트/지역 계층).
    
    Args:
        functions: 함수 정보 리스트
    """
    if not functions:
        console.print("[yellow]표시할 GCP Cloud Functions 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for function in functions:
        project_id = function.get("project_id", "unknown")
        region = function.get("region", "unknown")
        
        if project_id not in projects:
            projects[project_id] = {}
        if region not in projects[project_id]:
            projects[project_id][region] = []
        
        projects[project_id][region].append(function)

    # 트리 구조 생성
    tree = Tree("⚡ [bold blue]GCP Cloud Functions[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        
        for region in sorted(projects[project_id].keys()):
            region_functions = projects[project_id][region]
            region_node = project_node.add(
                f"🌍 [bold cyan]{region}[/bold cyan] ({len(region_functions)} functions)"
            )
            
            for function in sorted(region_functions, key=lambda x: x.get("name", "")):
                # 상태 아이콘
                status = function.get('status', 'N/A')
                if status == "ACTIVE":
                    status_icon = "🟢"
                elif status in ["OFFLINE", "DEPLOY_IN_PROGRESS"]:
                    status_icon = "🟡"
                elif status in ["CLOUD_FUNCTION_STATUS_UNSPECIFIED", "DELETE_IN_PROGRESS"]:
                    status_icon = "🔴"
                else:
                    status_icon = "⚪"
                
                # 트리거 아이콘
                trigger_type = function.get('trigger_type', 'Unknown')
                if trigger_type == 'HTTP':
                    trigger_icon = "🌐"
                elif trigger_type == 'Event':
                    trigger_icon = "📡"
                else:
                    trigger_icon = "❓"
                
                # 함수 정보
                function_name = function.get("name", "N/A")
                runtime = function.get("runtime", "N/A")
                memory_mb = function.get("memory_mb", 0)
                timeout_seconds = function.get("timeout_seconds", 0)
                
                function_info = (
                    f"{status_icon} {trigger_icon} [bold white]{function_name}[/bold white] "
                    f"({runtime}) - "
                    f"Memory: [blue]{memory_mb}MB[/blue], "
                    f"Timeout: [green]{timeout_seconds}s[/green]"
                )
                
                function_node = region_node.add(function_info)
                
                # 추가 세부 정보
                if function.get('entry_point'):
                    function_node.add(f"🎯 Entry Point: {function['entry_point']}")
                
                if function.get('https_trigger', {}).get('url'):
                    url = function['https_trigger']['url']
                    function_node.add(f"🔗 URL: {url}")
                
                if function.get('event_trigger', {}).get('event_type'):
                    event_type = function['event_trigger']['event_type']
                    resource = function['event_trigger'].get('resource', 'N/A')
                    function_node.add(f"📡 Event: {event_type} ({resource})")
                
                env_vars = function.get('environment_variables', {})
                if env_vars:
                    env_count = len(env_vars)
                    function_node.add(f"🔧 Environment Variables: {env_count}")
                
                if function.get('labels'):
                    labels_text = ", ".join([f"{k}={v}" for k, v in function['labels'].items()])
                    function_node.add(f"🏷️  Labels: {labels_text}")
                
                if function.get('service_account_email'):
                    function_node.add(f"👤 Service Account: {function['service_account_email']}")

    console.print(tree)


def format_output(functions: List[Dict], output_format: str = 'table') -> str:
    """
    함수 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        functions: 함수 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(functions)
        return ""
    elif output_format == 'tree':
        format_tree_output(functions)
        return ""
    elif output_format == 'json':
        return format_gcp_output(functions, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(functions, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(functions)
        return ""


def main(args):
    """
    메인 함수 - GCP Cloud Functions 정보를 조회하고 출력합니다.
    
    Args:
        args: CLI 인자 객체
    """
    try:
        log_info("GCP Cloud Functions 조회 시작")
        
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
        
        # 병렬로 함수 수집
        all_functions = resource_collector.parallel_collect(
            projects, 
            fetch_functions,
            getattr(args, 'region', None)
        )
        
        if not all_functions:
            console.print("[yellow]조회된 Cloud Functions가 없습니다.[/yellow]")
            return
        
        # 필터 적용
        filters = {}
        if hasattr(args, 'function') and args.function:
            filters['name'] = args.function
        if hasattr(args, 'project') and args.project:
            filters['project'] = args.project
        if hasattr(args, 'region') and args.region:
            filters['region'] = args.region
        
        filtered_functions = resource_collector.apply_filters(all_functions, filters)
        
        # 출력 형식 결정
        output_format = getattr(args, 'output', 'table')
        
        # 결과 출력
        if output_format in ['json', 'yaml']:
            output_text = format_output(filtered_functions, output_format)
            console.print(output_text)
        else:
            format_output(filtered_functions, output_format)
        
        log_info(f"총 {len(filtered_functions)}개 함수 조회 완료")
        
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
        '-f', '--function', 
        help='함수 이름으로 필터링 (부분 일치)'
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
    parser = argparse.ArgumentParser(description="GCP Cloud Functions 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)