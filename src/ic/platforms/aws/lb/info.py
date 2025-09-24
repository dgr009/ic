#!/usr/bin/env python3
import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import get_env_accounts, get_profiles, DEFINED_REGIONS

load_dotenv()
console = Console()

def fetch_lb_one_account_region(account_id, profile_name, region_name, name_filter):
    log_info_non_console(f"LB 정보 수집 시작: Account={account_id}, Region={region_name}")
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    elbv2_client = session.client("elbv2", region_name=region_name)
    
    rows = []
    
    try:
        lbs = elbv2_client.describe_load_balancers().get("LoadBalancers", [])
    except Exception as e:
        log_info_non_console(f"LB 목록 조회 실패: {e}")
        return []

    for lb in lbs:
        if name_filter and name_filter.lower() not in lb['LoadBalancerName'].lower():
            continue

        lb_arn = lb['LoadBalancerArn']
        lb_name = lb['LoadBalancerName']
        lb_type = lb['Type']
        lb_scheme = lb['Scheme']
        lb_dns = lb['DNSName']
        
        listeners = elbv2_client.describe_listeners(LoadBalancerArn=lb_arn).get('Listeners', [])
        
        if not listeners:
            rows.append({
                "account": account_id, "region": region_name, "lb_name": lb_name, "type": lb_type,
                "scheme": lb_scheme, "dns": lb_dns, "listener": "(No Listeners)", "target_group": "-",
                "targets": "-", "health": "-"
            })
            continue

        for listener in listeners:
            listener_str = f"{listener['Protocol']}:{listener['Port']}"
            
            default_actions = listener.get('DefaultActions', [])
            target_groups = []
            for action in default_actions:
                if action['Type'] == 'forward' and 'TargetGroupArn' in action:
                     target_groups.append(action['TargetGroupArn'])

            if not target_groups:
                rows.append({
                    "account": account_id, "region": region_name, "lb_name": lb_name, "type": lb_type,
                    "scheme": lb_scheme, "dns": lb_dns, "listener": listener_str, "target_group": "(No Target Groups)",
                    "targets": "-", "health": "-"
                })
                continue
            
            tg_arns = list(set(target_groups))
            tg_details = elbv2_client.describe_target_groups(TargetGroupArns=tg_arns).get('TargetGroups', [])
            
            for tg in tg_details:
                tg_name = tg['TargetGroupName']
                health_checks = elbv2_client.describe_target_health(TargetGroupArn=tg['TargetGroupArn']).get('TargetHealthDescriptions', [])
                
                if not health_checks:
                    rows.append({
                        "account": account_id, "region": region_name, "lb_name": lb_name, "type": lb_type,
                        "scheme": lb_scheme, "dns": lb_dns, "listener": listener_str, "target_group": tg_name,
                        "targets": "(No Targets)", "health": "-"
                    })
                    continue
                    
                for health in health_checks:
                    target_id = health['Target'].get('Id', '-')
                    try:
                        ec2_client = session.client("ec2", region_name=region_name)
                        resp = ec2_client.describe_instances(InstanceIds=[target_id])
                        reservations = resp.get("Reservations", [])
                        if reservations and reservations[0]["Instances"]:
                            tags = reservations[0]["Instances"][0].get("Tags", [])
                            target_name = next((t["Value"] for t in tags if t["Key"] == "Name"), target_id)
                        else:
                            target_name = target_id
                    except Exception as e:
                        target_name = target_id
                    
                    target_port = health['Target'].get('Port', '-')
                    health_status = health['TargetHealth']['State']
                    
                    color = "green" if health_status == "healthy" else "red" if health_status == "unhealthy" else "yellow"
                    health_colored = f"[{color}]{health_status}[/{color}]"

                    rows.append({
                        "account": account_id, "region": region_name, "lb_name": lb_name, "type": lb_type,
                        "scheme": lb_scheme, "dns": lb_dns, "listener": listener_str, "target_group": tg_name,
                        "targets": f"{target_name}:{target_port}", "health": health_colored
                    })
    return rows

def print_lb_table(all_rows):
    if not all_rows:
        console.print("[yellow]표시할 로드 밸런서 정보가 없습니다.[/yellow]")
        return
        
    all_rows.sort(key=lambda x: (x["account"], x["region"], x["lb_name"], x["listener"], x["target_group"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.show_edge = False
    
    headers = ["Account", "Region", "LB Name", "Type", "Scheme", "Listener", "Target Group", "Targets", "Health"]
    keys = ["account", "region", "lb_name", "type", "scheme", "listener", "target_group", "targets", "health"]
    
    for h in headers:
        style = {}
        if h == "Account": style = {"style": "bold magenta"}
        elif h == "Region": style = {"style": "bold cyan"}
        elif h == "Health": style = {"justify": "center"}
        table.add_column(h, **style)

    last_account, last_region, last_lb, last_tg = None, None, None, None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region
        lb_changed = row["lb_name"] != last_lb
        tg_changed = row["target_group"] != last_tg

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif lb_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])
            elif tg_changed:
                table.add_row("", "", "", "", "", "", *[Rule(style="dim") for _ in headers[6:]])

        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        display_values.append(row["lb_name"] if account_changed or region_changed or lb_changed else "")
        display_values.append(row["type"] if account_changed or region_changed or lb_changed else "")
        display_values.append(row["scheme"] if account_changed or region_changed or lb_changed else "")
        display_values.append(row["listener"] if account_changed or region_changed or lb_changed else "")
        display_values.append(row["target_group"] if account_changed or region_changed or lb_changed or tg_changed else "")

        for k in keys[7:]:
            display_values.append(str(row.get(k, "-")))
        
        table.add_row(*display_values)
        
        last_account, last_region, last_lb, last_tg = row["account"], row["region"], row["lb_name"], row["target_group"]

    console.print(table)

def main(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    name_filter = args.name if hasattr(args, 'name') and args.name else None
    
    # Filter out accounts without valid profiles
    valid_accounts = []
    for acct in accounts:
        profile_name = profiles_map.get(acct)
        if profile_name:
            valid_accounts.append((acct, profile_name))
    
    total_operations = len(valid_accounts) * len(regions)
    
    all_rows = []
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
            
    print_lb_table(all_rows)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-n', '--name', help='LB 이름 필터 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS LB 정보 (병렬 수집)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
