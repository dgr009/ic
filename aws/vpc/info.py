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
from common.utils import get_env_accounts, get_profiles, DEFINED_REGIONS

load_dotenv()
console = Console()

def get_name_tag(tags):
    return next((tag['Value'] for tag in tags if tag['Key'] == 'Name'), None)

def fetch_vpc_one_account_region(account_id, profile_name, region_name, name_filter):
    log_info_non_console(f"VPC 정보 수집 시작: Account={account_id}, Region={region_name}")
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    ec2_client = session.client("ec2", region_name=region_name)
    
    rows = []
    
    try:
        vpcs = ec2_client.describe_vpcs().get('Vpcs', [])
    except Exception as e:
        log_info_non_console(f"VPC 목록 조회 실패: {e}")
        return []

    for vpc in vpcs:
        vpc_name = get_name_tag(vpc.get('Tags', [])) or vpc['VpcId']
        if name_filter and name_filter.lower() not in vpc_name.lower():
            continue

        subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc['VpcId']]}]).get('Subnets', [])
        
        if not subnets:
            rows.append({"account": account_id, "region": region_name, "vpc_name": vpc_name, "vpc_cidr": vpc.get('CidrBlock', '-'), "subnet_name": "No Subnets", "subnet_cidr": "-", "route_table": "-", "route_rule": "-"})
            continue

        for subnet in subnets:
            subnet_name = get_name_tag(subnet.get('Tags', [])) or subnet['SubnetId']
            route_tables = ec2_client.describe_route_tables(Filters=[{'Name': 'association.subnet-id', 'Values': [subnet['SubnetId']]}]).get('RouteTables', [])
            
            if not route_tables:
                rows.append({"account": account_id, "region": region_name, "vpc_name": vpc_name, "vpc_cidr": vpc.get('CidrBlock', '-'), "subnet_name": subnet_name, "subnet_cidr": subnet.get('CidrBlock', '-'), "route_table": "Main (Implicit)", "route_rule": "-"})
                continue

            for rt in route_tables:
                rt_name = get_name_tag(rt.get('Tags', [])) or rt['RouteTableId']
                for route in rt.get('Routes', []):
                    dest = route.get('DestinationCidrBlock', 'N/A')
                    target = route.get('GatewayId', route.get('NatGatewayId', route.get('InstanceId', 'N/A')))
                    rows.append({"account": account_id, "region": region_name, "vpc_name": vpc_name, "vpc_cidr": vpc.get('CidrBlock', '-'), "subnet_name": subnet_name, "subnet_cidr": subnet.get('CidrBlock', '-'), "route_table": rt_name, "route_rule": f"{dest} -> {target}"})

    return rows


def print_vpc_table(all_rows):
    if not all_rows:
        console.print("[yellow]표시할 VPC 정보가 없습니다.[/yellow]")
        return
        
    all_rows.sort(key=lambda x: (x["account"], x["region"], x["vpc_name"], x["subnet_name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.show_edge = False
    
    headers = ["Account", "Region", "VPC Name", "VPC CIDR", "Subnet Name", "Subnet CIDR", "Route Table", "Route Rule"]
    keys = ["account", "region", "vpc_name", "vpc_cidr", "subnet_name", "subnet_cidr", "route_table", "route_rule"]
    
    for h in headers:
        style = {}
        if h == "Account": style = {"style": "dim magenta"}
        elif h == "Region": style = {"style": "bold cyan"}
        table.add_column(h, **style)

    last_account, last_region, last_vpc, last_subnet = None, None, None, None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region
        vpc_changed = row["vpc_name"] != last_vpc
        subnet_changed = row["subnet_name"] != last_subnet

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif vpc_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])
            elif subnet_changed:
                table.add_row("", "", "", "", *[Rule(style="dim") for _ in headers[4:]])

        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        display_values.append(row["vpc_name"] if account_changed or region_changed or vpc_changed else "")
        display_values.append(row["vpc_cidr"] if account_changed or region_changed or vpc_changed else "")
        display_values.append(row["subnet_name"] if account_changed or region_changed or vpc_changed or subnet_changed else "")
        display_values.append(row["subnet_cidr"] if account_changed or region_changed or vpc_changed or subnet_changed else "")

        for k in keys[6:]:
            display_values.append(str(row.get(k, "-")))

        table.add_row(*display_values)
        
        last_account, last_region, last_vpc, last_subnet = row["account"], row["region"], row["vpc_name"], row["subnet_name"]

    console.print(table)


def main(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    name_filter = args.name if hasattr(args, 'name') and args.name else None

    all_rows = []
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(fetch_vpc_one_account_region, acct, profiles_map.get(acct), reg, name_filter): (acct, reg)
            for acct in accounts if profiles_map.get(acct)
            for reg in regions
        }
        for future in as_completed(futures):
            all_rows.extend(future.result())

    print_vpc_table(all_rows)


def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-n', '--name', help='VPC 이름 필터 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS VPC 정보 (병렬 수집)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
