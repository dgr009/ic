#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
# Using google-cloud-sql-python-connector for Cloud SQL connections
try:
    from google.cloud.sql.connector import Connector  # type: ignore
    CONNECTOR_AVAILABLE = True
except ImportError:
    CONNECTOR_AVAILABLE = False
    Connector: Any = None
try:
    from google.cloud.sql_v1 import SqlInstancesServiceClient, SqlDatabasesServiceClient  # type: ignore
    from google.cloud.sql_v1.types import (  # type: ignore
        SqlInstancesListRequest, SqlInstancesGetRequest,
        SqlDatabasesListRequest, SqlDatabasesGetRequest
    )
    SQL_ADMIN_AVAILABLE = True
except ImportError:
    SQL_ADMIN_AVAILABLE = False
    SqlInstancesServiceClient: Any = None
    SqlDatabasesServiceClient: Any = None
    SqlInstancesListRequest: Any = None
    SqlInstancesGetRequest: Any = None
    SqlDatabasesListRequest: Any = None
    SqlDatabasesGetRequest: Any = None
try:
    from google.api_core import exceptions as gcp_exceptions
except ImportError:
    gcp_exceptions: Any = None
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    format_gcp_output
)
from common.log import log_info, log_error, log_exception, log_info_non_console
from ic.core.interfaces import BaseCommand, CommandResult

console = Console()


def fetch_sql_instances_direct(project_id: str) -> List[Dict]:
    """
    직접 API를 통해 GCP Cloud SQL 인스턴스를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
    
    Returns:
        Cloud SQL 인스턴스 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        sql_client = SqlInstancesServiceClient(credentials=credentials)
        databases_client = SqlDatabasesServiceClient(credentials=credentials)
        
        all_instances = []
        
        try:
            # 프로젝트의 모든 SQL 인스턴스 가져오기
            request = SqlInstancesListRequest(project=project_id)
            response = sql_client.list(request=request)
            
            for instance in response.items:
                instance_data = collect_instance_details(
                    sql_client, databases_client, project_id, instance
                )
                if instance_data:
                    all_instances.append(instance_data)
                    
        except gcp_exceptions.Forbidden:
            log_error(f"프로젝트 {project_id}에 대한 Cloud SQL 접근 권한이 없습니다")
            return []
        except Exception as e:
            log_error(f"Cloud SQL 인스턴스 조회 실패: {project_id}, Error={e}")
            return []
        
        log_info(f"프로젝트 {project_id}에서 {len(all_instances)}개 Cloud SQL 인스턴스 발견")
        return all_instances
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Cloud SQL 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Cloud SQL 인스턴스 조회 실패: {project_id}, Error={e}")
        return []


def fetch_sql_instances(project_id: str) -> List[Dict]:
    """
    GCP Cloud SQL 인스턴스를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
    
    Returns:
        Cloud SQL 인스턴스 정보 리스트
    """
    return fetch_sql_instances_direct(project_id)


def collect_instance_details(sql_client: Any, 
                           databases_client: Any,
                           project_id: str, instance) -> Optional[Dict]:
    """
    SQL 인스턴스의 상세 정보를 수집합니다.
    
    Args:
        sql_client: Cloud SQL 인스턴스 클라이언트
        databases_client: Cloud SQL 데이터베이스 클라이언트
        project_id: GCP 프로젝트 ID
        instance: SQL 인스턴스 객체
    
    Returns:
        SQL 인스턴스 상세 정보 딕셔너리
    """
    try:
        # 기본 인스턴스 정보
        instance_data = {
            'project_id': project_id,
            'name': instance.name,
            'database_version': instance.database_version,
            'region': instance.region,
            'tier': instance.settings.tier if instance.settings else 'N/A',
            'state': instance.state.name if hasattr(instance.state, 'name') else str(instance.state),
            'creation_time': instance.create_time,
            'master_instance_name': instance.master_instance_name or None,
            'backend_type': instance.backend_type.name if hasattr(instance.backend_type, 'name') else str(instance.backend_type),
            'instance_type': instance.instance_type.name if hasattr(instance.instance_type, 'name') else str(instance.instance_type),
            'connection_name': instance.connection_name,
            'gce_zone': instance.gce_zone,
            'service_account_email': instance.service_account_email_address,
            'settings': {},
            'ip_addresses': [],
            'server_ca_cert': {},
            'replica_names': list(instance.replica_names) if instance.replica_names else [],
            'failover_replica': instance.failover_replica,
            'databases': [],
            'backup_configuration': {},
            'maintenance_window': {},
            'database_flags': {}
        }
        
        settings_data: Dict[str, Any] = {}
        backup_config_data: Dict[str, Any] = {}
        ip_addresses_list: List[Dict[str, Any]] = []
        databases_list: List[Dict[str, Any]] = []

        # 설정 정보
        if instance.settings:
            settings = instance.settings
            settings_data = {
                'tier': settings.tier,
                'pricing_plan': settings.pricing_plan.name if hasattr(settings.pricing_plan, 'name') else str(settings.pricing_plan),
                'replication_type': settings.replication_type.name if hasattr(settings.replication_type, 'name') else str(settings.replication_type),
                'activation_policy': settings.activation_policy.name if hasattr(settings.activation_policy, 'name') else str(settings.activation_policy),
                'storage_auto_resize': settings.storage_auto_resize,
                'storage_auto_resize_limit': settings.storage_auto_resize_limit,
                'data_disk_size_gb': settings.data_disk_size_gb,
                'data_disk_type': settings.data_disk_type.name if hasattr(settings.data_disk_type, 'name') else str(settings.data_disk_type),
                'availability_type': settings.availability_type.name if hasattr(settings.availability_type, 'name') else str(settings.availability_type),
                'crash_safe_replication': settings.crash_safe_replication_enabled,
                'location_preference': {}
            }
            
            # 위치 선호도
            if settings.location_preference:
                settings_data['location_preference'] = {
                    'zone': settings.location_preference.zone,
                    'follow_gae_application': settings.location_preference.follow_gae_application
                }
            
            # 백업 설정
            if settings.backup_configuration:
                backup_config = settings.backup_configuration
                backup_config_data = {
                    'enabled': backup_config.enabled,
                    'start_time': backup_config.start_time,
                    'binary_log_enabled': backup_config.binary_log_enabled,
                    'location': backup_config.location,
                    'point_in_time_recovery_enabled': backup_config.point_in_time_recovery_enabled,
                    'transaction_log_retention_days': backup_config.transaction_log_retention_days,
                    'backup_retention_settings': {}
                }
                
                if backup_config.backup_retention_settings:
                    backup_config_data['backup_retention_settings'] = {
                        'retention_unit': backup_config.backup_retention_settings.retention_unit.name if hasattr(backup_config.backup_retention_settings.retention_unit, 'name') else str(backup_config.backup_retention_settings.retention_unit),
                        'retained_backups': backup_config.backup_retention_settings.retained_backups
                    }
            
            # 유지보수 창
            if settings.maintenance_window:
                maintenance = settings.maintenance_window
                instance_data['maintenance_window'] = {
                    'hour': maintenance.hour,
                    'day': maintenance.day,
                    'update_track': maintenance.update_track.name if hasattr(maintenance.update_track, 'name') else str(maintenance.update_track)
                }
            
            # 데이터베이스 플래그
            if settings.database_flags:
                instance_data['database_flags'] = {
                    flag.name: flag.value for flag in settings.database_flags
                }
        
        instance_data['settings'] = settings_data
        instance_data['backup_configuration'] = backup_config_data

        # IP 주소 정보
        if instance.ip_addresses:
            for ip_addr in instance.ip_addresses:
                ip_info = {
                    'type': ip_addr.type_.name if hasattr(ip_addr.type_, 'name') else str(ip_addr.type_),
                    'ip_address': ip_addr.ip_address,
                    'time_to_retire': ip_addr.time_to_retire
                }
                ip_addresses_list.append(ip_info)
        
        instance_data['ip_addresses'] = ip_addresses_list

        # 서버 CA 인증서
        if instance.server_ca_cert:
            instance_data['server_ca_cert'] = {
                'kind': instance.server_ca_cert.kind,
                'cert_serial_number': instance.server_ca_cert.cert_serial_number,
                'cert': instance.server_ca_cert.cert,
                'create_time': instance.server_ca_cert.create_time,
                'common_name': instance.server_ca_cert.common_name,
                'sha1_fingerprint': instance.server_ca_cert.sha1_fingerprint,
                'instance': instance.server_ca_cert.instance
            }
        
        # 데이터베이스 목록 수집
        try:
            db_request = SqlDatabasesListRequest(
                project=project_id,
                instance=instance.name
            )
            databases_response = databases_client.list(request=db_request)
            
            for database in databases_response.items:
                db_info = {
                    'name': database.name,
                    'charset': database.charset,
                    'collation': database.collation,
                    'instance': database.instance,
                    'self_link': database.self_link
                }
                databases_list.append(db_info)
                
        except Exception as e:
            log_error(f"데이터베이스 목록 수집 실패: {instance.name}, Error={e}")
        
        instance_data['databases'] = databases_list

        # 편의를 위한 추가 필드
        instance_data['primary_ip'] = (
            ip_addresses_list[0]['ip_address'] 
            if ip_addresses_list else 'N/A'
        )
        instance_data['high_availability'] = (
            settings_data.get('availability_type') == 'REGIONAL'
        )
        instance_data['backup_enabled'] = (
            backup_config_data.get('enabled', False)
        )
        
        return instance_data
        
    except Exception as e:
        log_error(f"SQL 인스턴스 상세 정보 수집 실패: {instance.name}, Error={e}")
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


def format_table_output(instances: List[Dict]) -> None:
    """
    GCP Cloud SQL 인스턴스 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        instances: SQL 인스턴스 정보 리스트
    """
    if not instances:
        console.print("[yellow]표시할 GCP Cloud SQL 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 이름 순으로 정렬
    instances.sort(key=lambda x: (x.get("project_id", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Instance Name", style="bold white")
    table.add_column("DB Version", style="bold cyan")
    table.add_column("Region", style="dim")
    table.add_column("Tier", style="dim")
    table.add_column("State", justify="center")
    table.add_column("HA", justify="center")
    table.add_column("Backup", justify="center")
    table.add_column("IP Address", style="blue")
    table.add_column("Databases", justify="center", style="green")

    last_project = None
    
    for i, instance in enumerate(instances):
        project_changed = instance.get("project_id") != last_project

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", "", end_section=True)

        # 상태에 따른 색상 적용
        state = instance.get('state', 'N/A')
        if state == "RUNNABLE":
            state_colored = f"[green]{state}[/green]"
        elif state in ["STOPPED", "SUSPENDED"]:
            state_colored = f"[red]{state}[/red]"
        elif state in ["PENDING_CREATE", "MAINTENANCE"]:
            state_colored = f"[yellow]{state}[/yellow]"
        else:
            state_colored = f"[dim]{state}[/dim]"
        
        # HA 상태
        ha_enabled = instance.get('high_availability', False)
        ha_status = "✓" if ha_enabled else "✗"
        ha_colored = f"[green]{ha_status}[/green]" if ha_enabled else f"[red]{ha_status}[/red]"
        
        # 백업 상태
        backup_enabled = instance.get('backup_enabled', False)
        backup_status = "✓" if backup_enabled else "✗"
        backup_colored = f"[green]{backup_status}[/green]" if backup_enabled else f"[red]{backup_status}[/red]"
        
        # 데이터베이스 수
        db_count = len(instance.get('databases', []))
        db_count_str = str(db_count) if db_count > 0 else "-"
        
        display_values = [
            instance.get("project_id", "") if project_changed else "",
            instance.get("name", "N/A"),
            instance.get("database_version", "N/A"),
            instance.get("region", "N/A"),
            instance.get("tier", "N/A"),
            state_colored,
            ha_colored,
            backup_colored,
            instance.get("primary_ip", "N/A"),
            db_count_str
        ]
        
        table.add_row(*display_values)

        last_project = instance.get("project_id")
    
    console.print(table)


def format_tree_output(instances: List[Dict]) -> None:
    """
    GCP Cloud SQL 인스턴스 목록을 트리 형식으로 출력합니다 (프로젝트/지역 계층).
    
    Args:
        instances: SQL 인스턴스 정보 리스트
    """
    if not instances:
        console.print("[yellow]표시할 GCP Cloud SQL 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for instance in instances:
        project_id = instance.get("project_id", "unknown")
        region = instance.get("region", "unknown")
        
        if project_id not in projects:
            projects[project_id] = {}
        if region not in projects[project_id]:
            projects[project_id][region] = []
        
        projects[project_id][region].append(instance)

    # 트리 구조 생성
    tree = Tree("🗄️ [bold blue]GCP Cloud SQL Instances[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        
        for region in sorted(projects[project_id].keys()):
            region_instances = projects[project_id][region]
            region_node = project_node.add(
                f"🌍 [bold cyan]{region}[/bold cyan] ({len(region_instances)} instances)"
            )
            
            for instance in sorted(region_instances, key=lambda x: x.get("name", "")):
                # 상태 아이콘
                state = instance.get('state', 'N/A')
                if state == "RUNNABLE":
                    state_icon = "🟢"
                elif state in ["STOPPED", "SUSPENDED"]:
                    state_icon = "🔴"
                elif state in ["PENDING_CREATE", "MAINTENANCE"]:
                    state_icon = "🟡"
                else:
                    state_icon = "⚪"
                
                # 인스턴스 정보
                instance_name = instance.get("name", "N/A")
                db_version = instance.get("database_version", "N/A")
                tier = instance.get("tier", "N/A")
                primary_ip = instance.get("primary_ip", "N/A")
                
                instance_info = (
                    f"{state_icon} [bold white]{instance_name}[/bold white] "
                    f"({db_version}, {tier}) - "
                    f"IP: [blue]{primary_ip}[/blue]"
                )
                
                instance_node = region_node.add(instance_info)
                
                # 추가 세부 정보
                if instance.get('high_availability'):
                    instance_node.add("🔄 High Availability: Enabled")
                
                if instance.get('backup_enabled'):
                    backup_config = instance.get('backup_configuration', {})
                    start_time = backup_config.get('start_time', 'N/A')
                    instance_node.add(f"💾 Backup: Enabled (Start: {start_time})")
                
                databases = instance.get('databases', [])
                if databases:
                    db_names = [db['name'] if isinstance(db, dict) else str(db) for db in databases]
                    instance_node.add(f"🗃️  Databases: {', '.join(db_names)}")
                
                if instance.get('replica_names'):
                    replica_count = len(instance['replica_names'])
                    instance_node.add(f"🔄 Read Replicas: {replica_count}")
                
                maintenance = instance.get('maintenance_window', {})
                if maintenance.get('hour') is not None:
                    day = maintenance.get('day', 'N/A')
                    hour = maintenance.get('hour', 'N/A')
                    instance_node.add(f"🔧 Maintenance: Day {day}, Hour {hour}")

    console.print(tree)


def format_output(instances: List[Dict], output_format: str = 'table') -> str:
    """
    SQL 인스턴스 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        instances: SQL 인스턴스 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(instances)
        return ""
    elif output_format == 'tree':
        format_tree_output(instances)
        return ""
    elif output_format == 'json':
        return format_gcp_output(instances, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(instances, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(instances)
        return ""


def format_paste_output(instances: List[Dict]) -> None:
    """SQL 인스턴스 목록을 -p (paste) 모드용 CSV로 출력합니다."""
    for inst in instances:
        row = [
            inst.get('project_id', '-'),
            inst.get('region', '-'),
            inst.get('name', '-'),
            inst.get('state', '-'),
            inst.get('database_version', '-'),
            inst.get('tier', '-'),
            inst.get('ip_address', '-'),
        ]
        print(",".join(str(c) for c in row))


class GcpSqlInfoCommand(BaseCommand):
    """GCP Cloud SQL 인스턴스 정보 조회 커맨드"""

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
            '-n', '--name', '-i', '--instance',
            dest='instance',
            help='SQL 인스턴스 이름으로 필터링 (콤마 구분 가능, 부분 일치)'
        )
        parser.add_argument(
            '-r', '--region', '--regions',
            dest='region',
            help='지역으로 필터링 (콤마 구분 가능, 예: us-central1)'
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
            instances = load_mock_data()
            filtered = []
            inst_filter = getattr(args, 'instance', None)
            proj_filter = getattr(args, 'project', None)
            reg_filter = getattr(args, 'region', None)

            inst_patterns = [p.strip().lower() for p in inst_filter.split(',')] if inst_filter else []
            proj_patterns = [p.strip().lower() for p in proj_filter.split(',')] if proj_filter else []

            for inst in instances:
                inst_name = str(inst.get('name', '')).lower()
                inst_proj = str(inst.get('project_id', '')).lower()
                inst_reg = str(inst.get('region', '')).lower()

                if inst_patterns and not any(p in inst_name for p in inst_patterns):
                    continue
                if proj_patterns and not any(p in inst_proj for p in proj_patterns):
                    continue
                if reg_filter and reg_filter.lower() not in inst_reg:
                    continue
                filtered.append(inst)
            return CommandResult(
                data=filtered,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )

        if not SQL_ADMIN_AVAILABLE:
            console.print("[red]❌ google-cloud-sql-admin 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
            return CommandResult(data=[], error="google-cloud-sql-admin is not installed", success=False)

        try:
            log_info_non_console("GCP Cloud SQL 인스턴스 조회 시작")
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

            all_instances = resource_collector.parallel_collect(
                projects, 
                fetch_sql_instances
            )

            # Region & Name filtering
            if getattr(args, 'region', None):
                all_instances = [i for i in all_instances if getattr(args, 'region').lower() in str(i.get('region', '')).lower()]
            if getattr(args, 'instance', None):
                inst_patterns = [p.strip().lower() for p in args.instance.split(',') if p.strip()]
                all_instances = [
                    i for i in all_instances
                    if any(p in str(i.get('name', '')).lower() for p in inst_patterns)
                ]

            return CommandResult(
                data=all_instances,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )
        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpSqlInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpSqlInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Cloud SQL 인스턴스 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)