#!/usr/bin/env python3
"""
AWS EC2 Detailed Resource Inspection (desc) Command.
Enables full attribute discovery, dot-notation key filtering, and schema inspection.
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich import box
import yaml  # type: ignore

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import get_env_accounts, get_profiles, DEFINED_REGIONS
from ic.core.interfaces.command import BaseCommand
from ic.core.interfaces.formatter import OutputFormatter, safe_serialize
from ic.core.interfaces.result import CommandResult
from ic.core.desc_helper import (
    extract_filtered_attributes,
    render_keys_list,
    render_filtered_table,
)

load_dotenv()
console = Console()


def fetch_raw_ec2_instances(account_id: str, profile_name: str, region_name: str, name_filter: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch raw EC2 instance dictionaries from AWS."""
    log_info_non_console(f"EC2 desc 수집 시작: Account={account_id}, Region={region_name}")
    try:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        ec2_client = session.client("ec2", region_name=region_name)
    except Exception as e:
        log_info_non_console(f"Session 생성 실패 ({account_id}/{region_name}): {e}")
        return []

    instances = []
    try:
        paginator = ec2_client.get_paginator("describe_instances")
        for page in paginator.paginate():
            for rsv in page.get("Reservations", []):
                for inst in rsv.get("Instances", []):
                    if inst.get("State", {}).get("Name") == "terminated":
                        continue

                    inst_name = next((t.get("Value") for t in inst.get("Tags", []) if t.get("Key") == "Name"), None) or inst.get("InstanceId", "")
                    
                    if name_filter:
                        patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                        if patterns and not any(p in inst_name.lower() or p in inst.get("InstanceId", "").lower() for p in patterns):
                            continue

                    # Enrich dictionary with metadata
                    inst["InstanceName"] = inst_name
                    inst["_account_name"] = account_id
                    inst["_region"] = region_name
                    instances.append(inst)
    except Exception as e:
        log_info_non_console(f"describe_instances 실패 ({account_id}/{region_name}): {e}")

    return instances


class AwsEc2DescCommand(BaseCommand):
    """
    AWS EC2 detailed inspection command.
    Supports full attribute dumping, key filtering (-k), and queryable key discovery (-l).
    """

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("-a", "--account", help="AWS 계정 ID 또는 프로파일 (없으면 .env 사용)")
        parser.add_argument("-r", "--regions", help="리전 목록 (콤마 구분, 예: ap-northeast-2)")
        parser.add_argument("-n", "--name", help="인스턴스 이름 또는 ID 필터 (콤마 구분)")
        parser.add_argument(
            "-k", "--keys", "-f", "--fields",
            help="조회할 상세 속성 키 목록 (콤마 구분, 점 표기법 지원, 예: ImageId,InstanceType,State.Name)"
        )
        parser.add_argument(
            "-l", "--list-keys",
            nargs="?",
            const=True,
            default=False,
            help="조회 가능한 모든 상세 속성 키 목록 표시 (키워드로 필터링 가능, 예: -l image)"
        )
        cls.add_common_arguments(parser)

    def execute(self, args: argparse.Namespace, config: Optional[Any] = None) -> CommandResult:
        accounts = get_env_accounts(getattr(args, "account", None))
        regions = args.regions.split(",") if getattr(args, "regions", None) else DEFINED_REGIONS
        profiles_map = get_profiles()
        name_filter = getattr(args, "name", None)
        keys_arg = getattr(args, "keys", None)
        list_keys = getattr(args, "list_keys", False)

        valid_accounts = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if profile_name:
                valid_accounts.append((acct, profile_name))

        total_ops = len(valid_accounts) * len(regions)
        all_instances: List[Dict[str, Any]] = []

        with ManualProgress("Collecting detailed EC2 instances", total=total_ops) as progress:
            with ThreadPoolExecutor() as executor:
                futures = {}
                for acct, profile_name in valid_accounts:
                    for reg in regions:
                        f = executor.submit(fetch_raw_ec2_instances, acct, profile_name, reg, name_filter)
                        futures[f] = (acct, reg)

                for f in as_completed(futures):
                    acct, reg = futures[f]
                    try:
                        res = f.result()
                        all_instances.extend(res)
                        progress.update(f"Processed {acct}/{reg} - Found {len(res)} instances", advance=1)
                    except Exception as e:
                        progress.update(f"Failed {acct}/{reg} - {str(e)[:40]}", advance=1)

        # 1. Handle --list-keys
        if list_keys:
            def render_keys(*a, **kw):
                if not all_instances:
                    console.print("[yellow]⚠️  No EC2 instances found to inspect keys.[/yellow]")
                    return
                filter_arg = list_keys if isinstance(list_keys, str) else None
                render_keys_list(all_instances, "AWS EC2 Instance", key_filter=filter_arg)

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
                    console.print("[yellow]⚠️  일치하는 EC2 인스턴스가 없습니다.[/yellow]")
                    return
                render_filtered_table(all_instances, key_list, name_field="InstanceName", id_field="InstanceId")

            return CommandResult(data=filtered_data, table_renderer=render_filtered_ui)

        # 3. Default: Full detailed attributes
        def render_full_yaml(*args, **kwargs):
            if not all_instances:
                console.print("[yellow]⚠️  일치하는 EC2 인스턴스가 없습니다.[/yellow]")
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
    AwsEc2DescCommand.add_arguments(parser)


def main(args: argparse.Namespace, config: Optional[Any] = None) -> None:
    cmd = AwsEc2DescCommand()
    cmd.run(args, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS EC2 Detailed Resource Inspection")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
