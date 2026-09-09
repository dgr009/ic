#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any

try:
    from google.cloud import dns  # type: ignore
    from google.api_core import exceptions as gcp_exceptions  # type: ignore
    GCP_DNS_AVAILABLE = True
except ImportError:
    GCP_DNS_AVAILABLE = False
    dns: Any = None
    gcp_exceptions: Any = None

from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from ic.core.interfaces import BaseCommand, CommandResult

from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector
)
from common.log import log_info, log_error, log_exception, log_info_non_console

console = Console()


def fetch_dns_zones_direct(project_id: str, zone_filter: Optional[str] = None) -> List[Dict]:
    """
    직접 Google Cloud DNS API를 통해 관리형 DNS 영역 및 레코드 정보를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        zone_filter: 영역 이름 필터 (선택사항)
    
    Returns:
        DNS 영역 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []

        client = dns.Client(project=project_id, credentials=credentials)
        zones = []

        for zone in client.list_zones():
            zone_name = zone.name
            if zone_filter and zone_filter.lower() not in zone_name.lower():
                continue

            records = []
            try:
                for record in zone.list_resource_record_sets():
                    records.append({
                        'name': record.name,
                        'type': record.record_type,
                        'ttl': record.ttl,
                        'rrdatas': list(record.rrdatas) if record.rrdatas else []
                    })
            except Exception as e:
                log_error(f"레코드 셋 조회 실패 (Zone: {zone_name}): {e}")

            visibility = "private" if getattr(zone, 'private_visibility_config', None) else "public"

            zone_data = {
                'project_id': project_id,
                'name': zone.name,
                'dns_name': zone.dns_name,
                'description': zone.description or '',
                'visibility': visibility,
                'record_count': len(records),
                'name_servers': list(zone.name_servers) if zone.name_servers else [],
                'records': records
            }
            zones.append(zone_data)

        log_info(f"프로젝트 {project_id}에서 {len(zones)}개 Cloud DNS 영역 발견")
        return zones

    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Cloud DNS 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Cloud DNS 영역 조회 실패: {project_id}, Error={e}")
        return []


def fetch_dns_zones(project_id: str, zone_filter: Optional[str] = None) -> List[Dict]:
    """Cloud DNS 영역 목록을 가져옵니다."""
    return fetch_dns_zones_direct(project_id, zone_filter)


def load_mock_data() -> List[Dict]:
    """mock_data.json에서 데이터를 로드합니다."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    mock_file = os.path.join(dir_path, 'mock_data.json')

    try:
        with open(mock_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[bold red]에러: Mock 데이터 파일을 찾을 수 없습니다: {mock_file}[/bold red]")
        return []
    except json.JSONDecodeError:
        console.print(f"[bold red]에러: Mock 데이터 파일의 형식이 올바르지 않습니다: {mock_file}[/bold red]")
        return []


def format_table_output(zones: List[Dict]) -> None:
    """
    GCP Cloud DNS 영역 목록을 Rich 테이블 형식으로 출력합니다.
    """
    if not zones:
        console.print("[yellow]표시할 GCP Cloud DNS 영역 정보가 없습니다.[/yellow]")
        return

    zones_sorted = sorted(zones, key=lambda x: (x.get("project_id", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.add_column("Project", style="bold magenta")
    table.add_column("Zone Name", style="bold white")
    table.add_column("DNS Name", style="bold cyan")
    table.add_column("Visibility", justify="center")
    table.add_column("Records", justify="right", style="blue")
    table.add_column("Name Servers", style="dim")
    table.add_column("Description", style="dim")

    last_project = None
    for i, zone in enumerate(zones_sorted):
        project_changed = zone.get("project_id") != last_project
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", end_section=True)

        visibility = zone.get("visibility", "public")
        if visibility == "public":
            vis_colored = "[green]public[/green]"
        else:
            vis_colored = "[yellow]private[/yellow]"

        ns_list = zone.get("name_servers", [])
        ns_str = ", ".join(ns_list[:2])
        if len(ns_list) > 2:
            ns_str += f" (+{len(ns_list) - 2})"

        table.add_row(
            zone.get("project_id", "") if project_changed else "",
            zone.get("name", "N/A"),
            zone.get("dns_name", "N/A"),
            vis_colored,
            str(zone.get("record_count", 0)),
            ns_str or "-",
            zone.get("description", "-")
        )
        last_project = zone.get("project_id")

    console.print(table)


def format_tree_output(zones: List[Dict]) -> None:
    """
    GCP Cloud DNS 영역 및 레코드를 트리 계층으로 출력합니다.
    """
    if not zones:
        console.print("[yellow]표시할 GCP Cloud DNS 정보가 없습니다.[/yellow]")
        return

    projects: Dict[str, List[Dict]] = {}
    for zone in zones:
        pid = zone.get("project_id", "unknown")
        if pid not in projects:
            projects[pid] = []
        projects[pid].append(zone)

    tree = Tree("🌐 [bold blue]GCP Cloud DNS Zones[/bold blue]")

    for project_id in sorted(projects.keys()):
        proj_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        for zone in sorted(projects[project_id], key=lambda x: x.get("name", "")):
            visibility = zone.get("visibility", "public")
            vis_icon = "🌍" if visibility == "public" else "🔒"
            zone_node = proj_node.add(
                f"{vis_icon} [bold white]{zone.get('name')}[/bold white] "
                f"([cyan]{zone.get('dns_name')}[/cyan]) - {visibility.upper()}"
            )

            records = zone.get("records", [])
            for r in records:
                rrdata_str = ", ".join(r.get("rrdatas", []))
                zone_node.add(
                    f"📝 [bold yellow]{r.get('type')}[/bold yellow] "
                    f"[white]{r.get('name')}[/white] "
                    f"(TTL: {r.get('ttl')}s) -> [dim]{rrdata_str}[/dim]"
                )

    console.print(tree)


def format_paste_output(zones: List[Dict]) -> None:
    """Cloud DNS 영역 목록을 -p (paste) 모드용 CSV로 출력합니다."""
    for z in zones:
        ns_str = ";".join(z.get('name_servers', []))
        row = [
            z.get('project_id', '-'),
            z.get('name', '-'),
            z.get('dns_name', '-'),
            z.get('visibility', '-'),
            str(z.get('record_count', 0)),
            ns_str or '-',
        ]
        print(",".join(str(c) for c in row))


class GcpDnsInfoCommand(BaseCommand):
    """GCP Cloud DNS 영역 및 레코드 정보 조회 커맨드"""

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
            '-n', '--name', '-z', '--zone',
            dest='zone',
            help='관리형 DNS 영역 이름으로 필터링 (콤마 구분 가능, 부분 일치)'
        )
        parser.add_argument(
            '-d', '--dns-name',
            help='도메인/DNS 이름으로 필터링 (예: example.com.)'
        )
        parser.add_argument(
            '-t', '--type',
            help='DNS 레코드 타입으로 필터링 (예: A, CNAME, TXT)'
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
            zones = load_mock_data()
            filtered = []
            proj_filter = getattr(args, 'project', None)
            zone_filter = getattr(args, 'zone', None)
            dns_name_filter = getattr(args, 'dns_name', None)
            type_filter = getattr(args, 'type', None)

            proj_patterns = [p.strip().lower() for p in proj_filter.split(',')] if proj_filter else []
            zone_patterns = [p.strip().lower() for p in zone_filter.split(',')] if zone_filter else []

            for z in zones:
                z_proj = str(z.get('project_id', '')).lower()
                z_name = str(z.get('name', '')).lower()

                if proj_patterns and not any(p in z_proj for p in proj_patterns):
                    continue
                if zone_patterns and not any(p in z_name for p in zone_patterns):
                    continue
                if dns_name_filter and dns_name_filter.lower() not in str(z.get('dns_name', '')).lower():
                    continue
                if type_filter:
                    records = z.get('records', [])
                    if not any(r.get('type') == type_filter.upper() for r in records):
                        continue
                filtered.append(z)
            return CommandResult(
                data=filtered,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )

        if not GCP_DNS_AVAILABLE:
            console.print("[red]❌ google-cloud-dns 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   pip install 'ic-cli[gcp]' 또는 pip install google-cloud-dns[/yellow]")
            console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
            return CommandResult(data=[], error="google-cloud-dns is not installed", success=False)

        try:
            log_info_non_console("GCP Cloud DNS 영역 조회 시작")
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
                console.print("💡 [dim]--project <PROJECT_ID> 옵션을 지정하거나 활성 gcloud 프로필을 설정하세요. (전체 조회를 원하시면 --all-projects 옵션을 사용하세요)[/dim]")
                return CommandResult(data=[], table_renderer=format_table_output, tree_renderer=format_tree_output, paste_renderer=format_paste_output)

            all_zones = resource_collector.parallel_collect(
                projects,
                fetch_dns_zones,
                getattr(args, 'zone', None)
            )

            filters = {}
            if getattr(args, 'project', None):
                filters['project'] = args.project
            if getattr(args, 'dns_name', None):
                filters['dns_name'] = args.dns_name

            filtered_zones = resource_collector.apply_filters(all_zones, filters)

            if getattr(args, 'type', None):
                type_filter = args.type.upper()
                type_filtered = []
                for z in filtered_zones:
                    matched_records = [
                        r for r in z.get('records', [])
                        if r.get('type', '').upper() == type_filter
                    ]
                    if matched_records:
                        z_copy = dict(z)
                        z_copy['records'] = matched_records
                        z_copy['record_count'] = len(matched_records)
                        type_filtered.append(z_copy)
                filtered_zones = type_filtered

            return CommandResult(
                data=filtered_zones,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )
        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpDnsInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpDnsInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Cloud DNS 영역 및 레코드 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
