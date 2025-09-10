#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import concurrent.futures
import time
import boto3
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.rule import Rule
from rich import box
from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import get_profiles, create_session

def add_arguments(parser):
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--account", "-a", default=None, help="계정 ID 필터 (부분 일치)")
    parser.add_argument("--regions", "-r", default=None, help="조회할 리전(,) 예: ap-northeast-2,us-east-1")
    parser.add_argument("--output", default="table", choices=["tree", "table"], help="출력 형식 선택 (기본: table)")

def fetch_sg_one_account_region(profile_name, account_id, region, name_filter):
    console = Console()
    results = []
    
    try:
        session = create_session(profile_name, region)
        if not session:
            return results
            
        ec2_client = session.client('ec2')
    except Exception as e:
        console.print(f"[red][ERROR] 세션 생성 실패:[/red] account={account_id}, region={region}: {e}")
        return results

    try:
        response = ec2_client.describe_security_groups()
        sg_list = response['SecurityGroups']
    except Exception as e:
        console.print(f"[red][ERROR] Security Group 조회 실패:[/red] account={account_id}, region={region}: {e}")
        return results

    for sg in sg_list:
        sg_name = sg.get('GroupName', sg['GroupId'])
        if name_filter and name_filter not in sg_name.lower():
            continue
            
        ingress_rules = sg.get('IpPermissions', [])
        
        if not ingress_rules:
            results.append({
                "account_id": account_id,
                "region": region,
                "sg_name": sg_name,
                "sg_id": sg['GroupId'],
                "desc": "(No Ingress Rules)",
                "proto": "-",
                "port_range": "-",
                "source": "-"
            })
        else:
            for rule in ingress_rules:
                proto_str = rule.get('IpProtocol', '-')
                if proto_str == 'tcp':
                    proto_str = 'TCP'
                elif proto_str == 'udp':
                    proto_str = 'UDP'
                elif proto_str == 'icmp':
                    proto_str = 'ICMP'
                elif proto_str == '-1':
                    proto_str = 'ALL'
                
                # 포트 범위 처리
                port_range = "-"
                if rule.get('FromPort') is not None and rule.get('ToPort') is not None:
                    if rule['FromPort'] == rule['ToPort']:
                        port_range = str(rule['FromPort'])
                    else:
                        port_range = f"{rule['FromPort']}-{rule['ToPort']}"
                elif proto_str == 'ALL':
                    port_range = "ALL"
                
                # 소스 처리
                sources = []
                
                # IP 범위
                for ip_range in rule.get('IpRanges', []):
                    desc = ip_range.get('Description', '')
                    cidr = ip_range['CidrIp']
                    source_str = f"{cidr}"
                    if desc:
                        source_str += f" ({desc})"
                    sources.append(source_str)
                
                # IPv6 범위
                for ipv6_range in rule.get('Ipv6Ranges', []):
                    desc = ipv6_range.get('Description', '')
                    cidr = ipv6_range['CidrIpv6']
                    source_str = f"{cidr}"
                    if desc:
                        source_str += f" ({desc})"
                    sources.append(source_str)
                
                # 다른 Security Group 참조
                for sg_ref in rule.get('UserIdGroupPairs', []):
                    sg_id = sg_ref.get('GroupId', '')
                    sg_desc = sg_ref.get('Description', '')
                    source_str = f"sg:{sg_id}"
                    if sg_desc:
                        source_str += f" ({sg_desc})"
                    sources.append(source_str)
                
                # Prefix List
                for prefix_list in rule.get('PrefixListIds', []):
                    pl_id = prefix_list['PrefixListId']
                    pl_desc = prefix_list.get('Description', '')
                    source_str = f"pl:{pl_id}"
                    if pl_desc:
                        source_str += f" ({pl_desc})"
                    sources.append(source_str)
                
                if not sources:
                    sources = ["-"]
                
                for source in sources:
                    results.append({
                        "account_id": account_id,
                        "region": region,
                        "sg_name": sg_name,
                        "sg_id": sg['GroupId'],
                        "desc": source.split('(', 1)[1].rstrip(')') if '(' in source else "-",
                        "proto": proto_str,
                        "port_range": port_range,
                        "source": source.split('(')[0].strip() if '(' in source else source
                    })
    
    return results

def collect_sg_parallel_fast(profiles, account_filter, region_list, name_filter, console, max_workers=20):
    start_ts = time.time()
    log_info_non_console("collect_sg_parallel_fast start")
    
    all_rows = []
    jobs = []
    
    # 작업 목록 생성
    for account_id, profile_name in profiles.items():
        if account_filter and account_filter not in account_id:
            continue
        for region in region_list:
            jobs.append((profile_name, account_id, region))
    
    total_operations = len(jobs)
    
    with ManualProgress("Collecting Security Group information across accounts and regions", total=total_operations) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            future_to_info = {}
            
            for profile, account, region in jobs:
                future = executor.submit(fetch_sg_one_account_region, profile, account, region, name_filter)
                futures.append(future)
                future_to_info[future] = (account, region)
            
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                account, region = future_to_info[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    completed += 1
                    sg_count = len(set(row['sg_name'] for row in result))
                    progress.update(f"Processed {account}/{region} - Found {sg_count} Security Groups", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect SG data for {account}/{region}: {e}")
                    progress.update(f"Failed {account}/{region} - {str(e)[:50]}...", advance=1)
    
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_sg_parallel_fast complete ({elapsed:.2f}s)")
    return all_rows

def group_sg_data(sg_rows):
    """SG 데이터를 계정 > 리전 > SG 이름으로 그룹화"""
    grouped = {}
    for row in sg_rows:
        account = row['account_id']
        region = row['region']
        sg_name = row['sg_name']
        rule = {k: v for k, v in row.items() if k not in ['account_id', 'region', 'sg_name']}
        
        grouped.setdefault(account, {}).setdefault(region, {}).setdefault(sg_name, []).append(rule)
    return grouped

def print_sg_tree(console, sg_rows):
    """SG 정보를 트리 형식으로 출력"""
    if not sg_rows:
        console.print("(No Security Groups)")
        return
        
    grouped_data = group_sg_data(sg_rows)
    
    console.print("\n[bold underline]Security Group Inbound Rules[/bold underline]")
    tree = Tree("AWS Account", guide_style="bold cyan")

    sorted_accounts = sorted(grouped_data.keys(), key=str.lower)
    for account_id in sorted_accounts:
        account_branch = tree.add(f"[magenta bold]{account_id}[/magenta bold]")

        sorted_regions = sorted(grouped_data[account_id].keys(), key=str.lower)
        for region_name in sorted_regions:
            region_branch = account_branch.add(f"[cyan]{region_name}[/cyan]")

            sorted_sgs = sorted(grouped_data[account_id][region_name].keys(), key=str.lower)
            for sg_name in sorted_sgs:
                sg_branch = region_branch.add(f"[bold white]{sg_name}[/bold white]")
                
                rules = grouped_data[account_id][region_name][sg_name]
                if not rules or rules[0]['desc'] == '(No Ingress Rules)':
                    sg_branch.add("[dim](No Ingress Rules)[/dim]")
                    continue

                # 소스 문자열의 최대 길이를 계산하여 정렬
                max_source_len = 0
                for r in rules:
                    if r.get('source') and r['source'] != '-':
                        if len(r['source']) > max_source_len:
                            max_source_len = len(r['source'])
                
                # 기본 최소 길이 보장
                if max_source_len == 0: 
                    max_source_len = 10 

                for rule in rules:
                    desc_str = f" ([dim]Desc: {rule['desc']}[/dim])" if rule['desc'] and rule['desc'] != '-' else ""
                    
                    # 프로토콜과 소스 문자열을 패딩하여 길이를 맞춤
                    padded_proto = rule['proto'].ljust(4)
                    padded_source = rule['source'].ljust(max_source_len)

                    rule_str = f"[{padded_proto}] {rule['port_range']:<11} ← [yellow]{padded_source}[/yellow]{desc_str}"
                    sg_branch.add(rule_str)

    console.print(tree)

def print_sg_table(console, sg_rows):
    if not sg_rows:
        console.print("(No Security Groups)")
        return
        
    sg_rows.sort(key=lambda x: (x["account_id"].lower(), x["region"].lower(), x["sg_name"].lower()))
    console.print("\n[bold underline]Security Group Inbound Rules[/bold underline]")
    
    t = Table(show_lines=False, box=box.HORIZONTALS)
    headers = ["Account", "Region", "SG Name", "Port Range", "Source", "Rule Desc", "Protocol"]
    for h in headers:
        t.add_column(h, style="bold magenta" if h == "Account" else "bold cyan" if h in ["Region", "SG Name"] else "")
    
    last_account = None
    last_region = None
    last_sg = None
    
    for row in sg_rows:
        account_display = row['account_id'] if row['account_id'] != last_account else ""
        if account_display:
            if last_account is not None:
                rule_row = [Rule(style="dim") for _ in headers]
                t.add_row(*rule_row)
            last_account = row['account_id']
            last_region = None
            last_sg = None
        
        region_display = row['region'] if row['region'] != last_region else ""
        if region_display:
            if last_region is not None:
                rule_row = [""] + [Rule(style="dim") for _ in range(len(headers) - 1)]
                t.add_row(*rule_row)
            last_region = row['region']
            last_sg = None

        sg_display = row['sg_name'] if row['sg_name'] != last_sg else ""
        if sg_display:
            if last_sg is not None:
                rule_row = ["", ""] + [Rule(style="dim") for _ in range(len(headers) - 2)]
                t.add_row(*rule_row)
            last_sg = row['sg_name']

        t.add_row(
            account_display, 
            region_display, 
            sg_display, 
            row["port_range"], 
            row["source"], 
            row["desc"], 
            row["proto"]
        )
    
    console.print(t)

def main(args):
    console = Console()
    
    try:
        profiles = get_profiles()
        if not profiles:
            console.print("[red]AWS 프로파일을 찾을 수 없습니다[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]AWS 프로파일 로드 실패: {e}[/red]")
        sys.exit(1)

    # 리전 목록 처리
    if args.regions:
        region_list = [r.strip() for r in args.regions.split(',') if r.strip()]
        if not region_list:
            console.print("[red]유효한 리전이 없어 종료합니다[/red]")
            sys.exit(0)
    else:
        # 기본 리전들
        region_list = ['ap-northeast-2', 'us-east-1', 'us-west-2', 'eu-west-1']
    
    sg_rows = collect_sg_parallel_fast(
        profiles, 
        args.account.lower() if args.account else None, 
        region_list, 
        args.name.lower() if args.name else None, 
        console
    )
    
    if args.output == 'tree':
        print_sg_tree(console, sg_rows)
    else:
        print_sg_table(console, sg_rows)