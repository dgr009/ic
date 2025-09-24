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

def resolve_route_target(ec2_client, route):
    """
    Route 객체를 받아 타겟의 이름과 유형, IP를 반환합니다.
    """
    if route.get('GatewayId'):
        gateway_id = route['GatewayId']
        if gateway_id.startswith('igw-'):
            try:
                igw = ec2_client.describe_internet_gateways(InternetGatewayIds=[gateway_id])['InternetGateways'][0]
                name = get_name_tag(igw.get('Tags', []))
                return f"{name} (igw)" if name else "(igw)"
            except Exception:
                return f"{gateway_id} (igw)"
        elif gateway_id.startswith('vgw-'):
            try:
                vgw = ec2_client.describe_vpn_gateways(VpnGatewayIds=[gateway_id])['VpnGateways'][0]
                name = get_name_tag(vgw.get('Tags', []))
                return f"{name} (vgw)" if name else "(vgw)"
            except Exception:
                return f"{gateway_id} (vgw)"
        elif gateway_id == 'local':
            return "local"

    if route.get('NatGatewayId'):
        nat_gateway_id = route['NatGatewayId']
        try:
            nat = ec2_client.describe_nat_gateways(NatGatewayIds=[nat_gateway_id])['NatGateways'][0]
            name = get_name_tag(nat.get('Tags', []))
            public_ip = nat.get('NatGatewayAddresses', [{}])[0].get('PublicIp')
            
            ip_str = f": {public_ip}" if public_ip else ""
            return f"{name} (nat{ip_str})" if name else f"(nat{ip_str})"
        except Exception:
            return f"{nat_gateway_id} (nat)"

    if route.get('TransitGatewayId'):
        tgw_id = route['TransitGatewayId']
        try:
            tgw = ec2_client.describe_transit_gateways(TransitGatewayIds=[tgw_id])['TransitGateways'][0]
            name = get_name_tag(tgw.get('Tags', []))
            return f"{name} (tgw)" if name else "(tgw)"
        except Exception:
            return f"{tgw_id} (tgw)"

    if route.get('VpcPeeringConnectionId'):
        pcx_id = route['VpcPeeringConnectionId']
        try:
            pcx = ec2_client.describe_vpc_peering_connections(VpcPeeringConnectionIds=[pcx_id])['VpcPeeringConnections'][0]
            name = get_name_tag(pcx.get('Tags', []))
            return f"{name} (pcx)" if name else "(pcx)"
        except Exception:
            return f"{pcx_id} (pcx)"

    if route.get('InstanceId'):
        instance_id = route['InstanceId']
        try:
            instance = ec2_client.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
            name = get_name_tag(instance.get('Tags', []))
            public_ip = instance.get('PublicIpAddress')
            private_ip = instance.get('PrivateIpAddress')
            
            display_name = name if name else instance_id
            # public ip가 없으면 private ip라도 표시
            if public_ip:
                ip_str = f": {public_ip}"
            elif private_ip:
                ip_str = f": {private_ip}"
            else:
                ip_str = ""
            return f"{display_name} (instance{ip_str})"
        except Exception:
            return f"{instance_id} (instance)"
            
    return "N/A"


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
            
            explicit_route_tables = ec2_client.describe_route_tables(Filters=[{'Name': 'association.subnet-id', 'Values': [subnet['SubnetId']]}]).get('RouteTables', [])
            
            if not explicit_route_tables:
                main_route_table_resp = ec2_client.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc['VpcId']]}, {'Name': 'association.main', 'Values': ['true']}]).get('RouteTables', [])
                route_tables = main_route_table_resp if main_route_table_resp else []
            else:
                route_tables = explicit_route_tables

            if not route_tables:
                rows.append({"account": account_id, "region": region_name, "vpc_name": vpc_name, "vpc_cidr": vpc.get('CidrBlock', '-'), "subnet_name": subnet_name, "subnet_cidr": subnet.get('CidrBlock', '-'), "route_table": "Not Found", "route_rule": "-"})
                continue

            for rt in route_tables:
                rt_name = get_name_tag(rt.get('Tags', [])) or rt['RouteTableId']
                if not rt.get('Routes'):
                    rows.append({"account": account_id, "region": region_name, "vpc_name": vpc_name, "vpc_cidr": vpc.get('CidrBlock', '-'), "subnet_name": subnet_name, "subnet_cidr": subnet.get('CidrBlock', '-'), "route_table": rt_name, "route_rule": "No explicit routes"})
                else:
                    for route in rt.get('Routes', []):
                        dest = route.get('DestinationCidrBlock') or route.get('DestinationPrefixListId', 'N/A')
                        target = resolve_route_target(ec2_client, route)
                        dest_padded = dest.ljust(18)
                        rows.append({"account": account_id, "region": region_name, "vpc_name": vpc_name, "vpc_cidr": vpc.get('CidrBlock', '-'), "subnet_name": subnet_name, "subnet_cidr": subnet.get('CidrBlock', '-'), "route_table": rt_name, "route_rule": f"{dest_padded} -> {target}"})

    return rows


def print_vpc_table(all_rows):
    if not all_rows:
        console.print("[yellow]표시할 VPC 정보가 없습니다.[/yellow]")
        return
        
    all_rows.sort(key=lambda x: (x["account"], x["region"], x["vpc_name"], x["subnet_name"], x["route_table"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    # table.show_edge = False
    
    headers = ["Account", "Region", "VPC Name", "VPC CIDR", "Subnet Name", "Subnet CIDR", "Route Table", "Route Rule"]
    keys = ["account", "region", "vpc_name", "vpc_cidr", "subnet_name", "subnet_cidr", "route_table", "route_rule"]
    
    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("VPC Name", max_width=15, overflow="ellipsis",style="bold green")
    table.add_column("VPC CIDR",style="green")
    table.add_column("Subnet Name", max_width=11, overflow="ellipsis",style="cyan")
    table.add_column("Subnet CIDR",style="cyan")
    table.add_column("Route Table", max_width=35, overflow="ellipsis",style="white")
    table.add_column("Route Rule")


    last_account, last_region, last_vpc, last_subnet, last_route_table = None, None, None, None, None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region
        vpc_changed = row["vpc_name"] != last_vpc
        subnet_changed = row["subnet_name"] != last_subnet
        route_table_changed = row["route_table"] != last_route_table

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif vpc_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])
            elif subnet_changed:
                table.add_row("", "", "", "", *[Rule(style="dim") for _ in headers[4:]])
            elif route_table_changed:
                table.add_row("", "", "", "", "", "", *[Rule(style="dim") for _ in headers[6:]])

        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        display_values.append(row["vpc_name"] if account_changed or region_changed or vpc_changed else "")
        display_values.append(row["vpc_cidr"] if account_changed or region_changed or vpc_changed else "")
        display_values.append(row["subnet_name"] if account_changed or region_changed or vpc_changed or subnet_changed else "")
        display_values.append(row["subnet_cidr"] if account_changed or region_changed or vpc_changed or subnet_changed else "")
        display_values.append(row["route_table"] if account_changed or region_changed or vpc_changed or subnet_changed or route_table_changed else "")

        for k in keys[7:]:
            display_values.append(str(row.get(k, "-")))

        table.add_row(*display_values)
        
        last_account, last_region, last_vpc, last_subnet, last_route_table = row["account"], row["region"], row["vpc_name"], row["subnet_name"], row["route_table"]

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
    with ManualProgress("Collecting VPC information across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(fetch_vpc_one_account_region, acct, profile_name, reg, name_filter)
                    futures.append(future)
                    future_to_info[future] = (acct, reg)

            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    completed += 1
                    vpc_count = len(set(row['vpc_name'] for row in result))
                    progress.update(f"Processed {acct}/{reg} - Found {vpc_count} VPCs", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect VPC data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)

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
