#!/usr/bin/env python3
import argparse
import json
from typing import Dict, List, Any
from pathlib import Path

try:
    from google.cloud.resourcemanager_v3 import ProjectsClient, FoldersClient, OrganizationsClient
    from google.cloud.resourcemanager_v3.types import SearchProjectsRequest
    from google.api_core import exceptions as gcp_exceptions
    GCP_PROJECTS_AVAILABLE = True
except ImportError:
    GCP_PROJECTS_AVAILABLE = False
    ProjectsClient: Any = None
    FoldersClient: Any = None
    OrganizationsClient: Any = None
    SearchProjectsRequest: Any = None
    gcp_exceptions: Any = None

from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from common.gcp_utils import GCPAuthManager
from common.log import log_info_non_console, log_error, log_exception
from ic.core.interfaces import BaseCommand, CommandResult

console = Console()

# 폴더 및 조직 이름 캐시 (반복 API 호출 방지)
_FOLDER_CACHE: Dict[str, Dict[str, Any]] = {}
_ORG_CACHE: Dict[str, str] = {}


def load_mock_data() -> List[Dict[str, Any]]:
    """mock_data.json에서 프로젝트 데이터를 로드합니다."""
    mock_file = Path(__file__).parent / "mock_data.json"
    try:
        with open(mock_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Mock 데이터 로드 실패: {e}")
        return []


def resolve_parent_path(parent_id: str, credentials) -> str:
    """
    folders/123 or organizations/456 을 받아서
    재귀적으로 'OrgName / Folder1 / Folder2' 형태의 계층 경로를 만듭니다.
    """
    if not parent_id or parent_id == "-":
        return "No Hierarchy"

    if parent_id in _FOLDER_CACHE:
        return _FOLDER_CACHE[parent_id]["full_path"]

    # 만약 organization인 경우
    if parent_id.startswith("organizations/"):
        if parent_id in _ORG_CACHE:
            return _ORG_CACHE[parent_id]
        if OrganizationsClient and credentials:
            try:
                org_client = OrganizationsClient(credentials=credentials)
                org = org_client.get_organization(name=parent_id)
                name = org.display_name or parent_id
                _ORG_CACHE[parent_id] = name
                return name
            except Exception:
                pass
        _ORG_CACHE[parent_id] = parent_id
        return parent_id

    # 만약 folder인 경우
    if parent_id.startswith("folders/"):
        if FoldersClient and credentials:
            try:
                folders_client = FoldersClient(credentials=credentials)
                folder = folders_client.get_folder(name=parent_id)
                display_name = folder.display_name or parent_id
                parent_parent = folder.parent
                if parent_parent:
                    parent_full = resolve_parent_path(parent_parent, credentials)
                    full_path = f"{parent_full} / {display_name}"
                else:
                    full_path = display_name
                _FOLDER_CACHE[parent_id] = {
                    "display_name": display_name,
                    "parent": parent_parent,
                    "full_path": full_path
                }
                return full_path
            except Exception:
                pass
        _FOLDER_CACHE[parent_id] = {
            "display_name": parent_id,
            "parent": None,
            "full_path": parent_id
        }
        return parent_id

    return parent_id


def fetch_projects_direct(auth_manager: GCPAuthManager, include_all: bool = False) -> List[Dict[str, Any]]:
    """
    Direct API를 통해 GCP 프로젝트 목록 및 상위 폴더 계층을 조회합니다.
    """
    credentials = auth_manager.get_credentials()
    if not credentials:
        log_error("GCP 인증 정보를 가져올 수 없습니다.")
        return []

    active_project_id = auth_manager.get_default_project_id()
    projects: List[Dict[str, Any]] = []

    try:
        client = ProjectsClient(credentials=credentials)
        query = "" if include_all else "lifecycleState:ACTIVE"
        request = SearchProjectsRequest(query=query)

        for p in client.search_projects(request=request):
            project_id = p.project_id
            project_number = p.name.split("/")[-1] if "/" in p.name else p.name
            state = p.state.name if hasattr(p.state, "name") else str(p.state)
            create_time_str = "-"
            if hasattr(p, "create_time") and p.create_time:
                try:
                    dt = getattr(p.create_time, "ToDatetime", lambda: getattr(p, "create_time"))()
                    create_time_str = getattr(dt, "strftime", lambda fmt: str(dt))("%Y-%m-%d %H:%M:%S")
                except Exception:
                    create_time_str = str(p.create_time)

            parent_id = p.parent or "-"
            folder_path = resolve_parent_path(parent_id, credentials)

            is_active = (project_id == active_project_id)

            projects.append({
                "project_id": project_id,
                "name": p.display_name or project_id,
                "project_number": project_number,
                "state": state,
                "parent": parent_id,
                "folder_path": folder_path,
                "create_time": create_time_str,
                "is_active": is_active,
                "labels": dict(p.labels) if p.labels else {}
            })

    except gcp_exceptions.PermissionDenied:
        log_error("GCP 프로젝트 목록을 조회할 권한(resourcemanager.projects.get / search)이 부족합니다.")
        if active_project_id:
            projects.append({
                "project_id": active_project_id,
                "name": active_project_id,
                "project_number": "-",
                "state": "ACTIVE",
                "parent": "-",
                "folder_path": "Active Project",
                "create_time": "-",
                "is_active": True,
                "labels": {}
            })
    except Exception as e:
        log_error(f"GCP 프로젝트 조회 실패: {e}")

    # 폴더 경로 및 프로젝트 ID 순으로 정렬
    projects.sort(key=lambda x: (x.get("folder_path", ""), not x.get("is_active", False), x.get("project_id", "")))
    log_info_non_console(f"GCP 프로젝트 조회 완료: 총 {len(projects)}개")
    return projects


def format_table_output(projects: List[Dict[str, Any]], verbose: bool = False) -> None:
    """GCP 프로젝트 목록을 상위 폴더 계층별로 그룹화된 Rich 테이블 형식으로 출력합니다."""
    if not projects:
        console.print("[yellow]표시할 GCP 프로젝트 정보가 없습니다.[/yellow]")
        return

    # 폴더 계층 순서대로 정렬
    projects_sorted = sorted(
        projects,
        key=lambda x: (x.get("folder_path", ""), not x.get("is_active", False), x.get("project_id", ""))
    )

    table = Table(title="🏢 GCP Projects (Hierarchical View)", title_style="bold blue", box=box.ROUNDED, expand=False)
    table.add_column("Active", justify="center", style="bold", no_wrap=True)
    table.add_column("Hierarchy / Folder Path", style="bold cyan")
    table.add_column("Project ID", style="bold yellow")
    table.add_column("Project Name", style="bold white")
    table.add_column("Project Number", style="dim white")
    table.add_column("State", justify="center")

    if verbose:
        table.add_column("Parent ID", style="dim")
        table.add_column("Created", style="dim")
        table.add_column("Labels", style="dim")

    last_folder = None
    unique_folders = set()

    for i, p in enumerate(projects_sorted):
        folder = p.get("folder_path") or p.get("parent") or "No Hierarchy"
        unique_folders.add(folder)
        folder_changed = (folder != last_folder)

        # 폴더 그룹이 변경될 때 섹션 구분선 추가
        if i > 0 and folder_changed:
            table.add_row("", "", "", "", "", "", end_section=True)

        is_active = p.get("is_active", False)
        active_mark = "[bold green]●[/bold green]" if is_active else "[dim]○[/dim]"

        pid = p.get("project_id", "-")
        pid_styled = f"[bold underline green]{pid}[/bold underline green]" if is_active else f"[bold yellow]{pid}[/bold yellow]"

        state = p.get("state", "UNKNOWN")
        if state == "ACTIVE":
            state_colored = "[green]ACTIVE[/green]"
        elif state == "DELETE_REQUESTED":
            state_colored = "[red]DELETING[/red]"
        else:
            state_colored = f"[yellow]{state}[/yellow]"

        display_folder = f"📁 [bold]{folder}[/bold]" if folder_changed else ""

        row = [
            active_mark,
            display_folder,
            pid_styled,
            p.get("name", "-"),
            str(p.get("project_number", "-")),
            state_colored,
        ]

        if verbose:
            labels_dict = p.get("labels", {})
            labels_str = ", ".join(f"{k}={v}" for k, v in labels_dict.items()) if labels_dict else "-"
            row.extend([
                p.get("parent", "-"),
                str(p.get("create_time", "-")),
                labels_str
            ])

        table.add_row(*row)
        last_folder = folder

    console.print(table)

    # 요약 정보 출력
    active_proj = next((p for p in projects if p.get("is_active")), None)
    if active_proj:
        active_path = active_proj.get("folder_path") or "No Hierarchy"
        console.print(
            f"🎯 [bold]Active Project:[/bold] [bold green]{active_proj.get('project_id')}[/bold green] "
            f"(Name: {active_proj.get('name')}, Folder: [cyan]{active_path}[/cyan])"
        )
    else:
        console.print("💡 [dim]현재 활성화된 기본 프로젝트가 지정되지 않았습니다.[/dim]")
    console.print(f"📊 [dim]Total Projects: {len(projects)} across {len(unique_folders)} Folder/Hierarchy groups[/dim]")


def format_tree_output(projects: List[Dict[str, Any]]) -> None:
    """GCP 프로젝트 목록을 조직/폴더의 실제 깊이(Depth) 계층 트리로 출력합니다."""
    if not projects:
        console.print("[yellow]표시할 GCP 프로젝트 정보가 없습니다.[/yellow]")
        return

    root_tree = Tree("🏢 [bold blue]Google Cloud Resource Hierarchy[/bold blue]")

    # 폴더 계층 파싱 및 트리 생성 (e.g. 'Organization / Platform / Service / Live')
    # node_registry: path_tuple -> tree_node
    node_registry: Dict[tuple, Any] = {}

    for p in sorted(projects, key=lambda x: (x.get("folder_path", ""), not x.get("is_active", False), x.get("project_id", ""))):
        folder_path = p.get("folder_path") or p.get("parent") or "No Hierarchy"
        parts = [part.strip() for part in folder_path.split("/") if part.strip()]

        current_node = root_tree
        current_path = []
        for depth, part in enumerate(parts):
            current_path.append(part)
            path_key = tuple(current_path)
            if path_key not in node_registry:
                icon = "🏛️" if depth == 0 else "📁"
                node_registry[path_key] = current_node.add(f"{icon} [bold cyan]{part}[/bold cyan]")
            current_node = node_registry[path_key]

        # 프로젝트 노드 추가
        is_active = p.get("is_active", False)
        icon = "🟢" if is_active else "⚪"
        active_suffix = " [bold green](ACTIVE)[/bold green]" if is_active else ""
        pid_style = "[bold green]" if is_active else "[bold white]"
        
        proj_line = (
            f"{icon} {pid_style}{p.get('project_id')}[/]{active_suffix} "
            f"- Name: [dim]{p.get('name')}[/dim], Number: [dim]{p.get('project_number')}[/dim], "
            f"State: {p.get('state')}"
        )
        p_node = current_node.add(proj_line)
        if p.get("labels"):
            lbl_text = ", ".join(f"{k}={v}" for k, v in p["labels"].items())
            p_node.add(f"🏷️  [dim]Labels: {lbl_text}[/dim]")

    console.print(root_tree)


def format_paste_output(projects: List[Dict[str, Any]]) -> None:
    """프로젝트 목록을 -p (paste) 모드용 CSV로 출력합니다."""
    for p in projects:
        row = [
            p.get("folder_path", "-"),
            p.get("project_id", "-"),
            p.get("name", "-"),
            str(p.get("project_number", "-")),
            p.get("state", "-"),
            str(p.get("is_active", False)),
        ]
        print(",".join(str(c) for c in row))


class GcpProjectInfoCommand(BaseCommand):
    """GCP 프로젝트 목록 및 활성 프로젝트 조회 커맨드"""

    @classmethod
    def add_arguments(cls, parser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            "-p", "--project",
            help="프로젝트 ID 또는 이름으로 필터링 (부분 일치)"
        )
        parser.add_argument(
            "-f", "--folder",
            help="상위 폴더 이름 또는 경로로 필터링 (부분 일치, 예: service, live)"
        )
        parser.add_argument(
            "--prefix",
            help="프로젝트 ID 접두어로 필터링 (예: prod-, dev-)"
        )
        parser.add_argument(
            "-s", "--state",
            help="프로젝트 수명 주기 상태로 필터링 (예: ACTIVE, DELETE_REQUESTED)"
        )
        parser.add_argument(
            "--tree",
            action="store_true",
            help="조직 및 다단계 폴더 계층을 트리(Tree) 구조로 출력"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="삭제 대기 중인 프로젝트를 포함하여 전체 프로젝트 조회"
        )
        parser.add_argument(
            "-v", "--verbose",
            action="store_true",
            help="상세 정보 출력 (Parent ID, 생성일, 라벨 등)"
        )
        parser.add_argument(
            "--paste",
            action="store_true",
            help="스프레드시트 복사용 콤마(,) 구분 텍스트 출력"
        )
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Mock 데이터를 사용하여 오프라인으로 실행"
        )

    def execute(self, args, config=None) -> CommandResult:
        verbose = getattr(args, "verbose", False)
        tree_mode = getattr(args, "tree", False)

        def _table_render(data, verbose_flag=verbose):
            if tree_mode:
                format_tree_output(data)
            else:
                format_table_output(data, verbose=verbose_flag)

        if getattr(args, "mock", False):
            projects = load_mock_data()
            filtered = []
            proj_filter = getattr(args, "project", None)
            folder_filter = getattr(args, "folder", None)
            prefix_filter = getattr(args, "prefix", None)
            state_filter = getattr(args, "state", None)
            include_all = getattr(args, "all", False)

            for p in projects:
                if not include_all and p.get("state") != "ACTIVE":
                    continue
                if proj_filter:
                    term = proj_filter.lower()
                    if term not in str(p.get("project_id", "")).lower() and term not in str(p.get("name", "")).lower():
                        continue
                if folder_filter:
                    term = folder_filter.lower()
                    if term not in str(p.get("folder_path", "")).lower() and term not in str(p.get("parent", "")).lower():
                        continue
                if prefix_filter:
                    if not str(p.get("project_id", "")).startswith(prefix_filter):
                        continue
                if state_filter and state_filter.lower() not in str(p.get("state", "")).lower():
                    continue
                filtered.append(p)

            return CommandResult(
                data=filtered,
                table_renderer=_table_render,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
                success=True,
                metadata={"total_count": len(filtered), "mock": True}
            )

        if not GCP_PROJECTS_AVAILABLE:
            console.print("[red]❌ google-cloud-resource-manager 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   pip install google-cloud-resource-manager[/yellow]")
            return CommandResult(data=[], error="google-cloud-resource-manager not installed", success=False)

        try:
            auth_manager = GCPAuthManager()
            if not auth_manager.validate_credentials():
                console.print("[bold red]GCP 인증에 실패했습니다. gcloud auth login 또는 ADC를 확인하세요.[/bold red]")
                return CommandResult(data=[], error="GCP authentication failed", success=False)

            include_all = getattr(args, "all", False)
            projects = fetch_projects_direct(auth_manager, include_all=include_all)

            filtered = []
            proj_filter = getattr(args, "project", None)
            folder_filter = getattr(args, "folder", None)
            prefix_filter = getattr(args, "prefix", None)
            state_filter = getattr(args, "state", None)

            for p in projects:
                if proj_filter:
                    term = proj_filter.lower()
                    if term not in str(p.get("project_id", "")).lower() and term not in str(p.get("name", "")).lower():
                        continue
                if folder_filter:
                    term = folder_filter.lower()
                    if term not in str(p.get("folder_path", "")).lower() and term not in str(p.get("parent", "")).lower():
                        continue
                if prefix_filter:
                    if not str(p.get("project_id", "")).startswith(prefix_filter):
                        continue
                if state_filter and state_filter.lower() not in str(p.get("state", "")).lower():
                    continue
                filtered.append(p)

            return CommandResult(
                data=filtered,
                table_renderer=_table_render,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
                success=True,
                metadata={"total_count": len(filtered)}
            )

        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpProjectInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpProjectInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP 프로젝트 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
