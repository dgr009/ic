#!/usr/bin/env python3
import os
import sys
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import (
    get_env_accounts,
    get_profiles,
    DEFINED_REGIONS
)

load_dotenv()
console = Console()

def color_state(state_name: str):
    s = state_name.lower()
    if s == "running":
        return f"[bold green]{state_name}[/bold green]"
    elif s == "stopped":
        return f"[bold yellow]{state_name}[/bold yellow]"
    elif s == "terminated":
        return f"[bold red]{state_name}[/bold red]"
    elif s == "pending":
        return f"[bold cyan]{state_name}[/bold cyan]"
    elif s == "shutting-down":
        return f"[bold magenta]{state_name}[/bold magenta]"
    else:
        return state_name

def fetch_ec2_one_account_region(account_id, profile_name, region_name, name_filter):
    log_info_non_console(f"EC2 인스턴스 정보 수집 시작: Account={account_id}, Region={region_name}")
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    ec2_client = session.client("ec2", region_name=region_name)

    all_instances = []
    try:
        paginator = ec2_client.get_paginator("describe_instances")
        page_count = 0
        for page in paginator.paginate():
            page_count += 1
            log_info_non_console(f"Processing page {page_count} for {account_id}/{region_name}")
            
            for rsv in page["Reservations"]:
                for inst in rsv["Instances"]:
                    if inst['State']['Name'] == 'terminated':
                        continue
                    
                    inst_name = next((t.get('Value') for t in inst.get('Tags', []) if t.get('Key') == 'Name'), None)

                    if name_filter and name_filter not in (inst_name or ''):
                        continue
                    all_instances.append(inst)
        
        log_info_non_console(f"Found {len(all_instances)} instances across {page_count} pages for {account_id}/{region_name}")
    except Exception as e:
        log_info_non_console(f"EC2 인스턴스 목록 조회 실패: {e}")
        return []

    if not all_instances:
        return []

    # Collect resource IDs for batch lookups
    subnet_ids = {inst["SubnetId"] for inst in all_instances if "SubnetId" in inst}
    sg_ids = {sgi["GroupId"] for inst in all_instances for sgi in inst.get("SecurityGroups", [])}
    volume_ids = {bdm["Ebs"]["VolumeId"] for inst in all_instances for bdm in inst.get("BlockDeviceMappings", []) if "Ebs" in bdm and "VolumeId" in bdm["Ebs"]}
    instance_types = {inst["InstanceType"] for inst in all_instances if "InstanceType" in inst}
    
    log_info_non_console(f"Collecting resource details: {len(subnet_ids)} subnets, {len(sg_ids)} security groups, {len(volume_ids)} volumes, {len(instance_types)} instance types")

    def get_resource_map(resource_ids, describe_func, result_key, id_key, value_key, resource_type):
        resource_map = {}
        if not resource_ids:
            return resource_map
        try:
            log_info_non_console(f"Fetching {len(resource_ids)} {resource_type} details for {account_id}/{region_name}")
            response = describe_func(**{f"{id_key}s": list(resource_ids)})
            for item in response[result_key]:
                name = item.get(value_key)
                if value_key == "Tags":
                    name = next((t['Value'] for t in item.get('Tags', []) if t['Key'] == 'Name'), item[id_key.replace('Id', 's')[:-1] + 'Id'])
                elif not name:
                    name = item[id_key]
                resource_map[item[id_key]] = name
            log_info_non_console(f"Successfully fetched {len(resource_map)} {resource_type} details")
        except Exception as e:
            log_info_non_console(f"{result_key} 정보 조회 실패: {e}")
        return resource_map

    subnet_map = get_resource_map(subnet_ids, ec2_client.describe_subnets, "Subnets", "SubnetId", "Tags", "subnets")
    sg_map = get_resource_map(sg_ids, ec2_client.describe_security_groups, "SecurityGroups", "GroupId", "GroupName", "security groups")
    
    volume_map = {}
    if volume_ids:
        try:
            log_info_non_console(f"Fetching {len(volume_ids)} volume details for {account_id}/{region_name}")
            vol_resp = ec2_client.describe_volumes(VolumeIds=list(volume_ids))
            for v in vol_resp["Volumes"]:
                volume_map[v["VolumeId"]] = v["Size"]
            log_info_non_console(f"Successfully fetched {len(volume_map)} volume details")
        except Exception as e:
            log_info_non_console(f"Volume 정보 조회 실패: {e}")

    insttype_map = {}
    if instance_types:
        try:
            log_info_non_console(f"Fetching {len(instance_types)} instance type details for {account_id}/{region_name}")
            itype_resp = ec2_client.describe_instance_types(InstanceTypes=list(instance_types))
            for tinfo in itype_resp["InstanceTypes"]:
                itype = tinfo["InstanceType"]
                vcpu = tinfo["VCpuInfo"]["DefaultVCpus"]
                mem_gb = int(tinfo["MemoryInfo"]["SizeInMiB"] / 1024.0)
                insttype_map[itype] = (vcpu, mem_gb)
            log_info_non_console(f"Successfully fetched {len(insttype_map)} instance type details")
        except Exception as e:
            log_info_non_console(f"InstanceType 정보 조회 실패: {e}")

    rows = []
    for inst in all_instances:
        itype = inst.get("InstanceType", "-")
        vcpu, mem_gb = insttype_map.get(itype, ("?", "?"))
        
        total_vol = sum(volume_map.get(bdm["Ebs"]["VolumeId"], 0) for bdm in inst.get("BlockDeviceMappings", []) if "Ebs" in bdm and "VolumeId" in bdm["Ebs"])

        tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}

        rows.append({
            "account": account_id,
            "region": region_name,
            "name": tags.get('Name', inst["InstanceId"]),
            "state": color_state(inst["State"]["Name"]),
            "private_ip": inst.get("PrivateIpAddress", "-"),
            "public_ip": inst.get("PublicIpAddress", "-"),
            "itype": itype,
            "vcpu": str(vcpu),
            "memory": str(mem_gb),
            "vol_size": str(total_vol),
            "subnet": subnet_map.get(inst.get("SubnetId"), "-"),
            "sgs": ", ".join([sg_map.get(sgi["GroupId"], sgi["GroupId"]) for sgi in inst.get("SecurityGroups", [])]),
            "created_by": tags.get('CreateBy', '-')
        })
    return rows

def print_ec2_table(all_rows, verbose):
    if not all_rows:
        console.print("[yellow]표시할 EC2 인스턴스 정보가 없습니다.[/yellow]")
        return
    
    all_rows.sort(key=lambda x: (x["account"], x["region"], x["name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    # table.show_edge = False
  
    if verbose:
        headers = ["Account", "Region", "Instance Name", "State", "Private IP", "Public IP", "Type", "vCPU", "Memory", "Volume", "Subnet", "Security Groups", "Create"]
        keys = ["account", "region", "name", "state", "private_ip", "public_ip", "itype", "vcpu", "memory", "vol_size", "subnet", "sgs", "created_by"]
    else:
        headers = ["Account", "Region", "Name", "State", "Private IP", "Public IP", "Type", "CPU", "Mem", "Vol"]
        keys = ["account", "region", "name", "state", "private_ip", "public_ip", "itype", "vcpu", "memory", "vol_size"]

    for h in headers:
        style = {}
        if h == "Account": style = {"style": "bold magenta"}
        elif h == "Region": style = {"style": "bold cyan"}
        elif h in ["vCPU", "Memory", "Volume", "CPU", "Mem", "Vol"]: style = {"justify": "right"}
        elif h == "State": style = {"justify": "center"}
        table.add_column(h, **style)

    last_account = None
    last_region = None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif not account_changed and not region_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in range(len(headers) - 2)])
        
        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        
        for k in keys[2:]:
            display_values.append(str(row.get(k, "-")))
        
        table.add_row(*display_values)

        last_account = row["account"]
        last_region = row["region"]
        
    console.print(table)

def main(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    name_filter = args.name.lower() if hasattr(args, 'name') and args.name else None

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
    with ManualProgress("Collecting EC2 instances across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(fetch_ec2_one_account_region, acct, profile_name, reg, name_filter)
                    futures.append(future)
                    future_to_info[future] = (acct, reg)

            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    completed += 1
                    progress.update(f"Processed {acct}/{reg} - Found {len(result)} instances", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect EC2 data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)

    print_ec2_table(all_rows, args.verbose)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-n', '--name', help='인스턴스 이름 필터 (부분 일치)')
    parser.add_argument('-v', '--verbose', action='store_true', help='상세 정보 출력')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EC2 인스턴스 정보 (병렬 수집)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)