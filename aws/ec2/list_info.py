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

from common.utils import (
    get_env_accounts,    # .env => AWS_ACCOUNTS
    get_profiles,        # ~/.aws/config => (account_id -> profile)
    DEFINED_REGIONS      # 기본 리전 목록
)

load_dotenv()
console = Console()

################################################################################
# 상태 컬러링 함수
################################################################################
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

################################################################################
# Client 기반 인스턴스 정보 수집 (빠른 방식)
################################################################################
def fetch_ec2_data_fast(account_id, profile_name, region_name):
    """
    한 (account, region)에 대해:
      1) describe_instances() 등으로 인스턴스 목록 수집
      2) Subnet, SG, Volume, InstanceType 정보를 일괄 조회
      3) 인스턴스별로 Name 태그, 상태, IP, vCPU/Memory, 볼륨합계, SG/Subnet 이름 등 매핑
      4) 최종 rows를 리턴
    """
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    ec2_client = session.client("ec2", region_name=region_name)

    # 1) describe_instances()
    all_instances = []
    paginator = ec2_client.get_paginator("describe_instances")
    # paginator로 전체 인스턴스를 페이징 처리
    for page in paginator.paginate():
        for rsv in page["Reservations"]:
            for inst in rsv["Instances"]:
                all_instances.append(inst)

    if not all_instances:
        return []

    # 2) 필요한 ID들 모으기 (subnet, SG, volume, instance_types)
    subnet_ids = set()
    sg_ids = set()
    volume_ids = set()
    instance_types = set()

    for inst in all_instances:
        if "SubnetId" in inst:
            subnet_ids.add(inst["SubnetId"])
        if "SecurityGroups" in inst:
            for sgi in inst["SecurityGroups"]:
                sg_ids.add(sgi["GroupId"])
        if "BlockDeviceMappings" in inst:
            for bdm in inst["BlockDeviceMappings"]:
                if "Ebs" in bdm and "VolumeId" in bdm["Ebs"]:
                    volume_ids.add(bdm["Ebs"]["VolumeId"])
        if "InstanceType" in inst:
            instance_types.add(inst["InstanceType"])

    # 2-A) Subnet
    subnet_map = {}
    if subnet_ids:
        try:
            sub_resp = ec2_client.describe_subnets(SubnetIds=list(subnet_ids))
            for s in sub_resp["Subnets"]:
                # 서브넷 Name 태그
                sname = None
                if "Tags" in s:
                    for t in s["Tags"]:
                        if t["Key"] == "Name":
                            sname = t["Value"]
                            break
                if not sname:
                    sname = s["SubnetId"]
                subnet_map[s["SubnetId"]] = sname
        except:
            pass

    # 2-B) SG
    sg_map = {}
    if sg_ids:
        try:
            sg_resp = ec2_client.describe_security_groups(GroupIds=list(sg_ids))
            for sg in sg_resp["SecurityGroups"]:
                sgname = None
                if "Tags" in sg:
                    for t in sg["Tags"]:
                        if t["Key"] == "Name":
                            sgname = t["Value"]
                            break
                if not sgname:
                    if sg["GroupName"] != "default":
                        sgname = sg["GroupName"]
                    else:
                        sgname = sg["GroupId"]
                sg_map[sg["GroupId"]] = sgname
        except:
            pass

    # 2-C) Volume
    volume_map = {}
    if volume_ids:
        try:
            vol_resp = ec2_client.describe_volumes(VolumeIds=list(volume_ids))
            for v in vol_resp["Volumes"]:
                volume_map[v["VolumeId"]] = v["Size"]  # GB
        except:
            pass

    # 2-D) InstanceType
    insttype_map = {}
    if instance_types:
        try:
            itype_resp = ec2_client.describe_instance_types(InstanceTypes=list(instance_types))
            for tinfo in itype_resp["InstanceTypes"]:
                itype = tinfo["InstanceType"]
                vcpu = tinfo["VCpuInfo"]["DefaultVCpus"]
                mem_gb = int(tinfo["MemoryInfo"]["SizeInMiB"] / 1024.0)
                insttype_map[itype] = (vcpu, f"{mem_gb}GB")
        except:
            pass

    # 3) 인스턴스별 정보 파싱
    rows = []
    for inst in all_instances:
        inst_id = inst["InstanceId"]
        state_name = inst["State"]["Name"]
        state_colored = color_state(state_name)
        itype = inst.get("InstanceType", "-")

        # Name 태그
        name_tag = inst_id
        if "Tags" in inst:
            for t in inst["Tags"]:
                if t["Key"] == "Name":
                    name_tag = t["Value"]
                    break

        # Subnet
        sn_id = inst.get("SubnetId")
        subnet_str = subnet_map.get(sn_id, "-")

        # SG
        sg_list = []
        if "SecurityGroups" in inst:
            for sgi in inst["SecurityGroups"]:
                sg_id = sgi["GroupId"]
                sg_name = sg_map.get(sg_id, sg_id)
                sg_list.append(sg_name)
        sgs_str = ", ".join(sg_list) if sg_list else "-"

        # IP
        private_ip = inst.get("PrivateIpAddress", "-")
        public_ip = inst.get("PublicIpAddress", "-")

        # InstanceType info
        vcpu = "?"
        mem_str = "?"
        if itype in insttype_map:
            vcpu, mem_str = insttype_map[itype]

        # 볼륨 합계
        total_vol = 0
        if "BlockDeviceMappings" in inst:
            for bdm in inst["BlockDeviceMappings"]:
                if "Ebs" in bdm and "VolumeId" in bdm["Ebs"]:
                    vid = bdm["Ebs"]["VolumeId"]
                    size_gb = volume_map.get(vid, 0)
                    total_vol += size_gb

        rows.append({
            "account": account_id,
            "region": region_name,
            "name": name_tag,
            "state": state_colored,
            "subnet": subnet_str,
            "sgs": sgs_str,
            "private_ip": private_ip,
            "public_ip": public_ip,
            "itype": itype,
            "vcpu": str(vcpu),
            "memory": mem_str,
            "vol_size": f"{total_vol}GB"
        })

    return rows

################################################################################
# 실제 main(args) - (account, region) 병렬 처리
################################################################################
def main(args):
    # 1) 계정 목록 결정
    if args.account:
        accounts = args.account.split(",")
    else:
        accounts = get_env_accounts()  # .env => AWS_ACCOUNTS

    # 2) 리전 목록 결정
    if args.regions:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    else:
        regions = DEFINED_REGIONS

    # 3) 프로파일 매핑
    profiles_map = get_profiles()  # { '111111111111': 'acc111-profile', ... }

    # 4) (account, region) 병렬 수집
    tasks = []
    with ThreadPoolExecutor() as executor:
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                console.print(f"[red]No profile found for account {acct}[/red]")
                continue
            for reg in regions:
                fut = executor.submit(fetch_ec2_data_fast, acct, profile_name, reg)
                tasks.append((acct, reg, fut))

    # 결과 dict: data[(acct,reg)] = list of row
    data = {}
    for (acct, reg, fut) in tasks:
        rows = fut.result()
        data.setdefault((acct, reg), []).extend(rows)

    # 5) 출력
    #    (계정, 리전)별로 구분. sort by instance name
    all_keys = sorted(data.keys(), key=lambda x: (x[0], x[1]))
    prev_account = None

    for (acct, reg) in all_keys:
        rows = data[(acct, reg)]
        if not rows:
            continue

        # 인스턴스 name 정렬
        rows.sort(key=lambda r: r["name"])

        # account 바뀔 때마다 구분선
        if acct != prev_account:
            prof = profiles_map.get(acct, "???")
            console.rule(f"Account: {acct} [bold magenta]({prof})[/bold magenta]",
                         style="bold magenta", align="left")
            prev_account = acct

        # region 구분선
        console.rule(f"Region: [bold cyan]{reg}[/bold cyan]", style="bold cyan", align="left")

        # 테이블
        table = Table(show_header=True, header_style="bold white", box=box.MINIMAL_DOUBLE_HEAD)
        table.add_column("Instance Name")
        table.add_column("State")
        table.add_column("Subnet")
        table.add_column("SGs")
        table.add_column("PrivateIP")
        table.add_column("PublicIP")
        table.add_column("Type")
        table.add_column("vCPU")
        table.add_column("Memory")
        table.add_column("VolumeSize")

        for rinfo in rows:
            table.add_row(
                rinfo["name"],
                rinfo["state"],
                rinfo["subnet"],
                rinfo["sgs"],
                rinfo["private_ip"],
                rinfo["public_ip"],
                rinfo["itype"],
                rinfo["vcpu"],
                rinfo["memory"],
                rinfo["vol_size"]
            )

        console.print(table)
        console.print()  # blank line


def add_arguments(parser):
    """
    기존과 동일하게 인자 정의:
      -a, --account => 여러 계정(,) 가능
      -r, --regions => 여러 리전(,) 가능
    """
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EC2 인스턴스 정보 (Client-based 병렬수집)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
