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

# ###############################################################################
# # CLI 인자 정의
# ###############################################################################
def add_arguments(parser):
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")
    parser.add_argument("--regions","-r", default=None, help="조회할 리전(,) 예: ap-seoul-1,us-ashburn-1")
    parser.add_argument("--output", default="table", choices=["tree", "table"], help="출력 형식 선택 (기본: table)")

###############################################################################
# LB 정보 수집
###############################################################################
@progress_bar("Collecting load balancers from compartment")
def fetch_lb_one_comp(config, region, comp, name_filter):
    console = Console()
    results = []
    ip_to_vm_name = {}

    # VM IP와 이름을 매핑합니다.
    try:
        compute_client = oci.core.ComputeClient(config)
        compute_client.base_client.set_region(region)
        network_client = oci.core.VirtualNetworkClient(config)
        network_client.base_client.set_region(region)

        instances = oci.pagination.list_call_get_all_results(compute_client.list_instances, compartment_id=comp.id).data
        instance_map = {i.id: i.display_name for i in instances}

        if instance_map:
            vnic_attachments = oci.pagination.list_call_get_all_results(compute_client.list_vnic_attachments, compartment_id=comp.id).data
            for attachment in vnic_attachments:
                if attachment.vnic_id and attachment.instance_id in instance_map:
                    try:
                        vnic = network_client.get_vnic(vnic_id=attachment.vnic_id).data
                        if vnic and vnic.private_ip:
                            ip_to_vm_name[vnic.private_ip] = instance_map[attachment.instance_id]
                    except oci.exceptions.ServiceError:
                        continue # VNIC가 삭제되었을 수 있음
    except Exception as e:
        console.print(f"[red][ERROR] VM Info 조회 실패 (LB Backend용):[/red] region={region}, comp={comp.name}: {e}")
    
    try:
        lb_client_main = oci.load_balancer.LoadBalancerClient(config)
        lb_client_main.base_client.set_region(region)
        lb_list = [lb for lb in lb_client_main.list_load_balancers(compartment_id=comp.id).data if not name_filter or name_filter in lb.display_name.lower()]
    except Exception as e:
        console.print(f"[red][ERROR] LB 조회 실패:[/red] region={region}, comp={comp.name}: {e}")
        return results

    def process_lb(lb_obj):
        start_ts = time.time()
        log_info_non_console(f"lb data collection : {comp.name} - {region} : {lb_obj.display_name}")

        lb_client = oci.load_balancer.LoadBalancerClient(config)
        try:
            lb_client.base_client.set_region(region)
        except Exception: pass

        lb_state = lb_obj.lifecycle_state
        shape_name = lb_obj.shape_name or "-"
        ip_addr_str = ", ".join([ip.ip_address or "-" for ip in lb_obj.ip_addresses]) if lb_obj.ip_addresses else "-"
        lb_type = "PRIVATE" if getattr(lb_obj, 'is_private', False) else "PUBLIC"

        min_bw, max_bw = "-", "-"
        if sd := getattr(lb_obj, "shape_details", None):
            if mbw := getattr(sd, "minimum_bandwidth_in_mbps", None): min_bw = str(mbw)
            if xbw := getattr(sd, "maximum_bandwidth_in_mbps", None): max_bw = str(xbw)

        rows = []
        try:
            bsets = lb_client.list_backend_sets(load_balancer_id=lb_obj.id).data
        except Exception: bsets = []

        if not bsets:
            rows.append({
                "region": region, "compartment_name": comp.name, "lb_name": lb_obj.display_name, "lb_state": lb_state,
                "ip_addrs": ip_addr_str, "shape": shape_name, "min_bw": min_bw, "max_bw": max_bw, "lb_type": lb_type,
                "backend_set": "(No Backend Sets)", "backend_target": "-", "vm_display_name": "-", "backend_health": "-"
            })
        else:
            for bset in bsets:
                try:
                    backends = lb_client.list_backends(load_balancer_id=lb_obj.id, backend_set_name=bset.name).data
                    health_map = {}
                    try:
                        bset_health = lb_client.get_backend_set_health(load_balancer_id=lb_obj.id, backend_set_name=bset.name).data
                        if bset_health:
                            # 1. 만약 전체 상태가 OK이면, 일단 모든 백엔드를 OK로 간주.
                            if bset_health.status == 'OK':
                                for be in backends:
                                    health_map[be.name] = 'OK'
                            
                            # 2. 특정 상태 목록에 있는 백엔드들의 상태를 덮어씀 (더 정확한 상태로).
                            for be_name in getattr(bset_health, 'critical_state_backend_names', []):
                                health_map[be_name] = "CRITICAL"
                            for be_name in getattr(bset_health, 'warning_state_backend_names', []):
                                health_map[be_name] = "WARNING"
                            for be_name in getattr(bset_health, 'unknown_state_backend_names', []):
                                health_map[be_name] = "UNKNOWN"
                                
                    except oci.exceptions.ServiceError as e:
                        if e.status != 404:
                            log_info_non_console(f"Could not get health for bset '{bset.name}': {e.message}")
                    except Exception as e:
                        log_info_non_console(f"An unexpected error occurred while getting health for '{bset.name}': {e}")

                except Exception as e:
                    backends = []
                    health_map = {}
                    log_info_non_console(f"Could not list backends for bset '{bset.name}': {e}")

                if not backends:
                    rows.append({
                        "region": region, "compartment_name": comp.name, "lb_name": lb_obj.display_name, "lb_state": lb_state,
                        "ip_addrs": ip_addr_str, "shape": shape_name, "min_bw": min_bw, "max_bw": max_bw, "lb_type": lb_type,
                        "backend_set": bset.name, "backend_target": "(No Backends)", "vm_display_name": "-", "backend_health": "-"
                    })
                else:
                    for backend in backends:
                        health_status = health_map.get(backend.name, "UNKNOWN")
                        target_ip = backend.name.split(':')[0]
                        vm_display_name = ip_to_vm_name.get(target_ip, "-")
                        rows.append({
                            "region": region, "compartment_name": comp.name, "lb_name": lb_obj.display_name, "lb_state": lb_state,
                            "ip_addrs": ip_addr_str, "shape": shape_name, "min_bw": min_bw, "max_bw": max_bw, "lb_type": lb_type,
                            "backend_set": bset.name, "backend_target": backend.name, "vm_display_name": vm_display_name, "backend_health": health_status
                        })
        
        elapsed = time.time() - start_ts
        log_info_non_console(f"lb data collection complete : {lb_obj.display_name} ({elapsed:.2f}s)")
        return rows

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as lb_pool:
        all_futs = [lb_pool.submit(process_lb, lb) for lb in lb_list]
        for fut in concurrent.futures.as_completed(all_futs):
            results.extend(fut.result())
    return results

@progress_bar("Collecting load balancers across compartments and regions")
def collect_lb_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=20):
    start_ts = time.time()
    log_info_non_console("collect_lb_parallel_fast start")
    all_rows, jobs = [], [(reg, comp) for reg in region_list for comp in compartments]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(fetch_lb_one_comp, config, r, c, name_filter): (r, c) for r, c in jobs}
        for fut in concurrent.futures.as_completed(fut_map):
            try:
                all_rows.extend(fut.result())
            except Exception as e:
                console.print(f"[red]LB Job failed[/red] {fut_map[fut]}: {e}")
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_lb_parallel_fast complete ({elapsed:.2f}s)")
    return all_rows

###############################################################################
# 데이터 그룹화 및 출력
###############################################################################
def group_lb_data(lb_rows):
    """LB 데이터를 컴파트먼트 > 리전 > LB > Backend Set 으로 그룹화"""
    grouped = {}
    for row in lb_rows:
        comp = row['compartment_name']
        region = row['region']
        lb_name = row['lb_name']
        bset_name = row['backend_set']
        
        # LB 정보 (한번만 저장)
        lb_info = grouped.setdefault(comp, {}).setdefault(region, {}).setdefault(lb_name, {'details': None, 'backend_sets': {}})
        if not lb_info['details']:
            lb_info['details'] = {
                'lb_state': row['lb_state'],
                'ip_addrs': row['ip_addrs'],
                'shape': row['shape'],
                'min_bw': row['min_bw'],
                'max_bw': row['max_bw'],
                'lb_type': row['lb_type']
            }
        
        # Backend Set 및 Target 정보
        if bset_name not in ["(No Backend Sets)", "(No Backends)"]:
            bset_list = lb_info['backend_sets'].setdefault(bset_name, [])
            if row['backend_target'] not in ['-', '(No Backends)']:
                bset_list.append({'name': row['backend_target'], 'health': row['backend_health'], 'vm_name': row.get('vm_display_name', '-')})

    return grouped

def print_lb_tree(console, lb_rows):
    """LB 정보를 트리 형식으로 출력"""
    if not lb_rows:
        console.print("(No LBs)")
        return

    grouped_data = group_lb_data(lb_rows)
    console.print("\n[bold underline]LoadBalancer Info[/bold underline]")
    tree = Tree("OCI Account", guide_style="bold cyan")

    sorted_comps = sorted(grouped_data.keys(), key=str.lower)
    for comp_name in sorted_comps:
        comp_branch = tree.add(f"[magenta bold]{comp_name}[/magenta bold]")

        sorted_regions = sorted(grouped_data[comp_name].keys(), key=str.lower)
        for region_name in sorted_regions:
            region_branch = comp_branch.add(f"[cyan]{region_name}[/cyan]")
            
            sorted_lbs = sorted(grouped_data[comp_name][region_name].keys(), key=str.lower)
            
            # 정렬을 위한 최대 길이 계산
            max_lb_name_len = 0
            max_ip_len = 0
            if sorted_lbs:
                max_lb_name_len = max(len(name) for name in sorted_lbs)
                max_ip_len = max(len(grouped_data[comp_name][region_name][name]['details']['ip_addrs']) for name in sorted_lbs)

            for lb_name in sorted_lbs:
                lb_data = grouped_data[comp_name][region_name][lb_name]
                details = lb_data['details']
                
                lb_state_map = {"ACTIVE": "green", "PROVISIONING": "cyan", "FAILED": "red", "UPDATING": "yellow", "TERMINATED": "red"}
                state_color = lb_state_map.get(details['lb_state'], 'white')
                
                # 패딩 추가
                padded_lb_name = lb_name.ljust(max_lb_name_len)
                padded_ip = details['ip_addrs'].ljust(max_ip_len)

                lb_text = (f"[bold white]{padded_lb_name}[/bold white] "
                           f"[{state_color}]({details['lb_state']:<12})[/] "
                           f"[yellow]{padded_ip}[/yellow] "
                           f"([dim]{details['shape']}, {details['lb_type']}, {details['min_bw']}-{details['max_bw']}Mbps[/dim])")
                lb_branch = region_branch.add(lb_text)

                backend_sets = lb_data['backend_sets']
                if not backend_sets:
                    lb_branch.add("[dim](No Backend Sets)[/dim]")
                else:
                    health_color_map = {"OK": "green", "WARNING": "yellow", "CRITICAL": "red", "UNKNOWN": "dim"}
                    sorted_bsets = sorted(backend_sets.keys(), key=str.lower)
                    for bset_name in sorted_bsets:
                        bset_branch = lb_branch.add(f"Backend Set: [bold]{bset_name}[/bold]")
                        targets = backend_sets[bset_name]
                        if not targets:
                            bset_branch.add("[dim](No Backends)[/dim]")
                        else:
                            for target in sorted(targets, key=lambda x: (x.get('vm_name', '-').lower(), x['name'])):
                                health_status = target['health']
                                health_color = health_color_map.get(health_status, 'white')
                                health_display = f" [{health_color}]({health_status})[/]" if health_status and health_status != '-' else ""
                                vm_name = target.get('vm_name', '-')
                                vm_display = f" [dim]({vm_name})[/dim]" if vm_name and vm_name != '-' else ""
                                bset_branch.add(f"└─ [green]{target['name']}[/green]{vm_display}{health_display}")

    console.print(tree)


def print_lb_table(console, lb_rows):
    if not lb_rows:
        console.print("(No LBs)")
        return

    lb_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["region"].lower(), x["lb_name"].lower(), x["backend_set"].lower(), x.get("vm_display_name", "-").lower(), x["backend_target"].lower()))
    console.print("\n[bold underline]LoadBalancer Info[/bold underline]")
    table = Table(show_lines=False, box=box.HORIZONTALS)
    headers = ["Compartment", "Region", "LB Name", "LB State", "IP Addresses", "Type", "Min", "Max", "Backend Set", "Backend Target", "Target VM Name", "Health"]
    for h in headers:
        style_opts = {}
        if h == "Compartment": style_opts['style'] = "bold magenta"
        if h == "Region": style_opts['style'] = "bold cyan"
        if h == "LB State" or h == "Backend Health": style_opts['justify'] = "center"
        if "Mbps" in h: style_opts['justify'] = "right"
        table.add_column(h, **style_opts)

    lb_state_map = {"ACTIVE": "green", "PROVISIONING": "cyan", "FAILED": "red", "UPDATING": "yellow", "TERMINATED": "red"}
    health_color_map = {"OK": "green", "WARNING": "yellow", "CRITICAL": "red", "UNKNOWN": "dim"}
    
    last_comp = None
    last_region = None
    last_lb = None
    last_bset = None
    
    for row in lb_rows:
        comp_display = row['compartment_name'] if row['compartment_name'] != last_comp else ""
        if comp_display:
            if last_comp is not None:
                table.add_row(*[Rule(style="dim") for _ in headers])
            last_comp = row['compartment_name']
            last_region, last_lb, last_bset = None, None, None

        region_display = row['region'] if row['region'] != last_region else ""
        if region_display:
            if last_region is not None:
                table.add_row("", *[Rule(style="dim") for _ in range(len(headers) - 1)])
            last_region = row['region']
            last_lb, last_bset = None, None

        lb_display = row['lb_name'] if row['lb_name'] != last_lb else ""
        if lb_display:
            if last_lb is not None:
                table.add_row(*["" for _ in range(2)], *[Rule(style="dim") for _ in range(len(headers) - 2)])
            last_lb = row['lb_name']
            last_bset = None

        bset_display = row['backend_set'] if row['backend_set'] != last_bset else ""
        if bset_display:
            if last_bset is not None:
                table.add_row(*["" for _ in range(9)], *[Rule(style="dim") for _ in range(len(headers) - 9)])
            last_bset = row['backend_set']

        st_col = f"[{lb_state_map.get(row['lb_state'], 'white')}]{row['lb_state']}[/]"
        health_status = row['backend_health']
        health_display = f"[{health_color_map.get(health_status, 'white')}]{health_status}[/]" if health_status and health_status != '-' else "-"
        
        # 중복 값들은 빈 문자열로 표시, lb 이름이 바뀔 때만 상세정보 표시
        ip_addrs_display = row["ip_addrs"] if lb_display else ""
        # shape_display = row["shape"] if lb_display else ""
        type_display = row["lb_type"] if lb_display else ""
        min_bw_display = row["min_bw"] if lb_display else ""
        max_bw_display = row["max_bw"] if lb_display else ""
        state_display = st_col if lb_display else ""

        table.add_row(
            comp_display, region_display, lb_display, state_display, ip_addrs_display,
            type_display, min_bw_display, max_bw_display, bset_display, row["backend_target"],
            row.get("vm_display_name", "-"),
            health_display
        )
    console.print(table)

###############################################################################
# main
###############################################################################
@progress_bar("OCI Load Balancer Information Collection")
def main(args):
    console = Console()
    try:
        config = oci.config.from_file("~/.oci/config", "DEFAULT")
        identity_client = oci.identity.IdentityClient(config)
    except Exception as e:
        console.print(f"[red]OCI 설정 파일 로드 실패: {e}[/red]")
        sys.exit(1)

    if args.regions:
        subscribed = get_all_subscribed_regions(identity_client, config["tenancy"])
        region_list = [r.strip() for r in args.regions.split(',') if r.strip() and r in subscribed]
        if not region_list:
            console.print("[red]유효한 리전이 없어 종료합니다[/red]"); sys.exit(0)
    else:
        region_list = get_all_subscribed_regions(identity_client, config["tenancy"])

    compartments = get_compartments(identity_client, config["tenancy"], args.compartment.lower() if args.compartment else None, console)
    lb_rows = collect_lb_parallel_fast(config, compartments, region_list, args.name.lower() if args.name else None, console)
    
    if args.output == 'tree':
        print_lb_tree(console, lb_rows)
    else:
        print_lb_table(console, lb_rows) 