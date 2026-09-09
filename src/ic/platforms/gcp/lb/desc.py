#!/usr/bin/env python3
"""
GCP Load Balancer Detailed Resource Inspection (desc) Command.
Enables full attribute discovery, dot-notation key filtering, and schema inspection for GCP LBs,
including Target Proxies, URL Maps, Backend Services, Health Checks, and SSL Certificates.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.syntax import Syntax
import yaml  # type: ignore

from common.gcp_utils import (
    GCPAuthManager,
    GCPProjectManager,
)
from common.log import log_error, log_info_non_console
from common.progress_decorator import ManualProgress
from ic.core.desc_helper import (
    extract_filtered_attributes,
    render_filtered_table,
    render_keys_list,
)
from ic.core.interfaces.command import BaseCommand
from ic.core.interfaces.formatter import safe_serialize
from ic.core.interfaces.result import CommandResult
from ic.platforms.gcp.lb.info import (
    GCP_LB_AVAILABLE,
    fetch_load_balancers_direct,
    load_mock_data,
)

console = Console()


def fetch_raw_lb_one_project(
    project_id: str,
    region_filter: Optional[str] = None,
    name_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch raw GCP Load Balancers for a project."""
    log_info_non_console(f"[GCP LB desc] 수집 시작: project={project_id}")
    if not GCP_LB_AVAILABLE:
        return []

    try:
        lbs = fetch_load_balancers_direct(project_id, region_filter)
        results: List[Dict[str, Any]] = []

        name_patterns = [p.strip().lower() for p in name_filter.split(",")] if name_filter else []
        for lb in lbs:
            lb_name = str(lb.get("name", ""))
            lb_ip = str(lb.get("ip_address", ""))
            lb_type = str(lb.get("type", ""))

            if name_patterns and not any(p in lb_name.lower() or p in lb_ip.lower() for p in name_patterns):
                continue
            if type_filter and type_filter.upper() != lb_type.upper():
                continue

            lb_copy = dict(lb)
            lb_copy["_account_name"] = project_id
            lb_copy["_region"] = lb.get("scope", "global")
            results.append(lb_copy)

        return results
    except Exception as e:
        log_error(f"GCP Load Balancer 조회 실패: {project_id}, Error={e}")
        return []


class GcpLbDescCommand(BaseCommand):
    """
    GCP Load Balancer detailed inspection command.
    Supports full attribute dumping, dot-notation key filtering (-k), and queryable key discovery (-l).
    """

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            "-a", "--account", "--project",
            dest="project",
            help="GCP 프로젝트 ID 또는 계정 (콤마 구분으로 복수 지정 가능, 예: my-project-123)"
        )
        parser.add_argument(
            "--all-projects",
            action="store_true",
            help="접근 가능한 모든 GCP 프로젝트 조회 (대규모 환경 주의)"
        )
        parser.add_argument(
            "-r", "--region", "--regions",
            dest="region",
            help="리전으로 필터링 (예: us-central1, global)"
        )
        parser.add_argument(
            "-n", "--name", "--lb-name",
            dest="name",
            help="Load Balancer 이름 또는 IP 필터 (콤마 구분 가능, 부분 일치)"
        )
        parser.add_argument(
            "-t", "--lb-type",
            choices=["HTTP_HTTPS", "TCP_PROXY", "SSL_PROXY", "NETWORK_TCP_UDP", "INTERNAL_TCP_UDP", "INTERNAL_HTTP_HTTPS"],
            help="Load Balancer 타입으로 필터링"
        )
        parser.add_argument(
            "-k", "--keys", "-f", "--fields",
            dest="keys",
            help="조회할 상세 속성 키 목록 (콤마 구분, 점 표기법 지원, 예: type,ip_address,backend_services.0.name)"
        )
        parser.add_argument(
            "-l", "--list-keys",
            dest="list_keys",
            nargs="?",
            const=True,
            default=False,
            help="조회 가능한 모든 상세 속성 키 목록 표시 (키워드로 필터링 가능, 예: -l backend)"
        )
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Mock 데이터를 사용하여 오프라인으로 실행"
        )

    def execute(self, args: argparse.Namespace, config: Optional[Any] = None) -> CommandResult:
        list_keys = getattr(args, "list_keys", False)
        keys_arg = getattr(args, "keys", None)

        # 1. Mock Data Execution
        if getattr(args, "mock", False):
            raw_lbs = load_mock_data()
            filtered: List[Dict[str, Any]] = []
            name_filter = getattr(args, "name", None)
            proj_filter = getattr(args, "project", None)
            reg_filter = getattr(args, "region", None)
            type_filter = getattr(args, "lb_type", None)

            name_patterns = [p.strip().lower() for p in name_filter.split(",")] if name_filter else []
            proj_patterns = [p.strip().lower() for p in proj_filter.split(",")] if proj_filter else []

            for lb in raw_lbs:
                lb_name = str(lb.get("name", "")).lower()
                lb_ip = str(lb.get("ip_address", "")).lower()
                lb_proj = str(lb.get("project_id", "")).lower()
                lb_scope = str(lb.get("scope", "")).lower()
                lb_type = str(lb.get("type", "")).upper()

                if name_patterns and not any(p in lb_name or p in lb_ip for p in name_patterns):
                    continue
                if proj_patterns and not any(p in lb_proj for p in proj_patterns):
                    continue
                if reg_filter and reg_filter.lower() not in lb_scope:
                    continue
                if type_filter and type_filter.upper() != lb_type:
                    continue

                lb_copy = dict(lb)
                lb_copy["_account_name"] = lb.get("project_id")
                lb_copy["_region"] = lb.get("scope", "global")
                filtered.append(lb_copy)

            all_lbs = filtered
        else:
            # 2. Live GCP API Execution
            if not GCP_LB_AVAILABLE:
                console.print("[red]❌ google-cloud-compute 패키지가 설치되지 않았습니다.[/red]")
                console.print("[yellow]   pip install 'ic-cli[gcp]' 또는 pip install google-cloud-compute[/yellow]")
                console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
                return CommandResult(data=[], error="google-cloud-compute is not installed", success=False)

            auth_manager = GCPAuthManager()
            if not auth_manager.validate_credentials():
                console.print("[bold red]GCP 인증에 실패했습니다. 인증 정보를 확인해주세요.[/bold red]")
                console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
                return CommandResult(data=[], error="GCP authentication failed", success=False)

            project_manager = GCPProjectManager(auth_manager)
            if getattr(args, "project", None):
                projects = [p.strip() for p in args.project.split(",") if p.strip()]
            else:
                projects = project_manager.get_projects(all_projects=getattr(args, "all_projects", False))

            if not projects:
                console.print("[yellow]⚠️  GCP 프로젝트가 지정되지 않았습니다.[/yellow]")
                console.print("💡 [dim]-a/--project <PROJECT_ID> 옵션을 지정하거나 활성 gcloud 프로필을 설정하세요.[/dim]")
                return CommandResult(data=[], success=True)

            all_lbs = []
            max_workers = min(len(projects), 10) or 1
            with ManualProgress("Collecting detailed GCP Load Balancers", total=len(projects)) as progress:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(
                            fetch_raw_lb_one_project,
                            proj,
                            getattr(args, "region", None),
                            getattr(args, "name", None),
                            getattr(args, "lb_type", None),
                        ): proj
                        for proj in projects
                    }

                    for f in as_completed(futures):
                        proj = futures[f]
                        try:
                            res = f.result()
                            all_lbs.extend(res)
                            progress.update(f"Processed {proj} - Found {len(res)} LBs", advance=1)
                        except Exception as e:
                            progress.update(f"Failed {proj} - {str(e)[:40]}", advance=1)

        # Output branch 1: --list-keys
        if list_keys:
            def render_keys(*a: Any, **kw: Any) -> None:
                if not all_lbs:
                    console.print("[yellow]⚠️  No GCP Load Balancers found to inspect keys.[/yellow]")
                    return
                filter_arg = list_keys if isinstance(list_keys, str) else None
                render_keys_list(all_lbs, "GCP Load Balancer", key_filter=filter_arg)

            return CommandResult(data=[], table_renderer=render_keys)

        # Output branch 2: -k / --keys filter
        key_list = [k.strip() for k in keys_arg.split(",") if k.strip()] if keys_arg else []
        if key_list:
            filtered_data: List[Dict[str, Any]] = []
            for lb in all_lbs:
                item: Dict[str, Any] = {
                    "name": lb.get("name"),
                    "ip_address": lb.get("ip_address"),
                    "_account_name": lb.get("_account_name") or lb.get("project_id"),
                    "_region": lb.get("_region") or lb.get("scope"),
                }
                item.update(extract_filtered_attributes(lb, key_list))
                filtered_data.append(item)

            def render_filtered_ui(*a: Any, **kw: Any) -> None:
                if not all_lbs:
                    console.print("[yellow]⚠️  일치하는 GCP Load Balancer가 없습니다.[/yellow]")
                    return
                render_filtered_table(all_lbs, key_list, name_field="name", id_field="ip_address")

            return CommandResult(data=filtered_data, table_renderer=render_filtered_ui)

        # Output branch 3: Full detailed YAML dump
        def render_full_yaml(*a: Any, **kw: Any) -> None:
            if not all_lbs:
                console.print("[yellow]⚠️  일치하는 GCP Load Balancer가 없습니다.[/yellow]")
                return

            clean_data = [safe_serialize(lb) for lb in all_lbs]
            yaml_str = yaml.dump(clean_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
            try:
                syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
                console.print(syntax)
            except Exception:
                console.print(yaml_str)

        return CommandResult(data=all_lbs, table_renderer=render_full_yaml)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    GcpLbDescCommand.add_arguments(parser)


def main(args: argparse.Namespace, config: Optional[Any] = None) -> None:
    cmd = GcpLbDescCommand()
    cmd.run(args, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Load Balancer Detailed Resource Inspection")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
