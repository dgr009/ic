#!/usr/bin/env python3
"""
AWS Load Balancer (ALB/NLB) 상세 정보 조회

Tencent CLB info와 동일한 스타일로 Listener, Target Group, Target Instance, Health Check Path, Health Status 정보 제공.

Usage:
    ic aws lb info
    ic aws lb info -a 123456789012
    ic aws lb info -r ap-northeast-2
    ic aws lb info -n "my-alb"
    ic aws lb info -v
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import boto3  # type: ignore
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import get_env_accounts, get_profiles, DEFINED_REGIONS
from ic.core.interfaces import BaseCommand, CommandResult

load_dotenv()
console = Console()


def _format_created_time(created_time: Any) -> str:
    if not created_time:
        return "-"
    try:
        return created_time.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(created_time)[:16]


def fetch_lb_one_account_region(
    account_id: str,
    profile_name: str,
    region_name: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    log_info_non_console(f"LB 정보 수집 시작: Account={account_id}, Region={region_name}")
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    elbv2_client = session.client("elbv2", region_name=region_name)
    ec2_client = session.client("ec2", region_name=region_name)

    rows: List[Dict[str, Any]] = []

    try:
        lbs = elbv2_client.describe_load_balancers().get("LoadBalancers", [])
    except Exception as e:
        log_info_non_console(f"LB 목록 조회 실패 ({account_id}/{region_name}): {e}")
        return []

    for lb in lbs:
        if name_filter:
            patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
            if patterns and not any(p in lb['LoadBalancerName'].lower() or p in lb.get('DNSName', '').lower() for p in patterns):
                continue

        lb_arn = lb['LoadBalancerArn']
        lb_name = lb['LoadBalancerName']
        lb_type = lb['Type']
        lb_scheme = lb['Scheme']
        lb_dns = lb.get('DNSName', '-')
        vpc_id = lb.get('VpcId', '-')
        state_code = lb.get('State', {}).get('Code', '-') if isinstance(lb.get('State'), dict) else str(lb.get('State', '-'))
        create_time = _format_created_time(lb.get('CreatedTime'))

        try:
            listeners = elbv2_client.describe_listeners(LoadBalancerArn=lb_arn).get('Listeners', [])
        except Exception as e:
            log_info_non_console(f"Listeners 조회 실패 ({lb_name}): {e}")
            listeners = []

        if not listeners:
            rows.append({
                "account": account_id, "region": region_name, "lb_name": lb_name, "lb_arn": lb_arn,
                "type": lb_type, "scheme": lb_scheme, "dns": lb_dns, "status": state_code,
                "vpc_id": vpc_id, "create_time": create_time,
                "listener": "(No Listeners)", "target_group": "-",
                "hc_path": "-", "targets": "-", "health": "-"
            })
            continue

        for listener in listeners:
            listener_str = f"{listener['Protocol']}:{listener['Port']}"

            default_actions = listener.get('DefaultActions', [])
            target_groups = []
            for action in default_actions:
                if action['Type'] == 'forward':
                    if 'TargetGroupArn' in action:
                        target_groups.append(action['TargetGroupArn'])
                    if 'ForwardConfig' in action and 'TargetGroups' in action['ForwardConfig']:
                        for tg_elem in action['ForwardConfig']['TargetGroups']:
                            if 'TargetGroupArn' in tg_elem:
                                target_groups.append(tg_elem['TargetGroupArn'])

            if not target_groups:
                rows.append({
                    "account": account_id, "region": region_name, "lb_name": lb_name, "lb_arn": lb_arn,
                    "type": lb_type, "scheme": lb_scheme, "dns": lb_dns, "status": state_code,
                    "vpc_id": vpc_id, "create_time": create_time,
                    "listener": listener_str, "target_group": "(No Target Groups)",
                    "hc_path": "-", "targets": "-", "health": "-"
                })
                continue

            tg_arns = list(set(target_groups))
            try:
                tg_details = elbv2_client.describe_target_groups(TargetGroupArns=tg_arns).get('TargetGroups', [])
            except Exception as e:
                log_info_non_console(f"TargetGroups 조회 실패 ({lb_name}): {e}")
                tg_details = []

            if not tg_details:
                rows.append({
                    "account": account_id, "region": region_name, "lb_name": lb_name, "lb_arn": lb_arn,
                    "type": lb_type, "scheme": lb_scheme, "dns": lb_dns, "status": state_code,
                    "vpc_id": vpc_id, "create_time": create_time,
                    "listener": listener_str, "target_group": "(Target Group Error)",
                    "hc_path": "-", "targets": "-", "health": "-"
                })
                continue

            for tg in tg_details:
                tg_name = tg['TargetGroupName']
                hc_path = tg.get('HealthCheckPath', '-')

                try:
                    health_checks = elbv2_client.describe_target_health(TargetGroupArn=tg['TargetGroupArn']).get('TargetHealthDescriptions', [])
                except Exception as e:
                    log_info_non_console(f"TargetHealth 조회 실패 ({tg_name}): {e}")
                    health_checks = []

                if not health_checks:
                    rows.append({
                        "account": account_id, "region": region_name, "lb_name": lb_name, "lb_arn": lb_arn,
                        "type": lb_type, "scheme": lb_scheme, "dns": lb_dns, "status": state_code,
                        "vpc_id": vpc_id, "create_time": create_time,
                        "listener": listener_str, "target_group": tg_name,
                        "hc_path": hc_path, "targets": "(No Targets)", "health": "-"
                    })
                    continue

                for health in health_checks:
                    target_id = health['Target'].get('Id', '-')
                    target_port = health['Target'].get('Port', '-')

                    target_name = target_id
                    if target_id.startswith("i-"):
                        try:
                            resp = ec2_client.describe_instances(InstanceIds=[target_id])
                            reservations = resp.get("Reservations", [])
                            if reservations and reservations[0]["Instances"]:
                                tags = reservations[0]["Instances"][0].get("Tags", [])
                                inst_name_tag = next((t["Value"] for t in tags if t["Key"] == "Name"), None)
                                private_ip = reservations[0]["Instances"][0].get("PrivateIpAddress", "")
                                if inst_name_tag:
                                    target_name = f"{inst_name_tag} ({private_ip or target_id}:{target_port})"
                                else:
                                    target_name = f"{target_id}:{target_port}"
                            else:
                                target_name = f"{target_id}:{target_port}"
                        except Exception:
                            target_name = f"{target_id}:{target_port}"
                    else:
                        target_name = f"{target_id}:{target_port}"

                    health_status = health['TargetHealth']['State']
                    reason = health['TargetHealth'].get('Reason', '')

                    if health_status == "healthy":
                        health_colored = "[bold green]Healthy[/bold green]"
                    elif health_status == "unhealthy":
                        reason_str = f" ({reason})" if reason else ""
                        health_colored = f"[bold red]Unhealthy{reason_str}[/bold red]"
                    else:
                        health_colored = f"[bold yellow]{health_status.capitalize()}[/bold yellow]"

                    rows.append({
                        "account": account_id, "region": region_name, "lb_name": lb_name, "lb_arn": lb_arn,
                        "type": lb_type, "scheme": lb_scheme, "dns": lb_dns, "status": state_code,
                        "vpc_id": vpc_id, "create_time": create_time,
                        "listener": listener_str, "target_group": tg_name,
                        "hc_path": hc_path, "targets": target_name, "health": health_colored
                    })

    return rows


def print_lb_table(all_rows: List[Dict[str, Any]], verbose: bool = False) -> None:
    if not all_rows:
        console.print("[yellow]표시할 로드 밸런서 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["lb_name"], x["listener"], x["target_group"], x["targets"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.show_edge = False

    if verbose:
        headers = [
            "Account", "Region", "LB Name", "Type", "Scheme", "Status",
            "DNS", "Listener", "Target Group", "Health Path",
            "Target (Instance / IP:Port)", "Health", "VPC", "Created"
        ]
    else:
        headers = [
            "Account", "Region", "LB Name", "Type", "Scheme",
            "Listener", "Target Group", "Health Path",
            "Target (Instance / IP:Port)", "Health"
        ]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
        elif h in ["Health", "Status"]:
            table.add_column(h, justify="center")
        else:
            table.add_column(h)

    last_account = None
    last_region = None
    last_lb = None
    last_listener = None
    last_tg = None

    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region
        lb_changed = row["lb_name"] != last_lb or account_changed or region_changed
        listener_changed = row["listener"] != last_listener or lb_changed
        tg_changed = row["target_group"] != last_tg or listener_changed

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif lb_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])
            elif listener_changed:
                offset = 7 if verbose else 5
                table.add_row(*["" for _ in range(offset)], *[Rule(style="dim") for _ in headers[offset:]])
            elif tg_changed:
                offset = 8 if verbose else 6
                table.add_row(*["" for _ in range(offset)], *[Rule(style="dim") for _ in headers[offset:]])

        display_values: List[str] = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        display_values.append(row["lb_name"] if lb_changed else "")
        display_values.append(row["type"] if lb_changed else "")
        display_values.append(row["scheme"] if lb_changed else "")

        if verbose:
            display_values.append(row.get("status", "-") if lb_changed else "")
            display_values.append(row.get("dns", "-") if lb_changed else "")
            display_values.append(row["listener"] if listener_changed else "")
            display_values.append(row["target_group"] if tg_changed else "")
            display_values.append(row["hc_path"] if tg_changed else "")
            display_values.append(row["targets"])
            display_values.append(row["health"])
            display_values.append(row.get("vpc_id", "-") if lb_changed else "")
            display_values.append(row.get("create_time", "-") if lb_changed else "")
        else:
            display_values.append(row["listener"] if listener_changed else "")
            display_values.append(row["target_group"] if tg_changed else "")
            display_values.append(row["hc_path"] if tg_changed else "")
            display_values.append(row["targets"])
            display_values.append(row["health"])

        table.add_row(*display_values)

        last_account = row["account"]
        last_region = row["region"]
        last_lb = row["lb_name"]
        last_listener = row["listener"]
        last_tg = row["target_group"]

    console.print(table)


def collect_lb_data(args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Collect AWS Load Balancer information across accounts and regions."""
    accounts = get_env_accounts(getattr(args, "account", None))
    regions = args.regions.split(",") if getattr(args, "regions", None) else DEFINED_REGIONS
    profiles_map = get_profiles()
    name_filter = getattr(args, "name", None)

    valid_accounts = []
    for acct in accounts:
        profile_name = profiles_map.get(acct)
        if profile_name:
            valid_accounts.append((acct, profile_name))

    total_operations = len(valid_accounts) * len(regions)
    all_rows: List[Dict[str, Any]] = []

    with ManualProgress("Collecting Load Balancer information across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}

            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(fetch_lb_one_account_region, acct, profile_name, reg, name_filter)
                    futures.append(future)
                    future_to_info[future] = (acct, reg)

            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    completed += 1
                    lb_count = len(set(row['lb_name'] for row in result))
                    progress.update(f"Processed {acct}/{reg} - Found {lb_count} Load Balancers", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect LB data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)

    return all_rows


class AwsLbInfoCommand(BaseCommand):
    """AWS Load Balancer (ALB/NLB) info command implementation."""

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
        parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
        parser.add_argument('-n', '--name', help='LB 이름 필터 (콤마(,)로 복수 검색 가능, 예: web,api)')
        parser.add_argument('-v', '--verbose', action='store_true', help='상세 정보 출력 (Status, DNS, VPC, Created 등)')

    def execute(self, args: argparse.Namespace, config: Optional[Any] = None) -> CommandResult:
        rows = collect_lb_data(args)
        return CommandResult(
            data=rows,
            table_renderer=print_lb_table,
        )


def main(args: argparse.Namespace, config: Optional[Any] = None) -> None:
    AwsLbInfoCommand().run(args, config)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    AwsLbInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS LB 정보 (병렬 수집)")
    add_arguments(parser)
    main(parser.parse_args())
