#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import concurrent.futures
import time
import oci
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.rule import Rule
from rich import box
from common.log import log_info_non_console
from common.progress_decorator import progress_bar, ManualProgress
from src.ic.platforms.oci.common.utils import get_all_subscribed_regions, get_compartments

def add_arguments(parser):
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")
    parser.add_argument("--regions","-r", default=None, help="조회할 리전(,) 예: ap-seoul-1,us-ashburn-1")
    parser.add_argument("--output", default="table", choices=["tree", "table"], help="출력 형식 선택 (기본: table)")

@progress_bar("Collecting network security groups from compartment")
def fetch_nsg_one_comp(config, region, comp, name_filter):
    console = Console()
    results = []
    vcn_client = oci.core.VirtualNetworkClient(config)
    try:
        vcn_client.base_client.set_region(region)
    except Exception: pass

    try:
        nsg_list = vcn_client.list_network_security_groups(compartment_id=comp.id).data
    except Exception as e:
        console.print(f"[red][ERROR] NSG 조회 실패:[/red] region={region}, comp={comp.name}: {e}")
        return results

    for nsg in nsg_list:
        if name_filter and name_filter not in nsg.display_name.lower():
            continue
        try:
            rules = vcn_client.list_network_security_group_security_rules(nsg.id).data
            ing = [r for r in rules if r.direction == "INGRESS"]
        except Exception: ing = []

        if not ing:
            results.append({"region": region, "compartment_name": comp.name, "nsg_name": nsg.display_name, "desc": "(No Ingress Rules)", "proto": "-", "port_range": "-", "source": "-"})
        else:
            for rule in ing:
                proto_str = {"6": "TCP", "17": "UDP", "1": "ICMP"}.get(rule.protocol, rule.protocol)
                port_range = "-"
                if rule.tcp_options and rule.tcp_options.destination_port_range:
                    rng = rule.tcp_options.destination_port_range
                    port_range = f"{rng.min}-{rng.max}"
                elif rule.udp_options and rule.udp_options.destination_port_range:
                    rng = rule.udp_options.destination_port_range
                    port_range = f"{rng.min}-{rng.max}"
                
                source_str = rule.source or "-"
                if rule.source_type == "NETWORK_SECURITY_GROUP" and rule.source:
                    try:
                        source_str = vcn_client.get_network_security_group(rule.source).data.display_name
                    except Exception: pass
                
                results.append({"region": region, "compartment_name": comp.name, "nsg_name": nsg.display_name, "desc": rule.description or "-", "proto": proto_str, "port_range": port_range, "source": source_str})
    return results

@progress_bar("Collecting network security groups across compartments and regions")
def collect_nsg_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=20):
    start_ts = time.time()
    log_info_non_console("collect_nsg_parallel_fast start")
    all_rows, jobs = [], [(reg, comp) for reg in region_list for comp in compartments]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(fetch_nsg_one_comp, config, r, c, name_filter): (r, c) for r, c in jobs}
        for fut in concurrent.futures.as_completed(fut_map):
            try:
                all_rows.extend(fut.result())
            except Exception as e:
                console.print(f"[red]NSG Job failed[/red]: {fut_map[fut]}: {e}")
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_nsg_parallel_fast complete ({elapsed:.2f}s)")
    return all_rows

def group_nsg_data(nsg_rows):
    """NSG 데이터를 컴파트먼트 > 리전 > NSG 이름으로 그룹화"""
    grouped = {}
    for row in nsg_rows:
        comp = row['compartment_name']
        region = row['region']
        nsg_name = row['nsg_name']
        rule = {k: v for k, v in row.items() if k not in ['compartment_name', 'region', 'nsg_name']}
        
        grouped.setdefault(comp, {}).setdefault(region, {}).setdefault(nsg_name, []).append(rule)
    return grouped

def print_nsg_tree(console, nsg_rows):
    """NSG 정보를 트리 형식으로 출력"""
    if not nsg_rows:
        console.print("(No NSG)")
        return
        
    grouped_data = group_nsg_data(nsg_rows)
    
    console.print("\n[bold underline]NSG Inbound Rules[/bold underline]")
    tree = Tree("OCI Account", guide_style="bold cyan")

    sorted_comps = sorted(grouped_data.keys(), key=str.lower)
    for comp_name in sorted_comps:
        comp_branch = tree.add(f"[magenta bold]{comp_name}[/magenta bold]")

        sorted_regions = sorted(grouped_data[comp_name].keys(), key=str.lower)
        for region_name in sorted_regions:
            region_branch = comp_branch.add(f"[cyan]{region_name}[/cyan]")

            sorted_nsgs = sorted(grouped_data[comp_name][region_name].keys(), key=str.lower)
            for nsg_name in sorted_nsgs:
                nsg_branch = region_branch.add(f"[bold white]{nsg_name}[/bold white]")
                
                rules = grouped_data[comp_name][region_name][nsg_name]
                if not rules or rules[0]['desc'] == '(No Ingress Rules)':
                     nsg_branch.add("[dim](No Ingress Rules)[/dim]")
                     continue

                # 소스 문자열의 최대 길이를 계산하여 정렬
                max_source_len = 0
                for r in rules:
                    # 빈 규칙이 아닌 경우에만 길이를 계산
                    if r.get('source') and r['source'] != '-':
                        if len(r['source']) > max_source_len:
                            max_source_len = len(r['source'])
                
                # 기본 최소 길이 보장
                if max_source_len == 0: max_source_len = 10 

                for rule in rules:
                    desc_str = f" ([dim]Desc: {rule['desc']}[/dim])" if rule['desc'] and rule['desc'] != '-' else ""
                    
                    # 프로토콜과 소스 문자열을 패딩하여 길이를 맞춤
                    padded_proto = rule['proto'].ljust(4)
                    padded_source = rule['source'].ljust(max_source_len)

                    rule_str = f"[{padded_proto}] {rule['port_range']:<11} ← [yellow]{padded_source}[/yellow]{desc_str}"
                    nsg_branch.add(rule_str)

    console.print(tree)

def print_nsg_table(console, nsg_rows):
    if not nsg_rows:
        console.print("(No NSG)")
        return
    nsg_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["region"].lower(), x["nsg_name"].lower()))
    console.print("\n[bold underline]NSG Inbound Rules[/bold underline]")
    t = Table(show_lines=False, box=box.HORIZONTALS)
    headers = ["Compartment", "Region", "NSG Name", "Port Range", "Source", "Rule Desc", "Protocol"]
    for h in headers:
        t.add_column(h, style="bold magenta" if h == "Compartment" else "bold cyan" if h in ["Region", "NSG Name"] else "")
    
    last_comp = None
    last_region = None
    last_nsg = None
    for row in nsg_rows:
        comp_display = row['compartment_name'] if row['compartment_name'] != last_comp else ""
        if comp_display:
            if last_comp is not None:
                rule_row = [Rule(style="dim") for _ in headers]
                t.add_row(*rule_row)
            last_comp = row['compartment_name']
            last_region = None
            last_nsg = None
        
        region_display = row['region'] if row['region'] != last_region else ""
        if region_display:
            if last_region is not None:
                rule_row = [""] + [Rule(style="dim") for _ in range(len(headers) - 1)]
                t.add_row(*rule_row)
            last_region = row['region']
            last_nsg = None

        nsg_display = row['nsg_name'] if row['nsg_name'] != last_nsg else ""
        if nsg_display:
            if last_nsg is not None:
                rule_row = ["", ""] + [Rule(style="dim") for _ in range(len(headers) - 2)]
                t.add_row(*rule_row)
            last_nsg = row['nsg_name']

        t.add_row(comp_display, region_display, nsg_display, row["port_range"], row["source"], row["desc"], row["proto"])
    console.print(t)

@progress_bar("OCI Network Security Group Information Collection")
def main(args):
    console = Console()
    try:
        config = oci.config.from_file("~/.oci/config", "DEFAULT")
        identity_client = oci.identity.IdentityClient(config)
    except Exception as e:
        console.print(f"[red]OCI 설정 파일 로드 실패: {e}[/red]"); sys.exit(1)

    if args.regions:
        subscribed = get_all_subscribed_regions(identity_client, config["tenancy"])
        region_list = [r.strip() for r in args.regions.split(',') if r.strip() and r in subscribed]
        if not region_list:
            console.print("[red]유효한 리전이 없어 종료합니다[/red]"); sys.exit(0)
    else:
        region_list = get_all_subscribed_regions(identity_client, config["tenancy"])
    
    compartments = get_compartments(identity_client, config["tenancy"], args.compartment.lower() if args.compartment else None, console)
    nsg_rows = collect_nsg_parallel_fast(config, compartments, region_list, args.name.lower() if args.name else None, console)
    
    if args.output == 'tree':
        print_nsg_tree(console, nsg_rows)
    else:
        print_nsg_table(console, nsg_rows) 