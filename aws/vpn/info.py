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

def get_name_tag(tags):
    return next((tag['Value'] for tag in tags if tag['Key'] == 'Name'), None)

def fetch_vpn_one_account_region(account_id, profile_name, region_name):
    log_info_non_console(f"VPN 정보 수집 시작: Account={account_id}, Region={region_name}")
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    ec2_client = session.client("ec2", region_name=region_name)
    
    rows = []

    # TGW, VGW, VPN Connections, VPC Endpoints
    try:
        tgws = ec2_client.describe_transit_gateways().get('TransitGateways', [])
        vgws = ec2_client.describe_vpn_gateways().get('VpnGateways', [])
        vpn_conns = ec2_client.describe_vpn_connections().get('VpnConnections', [])
        endpoints = ec2_client.describe_vpc_endpoints().get('VpcEndpoints', [])
    except Exception as e:
        log_info_non_console(f"VPN 관련 리소스 조회 실패: {e}")
        return []

    for tgw in tgws:
        rows.append({"account": account_id, "region": region_name, "type": "TGW", "id": tgw['TransitGatewayId'], "name": get_name_tag(tgw.get('Tags',[])), "state": tgw['State'], "details": f"Owner: {tgw['OwnerId']}"})
    
    for vgw in vgws:
        attachments = ", ".join([att['VpcId'] for att in vgw.get('VpcAttachments', [])])
        rows.append({"account": account_id, "region": region_name, "type": "VGW", "id": vgw['VpnGatewayId'], "name": get_name_tag(vgw.get('Tags',[])), "state": vgw['State'], "details": f"Attached to: {attachments}"})

    for conn in vpn_conns:
        rows.append({"account": account_id, "region": region_name, "type": "VPN Connection", "id": conn['VpnConnectionId'], "name": get_name_tag(conn.get('Tags',[])), "state": conn['State'], "details": f"Type: {conn['Type']}, GW: {conn.get('VpnGatewayId', 'N/A')}"})
        
    for ep in endpoints:
        rows.append({"account": account_id, "region": region_name, "type": "VPC Endpoint", "id": ep['VpcEndpointId'], "name": get_name_tag(ep.get('Tags',[])), "state": ep['State'], "details": f"Service: {ep['ServiceName']}, Type: {ep['VpcEndpointType']}"})

    return rows

def print_vpn_table(all_rows):
    if not all_rows:
        console.print("[yellow]표시할 VPN 관련 정보가 없습니다.[/yellow]")
        return
        
    all_rows.sort(key=lambda x: (x["account"], x["region"], x["type"], x["name"] or x["id"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.show_edge = False
    
    headers = ["Account", "Region", "Type", "ID", "Name", "State", "Details"]
    keys = ["account", "region", "type", "id", "name", "state", "details"]
    
    for h in headers:
        style = {}
        if h == "Account": style = {"style": "dim magenta"}
        elif h == "Region": style = {"style": "bold cyan"}
        table.add_column(h, **style)

    last_account, last_region, last_type = None, None, None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region
        type_changed = row["type"] != last_type

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif type_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])

        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        display_values.append(row["type"] if account_changed or region_changed or type_changed else "")
        
        for k in keys[3:]:
            display_values.append(str(row.get(k, "-")))

        table.add_row(*display_values)

        last_account, last_region, last_type = row["account"], row["region"], row["type"]

    console.print(table)


def main(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()

    # Filter out accounts without valid profiles
    valid_accounts = []
    for acct in accounts:
        profile_name = profiles_map.get(acct)
        if profile_name:
            valid_accounts.append((acct, profile_name))
    
    total_operations = len(valid_accounts) * len(regions)

    all_rows = []
    with ManualProgress("Collecting VPN and networking information across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(fetch_vpn_one_account_region, acct, profile_name, reg)
                    futures.append(future)
                    future_to_info[future] = (acct, reg)

            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    completed += 1
                    resource_count = len(result)
                    progress.update(f"Processed {acct}/{reg} - Found {resource_count} network resources", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect VPN data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)

    print_vpn_table(all_rows)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS VPN 관련 정보 (병렬 수집)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
