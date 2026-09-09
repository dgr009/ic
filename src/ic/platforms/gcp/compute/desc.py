#!/usr/bin/env python3
"""
GCP Compute Engine Detailed Resource Inspection (desc) Command.
Enables full attribute discovery, dot-notation key filtering, and schema inspection.
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
from ic.platforms.gcp.compute.info import (
    GCP_COMPUTE_AVAILABLE,
    InstancesClient,
    AggregatedListInstancesRequest,
    ListInstancesRequest,
    collect_instance_details,
    load_mock_data,
)

console = Console()


def compute_instance_to_dict(inst: Any) -> Dict[str, Any]:
    """Convert GCP Compute Instance model to a clean dictionary."""
    if isinstance(inst, dict):
        return dict(inst)
    if hasattr(inst, "_pb"):
        try:
            from google.protobuf.json_format import MessageToDict
            return MessageToDict(inst._pb, preserving_proto_field_name=True)
        except Exception:
            pass
    if hasattr(type(inst), "to_dict") and callable(getattr(type(inst), "to_dict")):
        try:
            return type(inst).to_dict(inst)
        except Exception:
            pass
    if hasattr(inst, "to_dict") and callable(getattr(inst, "to_dict")):
        try:
            return inst.to_dict()
        except Exception:
            pass
    if hasattr(inst, "__dict__"):
        return {k: v for k, v in inst.__dict__.items() if not k.startswith("_")}
    return {}


def fetch_raw_compute_instances_one_project(
    project_id: str,
    zone_filter: Optional[str] = None,
    region_filter: Optional[str] = None,
    name_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch raw Compute Engine instances for a project."""
    log_info_non_console(f"[GCP Compute desc] 수집 시작: project={project_id}")
    if not GCP_COMPUTE_AVAILABLE:
        return []

    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []

        instances_client = InstancesClient(credentials=credentials)
        instances: List[Dict[str, Any]] = []

        pager = None
        if hasattr(instances_client, "aggregated_list"):
            try:
                if AggregatedListInstancesRequest:
                    req = AggregatedListInstancesRequest(project=project_id)
                    pager = instances_client.aggregated_list(request=req)
                else:
                    pager = instances_client.aggregated_list(project=project_id)
                iter(pager)
            except (TypeError, AttributeError):
                pager = None

        if pager is not None:
            for location, scoped_list in pager:
                instances_seq = getattr(scoped_list, "instances", None)
                if not instances_seq:
                    continue

                zone_name = location.split("/")[-1]
                if zone_filter and zone_filter.lower() not in zone_name.lower():
                    continue

                if region_filter:
                    reg_clean = region_filter.lower().strip()
                    zone_region = zone_name.rsplit("-", 1)[0] if "-" in zone_name else zone_name
                    if reg_clean not in zone_name.lower() and reg_clean not in zone_region.lower():
                        continue

                for instance in instances_seq:
                    try:
                        raw_dict = compute_instance_to_dict(instance)
                        inst_name = raw_dict.get("name") or getattr(instance, "name", "")
                        inst_id = str(raw_dict.get("id") or getattr(instance, "id", ""))

                        if name_filter:
                            patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                            if patterns and not any(p in inst_name.lower() or p in inst_id.lower() for p in patterns):
                                continue

                        detailed = collect_instance_details(instances_client, project_id, zone_name, instance) or {}
                        merged = {**detailed, **raw_dict}
                        merged["name"] = inst_name
                        merged["id"] = inst_id
                        merged["project_id"] = project_id
                        merged["zone"] = zone_name
                        merged["_account_name"] = project_id
                        merged["_region"] = zone_name
                        instances.append(merged)
                    except Exception as e:
                        log_error(f"인스턴스 수집 중 오류: {getattr(instance, 'name', 'unknown')}, Error={e}")
        elif hasattr(instances_client, "list"):
            target_zone = zone_filter or "us-central1-a"
            try:
                req = ListInstancesRequest(project=project_id, zone=target_zone) if ListInstancesRequest else None
                instances_seq = instances_client.list(request=req) if req else instances_client.list(project=project_id, zone=target_zone)
                for instance in instances_seq:
                    raw_dict = compute_instance_to_dict(instance)
                    inst_name = raw_dict.get("name") or getattr(instance, "name", "")
                    inst_id = str(raw_dict.get("id") or getattr(instance, "id", ""))
                    if name_filter:
                        patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                        if patterns and not any(p in inst_name.lower() or p in inst_id.lower() for p in patterns):
                            continue
                    detailed = collect_instance_details(instances_client, project_id, target_zone, instance) or {}
                    merged = {**detailed, **raw_dict}
                    merged["name"] = inst_name
                    merged["id"] = inst_id
                    merged["project_id"] = project_id
                    merged["zone"] = target_zone
                    merged["_account_name"] = project_id
                    merged["_region"] = target_zone
                    instances.append(merged)
            except Exception as e:
                log_error(f"instances_client.list fallback 오류: {e}")

        return instances
    except Exception as e:
        log_error(f"Compute Engine 인스턴스 조회 실패: {project_id}, Error={e}")
        return []


class GcpComputeDescCommand(BaseCommand):
    """
    GCP Compute Engine detailed inspection command.
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
            help="리전으로 필터링 (콤마 구분 가능, 예: asia-northeast3)"
        )
        parser.add_argument(
            "-z", "--zone", "--zones",
            dest="zone",
            help="존으로 필터링 (예: asia-northeast3-a)"
        )
        parser.add_argument(
            "-n", "--name",
            dest="name",
            help="인스턴스 이름 또는 ID 필터 (콤마 구분 가능, 부분 일치, 예: web,api)"
        )
        parser.add_argument(
            "-k", "--keys", "-f", "--fields",
            dest="keys",
            help="조회할 상세 속성 키 목록 (콤마 구분, 점 표기법 지원, 예: machine_type,status,disks.0.device_name)"
        )
        parser.add_argument(
            "-l", "--list-keys",
            dest="list_keys",
            nargs="?",
            const=True,
            default=False,
            help="조회 가능한 모든 상세 속성 키 목록 표시 (키워드로 필터링 가능, 예: -l disk)"
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
            raw_instances = load_mock_data()
            filtered: List[Dict[str, Any]] = []
            name_filter = getattr(args, "name", None)
            proj_filter = getattr(args, "project", None)
            zone_filter = getattr(args, "zone", None)
            reg_filter = getattr(args, "region", None)

            name_patterns = [p.strip().lower() for p in name_filter.split(",")] if name_filter else []
            proj_patterns = [p.strip().lower() for p in proj_filter.split(",")] if proj_filter else []

            for inst in raw_instances:
                inst_name = str(inst.get("name", "")).lower()
                inst_id = str(inst.get("id", "")).lower()
                inst_proj = str(inst.get("project_id", "")).lower()
                inst_zone = str(inst.get("zone", "")).lower()

                if name_patterns and not any(p in inst_name or p in inst_id for p in name_patterns):
                    continue
                if proj_patterns and not any(p in inst_proj for p in proj_patterns):
                    continue
                if zone_filter and zone_filter.lower() not in inst_zone:
                    continue
                if reg_filter and reg_filter.lower() not in inst_zone:
                    continue

                inst_copy = dict(inst)
                inst_copy["_account_name"] = inst.get("project_id")
                inst_copy["_region"] = inst.get("zone")
                filtered.append(inst_copy)

            all_instances = filtered
        else:
            # 2. Live GCP API Execution
            if not GCP_COMPUTE_AVAILABLE:
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

            all_instances = []
            max_workers = min(len(projects), 10) or 1
            with ManualProgress("Collecting detailed GCP Compute instances", total=len(projects)) as progress:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(
                            fetch_raw_compute_instances_one_project,
                            proj,
                            getattr(args, "zone", None),
                            getattr(args, "region", None),
                            getattr(args, "name", None),
                        ): proj
                        for proj in projects
                    }

                    for f in as_completed(futures):
                        proj = futures[f]
                        try:
                            res = f.result()
                            all_instances.extend(res)
                            progress.update(f"Processed {proj} - Found {len(res)} instances", advance=1)
                        except Exception as e:
                            progress.update(f"Failed {proj} - {str(e)[:40]}", advance=1)

        # Output branch 1: --list-keys
        if list_keys:
            def render_keys(*a: Any, **kw: Any) -> None:
                if not all_instances:
                    console.print("[yellow]⚠️  No GCP Compute instances found to inspect keys.[/yellow]")
                    return
                filter_arg = list_keys if isinstance(list_keys, str) else None
                render_keys_list(all_instances, "GCP Compute Instance", key_filter=filter_arg)

            return CommandResult(data=[], table_renderer=render_keys)

        # Output branch 2: -k / --keys filter
        key_list = [k.strip() for k in keys_arg.split(",") if k.strip()] if keys_arg else []
        if key_list:
            filtered_data: List[Dict[str, Any]] = []
            for inst in all_instances:
                item: Dict[str, Any] = {
                    "name": inst.get("name"),
                    "id": inst.get("id"),
                    "_account_name": inst.get("_account_name") or inst.get("project_id"),
                    "_region": inst.get("_region") or inst.get("zone"),
                }
                item.update(extract_filtered_attributes(inst, key_list))
                filtered_data.append(item)

            def render_filtered_ui(*a: Any, **kw: Any) -> None:
                if not all_instances:
                    console.print("[yellow]⚠️  일치하는 GCP Compute 인스턴스가 없습니다.[/yellow]")
                    return
                render_filtered_table(all_instances, key_list, name_field="name", id_field="id")

            return CommandResult(data=filtered_data, table_renderer=render_filtered_ui)

        # Output branch 3: Full detailed YAML dump
        def render_full_yaml(*a: Any, **kw: Any) -> None:
            if not all_instances:
                console.print("[yellow]⚠️  일치하는 GCP Compute 인스턴스가 없습니다.[/yellow]")
                return

            clean_data = [safe_serialize(inst) for inst in all_instances]
            yaml_str = yaml.dump(clean_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
            try:
                syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
                console.print(syntax)
            except Exception:
                console.print(yaml_str)

        return CommandResult(data=all_instances, table_renderer=render_full_yaml)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    GcpComputeDescCommand.add_arguments(parser)


def main(args: argparse.Namespace, config: Optional[Any] = None) -> None:
    cmd = GcpComputeDescCommand()
    cmd.run(args, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Compute Engine Detailed Resource Inspection")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
