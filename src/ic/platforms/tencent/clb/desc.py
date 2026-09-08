#!/usr/bin/env python3
"""
Tencent CLB Detailed Resource Inspection (desc) Command.
Enables full attribute discovery, dot-notation key filtering, and schema inspection for CLB,
including Listeners, Rules, HealthChecks, and Target Backends.
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


def model_to_dict(model_obj: Any) -> Dict[str, Any]:
    """Convert a Tencent SDK model object to a Python dictionary."""
    if isinstance(model_obj, dict):
        return model_obj
    if hasattr(model_obj, "to_json_string") and callable(getattr(model_obj, "to_json_string")):
        try:
            return json.loads(model_obj.to_json_string())
        except Exception:
            pass
    if hasattr(model_obj, "to_dict") and callable(getattr(model_obj, "to_dict")):
        return model_obj.to_dict()
    if hasattr(model_obj, "__dict__"):
        return {k: v for k, v in model_obj.__dict__.items() if not k.startswith("_")}
    return {}


def fetch_raw_clb_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    """Fetch raw CLB instances including listeners, health checks, and targets."""
    account_id = account.get("id", "unknown")
    account_name = account.get("name", account_id)

    log_info_non_console(f"[CLB desc] 수집 시작: account={account_name}, region={region}")
    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.clb.v20180317 import clb_client, models
    except ImportError:
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    lbs_detail: List[Dict[str, Any]] = []
    try:
        client = clb_client.ClbClient(cred, region, make_client_profile())
        offset = 0
        limit = 100

        while True:
            req = models.DescribeLoadBalancersRequest()
            req.Offset = offset
            req.Limit = limit
            resp = client.DescribeLoadBalancers(req)
            batch = resp.LoadBalancerSet or []

            for lb in batch:
                lb_dict = model_to_dict(lb)
                lb_id = lb_dict.get("LoadBalancerId") or "-"
                lb_name = lb_dict.get("LoadBalancerName") or "-"

                if name_filter:
                    patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                    if patterns and not any(p in lb_name.lower() or p in lb_id.lower() for p in patterns):
                        continue

                lb_dict["LoadBalancerName"] = lb_name
                lb_dict["_account_name"] = account_name
                lb_dict["_region"] = region

                # Fetch listeners and health check details
                listeners_data = []
                all_health_checks = []

                try:
                    req_l = models.DescribeListenersRequest()
                    req_l.LoadBalancerId = lb_id
                    resp_l = client.DescribeListeners(req_l)
                    raw_listeners = resp_l.Listeners or []

                    # Also fetch targets
                    targets_map = {}
                    try:
                        req_t = models.DescribeTargetsRequest()
                        req_t.LoadBalancerId = lb_id
                        resp_t = client.DescribeTargets(req_t)
                        for l_t in (resp_t.Listeners or []):
                            l_id = l_t.ListenerId
                            targets_map[l_id] = model_to_dict(l_t)
                    except Exception as e:
                        log_info_non_console(f"[CLB desc] DescribeTargets 실패 ({lb_id}): {e}")

                    for l in raw_listeners:
                        l_dict = model_to_dict(l)
                        l_id = l_dict.get("ListenerId")

                        # Attach targets if available
                        if l_id in targets_map:
                            t_info = targets_map[l_id]
                            if "Targets" in t_info:
                                l_dict["Targets"] = t_info["Targets"]
                            if "Rules" in t_info and "Rules" in l_dict:
                                for r_idx, r_dict in enumerate(l_dict["Rules"]):
                                    if r_idx < len(t_info["Rules"]) and "Targets" in t_info["Rules"][r_idx]:
                                        r_dict["Targets"] = t_info["Rules"][r_idx]["Targets"]

                        # Collect health check objects
                        if l_dict.get("HealthCheck"):
                            all_health_checks.append(l_dict["HealthCheck"])
                        for r in l_dict.get("Rules", []):
                            if r.get("HealthCheck"):
                                all_health_checks.append(r["HealthCheck"])

                        listeners_data.append(l_dict)

                except Exception as e:
                    log_info_non_console(f"[CLB desc] DescribeListeners 실패 ({lb_id}): {e}")

                lb_dict["Listeners"] = listeners_data
                lb_dict["HealthCheck"] = all_health_checks if len(all_health_checks) > 1 else (all_health_checks[0] if all_health_checks else {})
                lbs_detail.append(lb_dict)

            offset += len(batch)
            if offset >= (resp.TotalCount or 0) or len(batch) < limit:
                break

    except Exception as e:
        log_info_non_console(f"[CLB desc] DescribeLoadBalancers 실패 ({account_name}/{region}): {e}")

    return lbs_detail


class TencentClbDescCommand(BaseCommand):
    """
    Tencent Cloud CLB detailed inspection command.
    Supports full attribute dumping, key filtering (-k), and queryable key discovery (-l).
    """

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
        parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
        parser.add_argument("-n", "--name", help="CLB 이름/ID 필터 (콤마 구분)")
        parser.add_argument(
            "-k", "--keys", "-f", "--fields",
            help="조회할 상세 속성 키 목록 (콤마 구분, 점 표기법 지원, 예: HealthCheck.IntervalTime,HealthCheck.TimeOut,Domain)"
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
        check_sdk_available()
        accounts = get_accounts(getattr(args, "account", None))
        regions = get_tencent_regions(getattr(args, "regions", None))
        name_filter = getattr(args, "name", None)
        keys_arg = getattr(args, "keys", None)
        list_keys = getattr(args, "list_keys", False)

        total_ops = len(accounts) * len(regions)
        all_lbs: List[Dict[str, Any]] = []

        with ManualProgress("Collecting detailed CLB resources", total=total_ops) as progress:
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {}
                for acct in accounts:
                    acct_name = acct.get("name", acct.get("id"))
                    for reg in regions:
                        f = executor.submit(fetch_raw_clb_one_account_region, acct, reg, name_filter)
                        futures[f] = (acct_name, reg)

                for f in as_completed(futures):
                    acct_name, reg = futures[f]
                    try:
                        res = f.result()
                        all_lbs.extend(res)
                        progress.update(f"Processed {acct_name}/{reg} - Found {len(res)} CLBs", advance=1)
                    except Exception as e:
                        progress.update(f"Failed {acct_name}/{reg} - {str(e)[:40]}", advance=1)

        # 1. Handle --list-keys
        if list_keys:
            def render_keys(*a, **kw):
                if not all_lbs:
                    console.print("[yellow]⚠️  No CLB instances found to inspect keys.[/yellow]")
                    return
                filter_arg = list_keys if isinstance(list_keys, str) else None
                render_keys_list(all_lbs, "Tencent CLB LoadBalancer", key_filter=filter_arg)

            return CommandResult(data=[], table_renderer=render_keys)

        # 2. Parse keys filter if provided
        key_list = [k.strip() for k in keys_arg.split(",") if k.strip()] if keys_arg else []

        if key_list:
            filtered_data = []
            for lb in all_lbs:
                item = {
                    "LoadBalancerName": lb.get("LoadBalancerName"),
                    "LoadBalancerId": lb.get("LoadBalancerId"),
                    "_account_name": lb.get("_account_name"),
                    "_region": lb.get("_region"),
                }
                item.update(extract_filtered_attributes(lb, key_list))
                filtered_data.append(item)

            def render_filtered_ui(*args, **kwargs):
                if not all_lbs:
                    console.print("[yellow]⚠️  일치하는 CLB 리소스가 없습니다.[/yellow]")
                    return
                render_filtered_table(all_lbs, key_list, name_field="LoadBalancerName", id_field="LoadBalancerId")

            return CommandResult(data=filtered_data, table_renderer=render_filtered_ui)

        # 3. Default: Full detailed attributes
        def render_full_yaml(*args, **kwargs):
            if not all_lbs:
                console.print("[yellow]⚠️  일치하는 CLB 리소스가 없습니다.[/yellow]")
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
    TencentClbDescCommand.add_arguments(parser)


def main(args: argparse.Namespace, config: Optional[Any] = None) -> None:
    cmd = TencentClbDescCommand()
    cmd.run(args, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tencent CLB Detailed Resource Inspection")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
