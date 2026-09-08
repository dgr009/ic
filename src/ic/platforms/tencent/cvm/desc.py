#!/usr/bin/env python3
"""
Tencent CVM Detailed Resource Inspection (desc) Command.
Enables full attribute discovery, dot-notation key filtering, and schema inspection.
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.syntax import Syntax
import yaml  # type: ignore

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from ic.core.interfaces.command import BaseCommand
from ic.core.interfaces.formatter import safe_serialize
from ic.core.interfaces.result import CommandResult
from ic.core.desc_helper import (
    extract_filtered_attributes,
    render_keys_list,
    render_filtered_table,
)
from ic.platforms.tencent.client import (
    get_accounts, get_credential_for_account, get_tencent_regions,
    make_client_profile, check_sdk_available, TENCENT_SDK_AVAILABLE
)

console = Console()


def cvm_instance_to_dict(inst: Any) -> Dict[str, Any]:
    """Convert Tencent CVM model to a clean dictionary."""
    if isinstance(inst, dict):
        return inst
    if hasattr(inst, "to_json_string") and callable(getattr(inst, "to_json_string")):
        try:
            return json.loads(inst.to_json_string())
        except Exception:
            pass
    if hasattr(inst, "to_dict") and callable(getattr(inst, "to_dict")):
        return inst.to_dict()
    if hasattr(inst, "__dict__"):
        return {k: v for k, v in inst.__dict__.items() if not k.startswith("_")}
    return {}


def fetch_raw_cvm_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    """Fetch raw CVM instance dictionaries for an account and region."""
    account_id = account.get("id", "unknown")
    account_name = account.get("name", account_id)

    log_info_non_console(f"[CVM desc] 수집 시작: account={account_name}, region={region}")
    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.cvm.v20170312 import cvm_client, models
    except ImportError:
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    instances: List[Dict[str, Any]] = []
    try:
        client = cvm_client.CvmClient(cred, region, make_client_profile())
        offset = 0
        limit = 100

        while True:
            req = models.DescribeInstancesRequest()
            req.Offset = offset
            req.Limit = limit

            resp = client.DescribeInstances(req)
            batch = resp.InstanceSet or []

            for inst in batch:
                inst_dict = cvm_instance_to_dict(inst)
                state = inst_dict.get("InstanceState") or ""
                if state.upper() == "TERMINATED":
                    continue

                inst_name = inst_dict.get("InstanceName") or inst_dict.get("InstanceId") or "-"

                if name_filter:
                    patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                    if patterns and not any(p in inst_name.lower() or p in (inst_dict.get("InstanceId") or "").lower() for p in patterns):
                        continue

                inst_dict["InstanceName"] = inst_name
                inst_dict["_account_name"] = account_name
                inst_dict["_region"] = region
                instances.append(inst_dict)

            offset += len(batch)
            if offset >= (resp.TotalCount or 0) or len(batch) < limit:
                break
    except Exception as e:
        log_info_non_console(f"[CVM desc] 오류 ({account_name}/{region}): {e}")

    return instances


class TencentCvmDescCommand(BaseCommand):
    """
    Tencent Cloud CVM detailed inspection command.
    Supports full attribute dumping, key filtering (-k), and queryable key discovery (-l).
    """

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
        parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
        parser.add_argument("-n", "--name", help="CVM 이름/ID 필터 (콤마 구분)")
        parser.add_argument(
            "-k", "--keys", "-f", "--fields",
            help="조회할 상세 속성 키 목록 (콤마 구분, 점 표기법 지원, 예: ImageId,Placement.Zone,SystemDisk.DiskSize)"
        )
        parser.add_argument(
            "-l", "--list-keys",
            nargs="?",
            const=True,
            default=False,
            help="조회 가능한 모든 상세 속성 키 목록 표시 (키워드로 필터링 가능, 예: -l disk)"
        )
        cls.add_common_arguments(parser)

    def execute(self, args: argparse.Namespace, config: Optional[Any] = None) -> CommandResult:
        check_sdk_available()
        accounts = get_accounts(getattr(args, "account", None))
        regions = get_tencent_regions(getattr(args, "regions", None))
        name_filter = getattr(args, "name", None)
        keys_arg = getattr(args, "keys", None)
        list_keys = getattr(args, "list_keys", False)

        total_ops = len(accounts) * len(regions)
        all_instances: List[Dict[str, Any]] = []

        with ManualProgress("Collecting detailed CVM instances", total=total_ops) as progress:
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {}
                for acct in accounts:
                    acct_name = acct.get("name", acct.get("id"))
                    for reg in regions:
                        f = executor.submit(fetch_raw_cvm_one_account_region, acct, reg, name_filter)
                        futures[f] = (acct_name, reg)

                for f in as_completed(futures):
                    acct_name, reg = futures[f]
                    try:
                        res = f.result()
                        all_instances.extend(res)
                        progress.update(f"Processed {acct_name}/{reg} - Found {len(res)} instances", advance=1)
                    except Exception as e:
                        progress.update(f"Failed {acct_name}/{reg} - {str(e)[:40]}", advance=1)

        # 1. Handle --list-keys
        if list_keys:
            def render_keys(*a, **kw):
                if not all_instances:
                    console.print("[yellow]⚠️  No CVM instances found to inspect keys.[/yellow]")
                    return
                filter_arg = list_keys if isinstance(list_keys, str) else None
                render_keys_list(all_instances, "Tencent CVM Instance", key_filter=filter_arg)

            return CommandResult(data=[], table_renderer=render_keys)

        # 2. Parse keys filter if provided
        key_list = [k.strip() for k in keys_arg.split(",") if k.strip()] if keys_arg else []

        if key_list:
            filtered_data = []
            for inst in all_instances:
                item = {
                    "InstanceName": inst.get("InstanceName"),
                    "InstanceId": inst.get("InstanceId"),
                    "_account_name": inst.get("_account_name"),
                    "_region": inst.get("_region"),
                }
                item.update(extract_filtered_attributes(inst, key_list))
                filtered_data.append(item)

            def render_filtered_ui(*args, **kwargs):
                if not all_instances:
                    console.print("[yellow]⚠️  일치하는 CVM 인스턴스가 없습니다.[/yellow]")
                    return
                render_filtered_table(all_instances, key_list, name_field="InstanceName", id_field="InstanceId")

            return CommandResult(data=filtered_data, table_renderer=render_filtered_ui)

        # 3. Default: Full detailed attributes
        def render_full_yaml(*args, **kwargs):
            if not all_instances:
                console.print("[yellow]⚠️  일치하는 CVM 인스턴스가 없습니다.[/yellow]")
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
    TencentCvmDescCommand.add_arguments(parser)


def main(args: argparse.Namespace, config: Optional[Any] = None) -> None:
    cmd = TencentCvmDescCommand()
    cmd.run(args, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tencent CVM Detailed Resource Inspection")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
