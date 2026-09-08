#!/usr/bin/env python3
"""
AWS Load Balancer (ALB/NLB) Detailed Resource Inspection (desc) Command.
Enables full attribute discovery, dot-notation key filtering, and schema inspection for AWS LBs,
including Listeners, Rules, Target Groups, Health Checks, and Backend Targets.
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
import yaml  # type: ignore

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import get_env_accounts, get_profiles, DEFINED_REGIONS
from ic.core.interfaces.command import BaseCommand
from ic.core.interfaces.formatter import safe_serialize
from ic.core.interfaces.result import CommandResult
from ic.core.desc_helper import (
    extract_filtered_attributes,
    render_keys_list,
    render_filtered_table,
)

load_dotenv()
console = Console()


def fetch_raw_lb_one_account_region(
    account_id: str,
    profile_name: str,
    region_name: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    """Fetch raw AWS ALB/NLB details including listeners, target groups, and health checks."""
    log_info_non_console(f"AWS LB desc 수집 시작: Account={account_id}, Region={region_name}")
    try:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        elbv2 = session.client("elbv2", region_name=region_name)
    except Exception as e:
        log_info_non_console(f"Session 생성 실패 ({account_id}/{region_name}): {e}")
        return []

    lbs_detail = []

    try:
        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                lb_name = lb.get("LoadBalancerName", "-")
                lb_arn = lb.get("LoadBalancerArn", "")

                if name_filter:
                    patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                    if patterns and not any(p in lb_name.lower() or p in lb.get("DNSName", "").lower() or p in lb_arn.lower() for p in patterns):
                        continue

                lb["_account_name"] = account_id
                lb["_region"] = region_name

                # 1. Listeners and rules
                listeners_data = []
                target_group_arns = set()

                try:
                    l_resp = elbv2.describe_listeners(LoadBalancerArn=lb_arn)
                    raw_listeners = l_resp.get("Listeners", [])

                    for l in raw_listeners:
                        l_arn = l.get("ListenerArn", "")
                        
                        # Collect target group ARNs from default actions
                        for action in l.get("DefaultActions", []):
                            if "TargetGroupArn" in action:
                                target_group_arns.add(action["TargetGroupArn"])
                            if "ForwardConfig" in action:
                                for tg_tup in action["ForwardConfig"].get("TargetGroups", []):
                                    if "TargetGroupArn" in tg_tup:
                                        target_group_arns.add(tg_tup["TargetGroupArn"])

                        # Also fetch listener rules
                        try:
                            r_resp = elbv2.describe_rules(ListenerArn=l_arn)
                            l["Rules"] = r_resp.get("Rules", [])
                            for r in l["Rules"]:
                                for action in r.get("Actions", []):
                                    if "TargetGroupArn" in action:
                                        target_group_arns.add(action["TargetGroupArn"])
                                    if "ForwardConfig" in action:
                                        for tg_tup in action["ForwardConfig"].get("TargetGroups", []):
                                            if "TargetGroupArn" in tg_tup:
                                                target_group_arns.add(tg_tup["TargetGroupArn"])
                        except Exception as e:
                            log_info_non_console(f"Rules 조회 실패 ({l_arn}): {e}")

                        listeners_data.append(l)

                except Exception as e:
                    log_info_non_console(f"Listeners 조회 실패 ({lb_name}): {e}")

                lb["Listeners"] = listeners_data

                # 2. Target Groups and health check configurations
                tg_data = []
                all_health_checks = []

                if target_group_arns:
                    try:
                        # Batch query up to 20 target groups at a time
                        tg_arn_list = list(target_group_arns)
                        for i in range(0, len(tg_arn_list), 20):
                            chunk = tg_arn_list[i:i + 20]
                            tg_resp = elbv2.describe_target_groups(TargetGroupArns=chunk)
                            for tg in tg_resp.get("TargetGroups", []):
                                tg_arn = tg.get("TargetGroupArn", "")
                                
                                # Query targets and health
                                try:
                                    th_resp = elbv2.describe_target_health(TargetGroupArn=tg_arn)
                                    tg["TargetHealthDescriptions"] = th_resp.get("TargetHealthDescriptions", [])
                                except Exception as e:
                                    log_info_non_console(f"TargetHealth 조회 실패 ({tg_arn}): {e}")

                                # Extract health check details for convenience
                                hc_info = {
                                    "TargetGroupName": tg.get("TargetGroupName"),
                                    "HealthCheckProtocol": tg.get("HealthCheckProtocol"),
                                    "HealthCheckPort": tg.get("HealthCheckPort"),
                                    "HealthCheckPath": tg.get("HealthCheckPath"),
                                    "HealthCheckIntervalSeconds": tg.get("HealthCheckIntervalSeconds"),
                                    "HealthCheckTimeoutSeconds": tg.get("HealthCheckTimeoutSeconds"),
                                    "HealthyThresholdCount": tg.get("HealthyThresholdCount"),
                                    "UnhealthyThresholdCount": tg.get("UnhealthyThresholdCount"),
                                    "Matcher": tg.get("Matcher", {}).get("HttpCode"),
                                }
                                all_health_checks.append(hc_info)
                                tg_data.append(tg)

                    except Exception as e:
                        log_info_non_console(f"TargetGroups 조회 실패 ({lb_name}): {e}")

                lb["TargetGroups"] = tg_data
                lb["HealthCheck"] = all_health_checks if len(all_health_checks) > 1 else (all_health_checks[0] if all_health_checks else {})
                lbs_detail.append(lb)

    except Exception as e:
        log_info_non_console(f"describe_load_balancers 실패 ({account_id}/{region_name}): {e}")

    return lbs_detail


class AwsLbDescCommand(BaseCommand):
    """
    AWS Load Balancer detailed inspection command.
    Supports full attribute dumping, key filtering (-k), and queryable key discovery (-l).
    """

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("-a", "--account", help="AWS 계정 ID 또는 프로파일 (없으면 .env 사용)")
        parser.add_argument("-r", "--regions", help="리전 목록 (콤마 구분, 예: ap-northeast-2)")
        parser.add_argument("-n", "--name", help="LB 이름 또는 DNS 필터 (콤마 구분)")
        parser.add_argument(
            "-k", "--keys", "-f", "--fields",
            help="조회할 상세 속성 키 목록 (콤마 구분, 점 표기법 지원, 예: DNSName,Type,HealthCheck.HealthCheckPath)"
        )
        parser.add_argument(
            "-l", "--list-keys",
            nargs="?",
            const=True,
            default=False,
            help="조회 가능한 모든 상세 속성 키 목록 표시 (키워드로 필터링 가능, 예: -l health)"
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
        all_lbs: List[Dict[str, Any]] = []

        with ManualProgress("Collecting detailed AWS Load Balancers", total=total_ops) as progress:
            with ThreadPoolExecutor() as executor:
                futures = {}
                for acct, profile_name in valid_accounts:
                    for reg in regions:
                        f = executor.submit(fetch_raw_lb_one_account_region, acct, profile_name, reg, name_filter)
                        futures[f] = (acct, reg)

                for f in as_completed(futures):
                    acct, reg = futures[f]
                    try:
                        res = f.result()
                        all_lbs.extend(res)
                        progress.update(f"Processed {acct}/{reg} - Found {len(res)} LBs", advance=1)
                    except Exception as e:
                        progress.update(f"Failed {acct}/{reg} - {str(e)[:40]}", advance=1)

        # 1. Handle --list-keys
        if list_keys:
            def render_keys(*a, **kw):
                if not all_lbs:
                    console.print("[yellow]⚠️  No AWS Load Balancers found to inspect keys.[/yellow]")
                    return
                filter_arg = list_keys if isinstance(list_keys, str) else None
                render_keys_list(all_lbs, "AWS Load Balancer (ALB/NLB)", key_filter=filter_arg)

            return CommandResult(data=[], table_renderer=render_keys)

        # 2. Parse keys filter if provided
        key_list = [k.strip() for k in keys_arg.split(",") if k.strip()] if keys_arg else []

        if key_list:
            filtered_data = []
            for lb in all_lbs:
                item = {
                    "LoadBalancerName": lb.get("LoadBalancerName"),
                    "DNSName": lb.get("DNSName"),
                    "_account_name": lb.get("_account_name"),
                    "_region": lb.get("_region"),
                }
                item.update(extract_filtered_attributes(lb, key_list))
                filtered_data.append(item)

            def render_filtered_ui(*args, **kwargs):
                if not all_lbs:
                    console.print("[yellow]⚠️  일치하는 AWS LB 리소스가 없습니다.[/yellow]")
                    return
                render_filtered_table(all_lbs, key_list, name_field="LoadBalancerName", id_field="DNSName")

            return CommandResult(data=filtered_data, table_renderer=render_filtered_ui)

        # 3. Default: Full detailed attributes
        def render_full_yaml(*args, **kwargs):
            if not all_lbs:
                console.print("[yellow]⚠️  일치하는 AWS LB 리소스가 없습니다.[/yellow]")
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
    AwsLbDescCommand.add_arguments(parser)


def main(args: argparse.Namespace, config: Optional[Any] = None) -> None:
    cmd = AwsLbDescCommand()
    cmd.run(args, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS Load Balancer Detailed Resource Inspection")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
