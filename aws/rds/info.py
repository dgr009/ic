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

def color_status(status: str):
    s = status.lower()
    if s == "available":
        return f"[bold green]{status}[/bold green]"
    elif s in ["stopped", "stopping"]:
        return f"[bold yellow]{status}[/bold yellow]"
    elif s in ["creating", "modifying", "upgrading"]:
        return f"[bold cyan]{status}[/bold cyan]"
    else:
        return f"[bold red]{status}[/bold red]"

def fetch_rds_one_account_region(account_id, profile_name, region_name, name_filter):
    log_info_non_console(f"RDS 정보 수집 시작: Account={account_id}, Region={region_name}")
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    rds_client = session.client("rds", region_name=region_name)
    
    rows = []
    
    try:
        db_instances = rds_client.describe_db_instances().get('DBInstances', [])
        db_clusters = rds_client.describe_db_clusters().get('DBClusters', [])
    except Exception as e:
        log_info_non_console(f"RDS 목록 조회 실패: {e}")
        return []

    cluster_map = {c['DBClusterIdentifier']: c for c in db_clusters}
    
    for db in db_instances:
        if name_filter and name_filter.lower() not in db['DBInstanceIdentifier'].lower():
            continue

        cluster_id = db.get('DBClusterIdentifier')
        cluster_info = cluster_map.get(cluster_id) if cluster_id else None
        
        endpoint = db['Endpoint']['Address'] if 'Endpoint' in db and 'Address' in db['Endpoint'] else "-"
        if cluster_info:
            role = "Writer" if db['DBInstanceIdentifier'] == cluster_info.get('DBClusterMembers', [{}])[0].get('DBInstanceIdentifier') else "Reader"
            endpoint = cluster_info['Endpoint'] if 'Endpoint' in cluster_info else endpoint # Use cluster endpoint if available
        else:
            role = "Instance"

        rows.append({
            "account": account_id,
            "region": region_name,
            "identifier": db['DBInstanceIdentifier'],
            "cluster": cluster_id or "-",
            "role": role,
            "status": color_status(db['DBInstanceStatus']),
            "engine": f"{db['Engine']} {db['EngineVersion']}",
            "instance_class": db['DBInstanceClass'],
            "endpoint": endpoint,
            "multi_az": db['MultiAZ'],
        })
    return rows

def print_rds_table(all_rows):
    if not all_rows:
        console.print("[yellow]표시할 RDS 정보가 없습니다.[/yellow]")
        return
        
    all_rows.sort(key=lambda x: (x["account"], x["region"], x["cluster"], x["identifier"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.show_edge = False

    headers = ["Account", "Region", "Identifier", "Cluster", "Role", "Status", "Engine", "Instance Class", "Endpoint", "Multi-AZ"]
    keys = ["account", "region", "identifier", "cluster", "role", "status", "engine", "instance_class", "endpoint", "multi_az"]
    
    for h in headers:
        style = {}
        if h == "Account": style = {"style": "dim magenta"}
        elif h == "Region": style = {"style": "bold cyan"}
        elif h == "Status": style = {"justify": "center"}
        table.add_column(h, **style)

    last_account, last_region, last_cluster = None, None, None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region
        cluster_changed = row["cluster"] != last_cluster

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif cluster_changed:
                 table.add_row("", "", "", *[Rule(style="dim") for _ in headers[3:]])

        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        display_values.append(row["identifier"])
        display_values.append(row["cluster"] if account_changed or region_changed or cluster_changed else "")

        for k in keys[4:]:
            display_values.append(str(row.get(k, "-")))
        
        table.add_row(*display_values)

        last_account, last_region, last_cluster = row["account"], row["region"], row["cluster"]
        
    console.print(table)


def main(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    name_filter = args.name if hasattr(args, 'name') and args.name else None

    # Calculate total operations for progress tracking
    valid_accounts = []
    for acct in accounts:
        profile_name = profiles_map.get(acct)
        if not profile_name:
            log_info_non_console(f"Account {acct} 에 대한 프로파일을 찾을 수 없습니다.")
            continue
        valid_accounts.append((acct, profile_name))
    
    total_operations = len(valid_accounts) * len(regions)
    
    all_rows = []
    with ManualProgress("Collecting RDS instances and clusters across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(fetch_rds_one_account_region, acct, profile_name, reg, name_filter)
                    futures[future] = (acct, reg)
                    future_to_info[future] = (acct, reg)

            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    completed += 1
                    progress.update(f"Processed {acct}/{reg} - Found {len(result)} RDS resources", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect RDS data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)

    print_rds_table(all_rows)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-n', '--name', help='RDS 인스턴스/클러스터 이름 필터 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS RDS 정보 (병렬 수집)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)