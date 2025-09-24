#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import concurrent.futures
import time

import oci
from rich.console import Console
from rich.table import Table
from rich import box
from common.log import log_info_non_console
from common.progress_decorator import progress_bar, ManualProgress
from src.ic.platforms.oci.common.utils import get_all_subscribed_regions, get_compartments

def add_arguments(parser):
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")
    parser.add_argument("--regions","-r", default=None, help="조회할 리전(,) 예: ap-seoul-1,us-ashburn-1")

def fetch_volume_one_comp(config, region, comp, name_filter):
    console = Console()
    boot_rows, block_rows = [], []
    state_color_map = {
        "RUNNING": "green", "STOPPED": "yellow", "STOPPING": "yellow", "STARTING": "cyan",
        "PROVISIONING": "cyan", "TERMINATED": "red", "AVAILABLE": "green"
    }
    
    try:
        blk_client = oci.core.BlockstorageClient(config)
        blk_client.base_client.set_region(region)
        compute_client = oci.core.ComputeClient(config)
        compute_client.base_client.set_region(region)
        idy_client = oci.identity.IdentityClient(config)
        idy_client.base_client.set_region(region)
        ads = idy_client.list_availability_domains(config["tenancy"]).data
    except Exception as e:
        console.print(f"[red]Client/AD 조회 실패[/red]: region={region}, comp={comp.name}: {e}")
        return boot_rows, block_rows

    # Boot volumes
    for ad in ads:
        try:
            bvas = blk_client.list_boot_volumes(availability_domain=ad.name, compartment_id=comp.id).data
            for bva in bvas:
                if name_filter and name_filter not in bva.display_name.lower():
                    continue
                inst_name = "-"
                try:
                    atts = compute_client.list_boot_volume_attachments(availability_domain=ad.name, compartment_id=comp.id, boot_volume_id=bva.id).data
                    if atts:
                        inst_name = compute_client.get_instance(atts[0].instance_id).data.display_name
                except Exception: pass
                
                vpu_str = str(vpu) if (vpu := getattr(bva, "vpus_per_gb", None)) is not None else "-"
                color = state_color_map.get(bva.lifecycle_state, "white")
                st_colored = f"[{color}]{bva.lifecycle_state}[/{color}]"
                boot_rows.append({"region": region, "compartment_name": comp.name, "volume_name": bva.display_name, "state": st_colored, "size_gb": bva.size_in_gbs, "vpu": vpu_str, "attached": inst_name})
        except Exception: pass

    # Block Volumes
    try:
        vols = blk_client.list_volumes(compartment_id=comp.id).data
        for vol in vols:
            if name_filter and name_filter not in vol.display_name.lower():
                continue
            inst_name = "-"
            try:
                vas = compute_client.list_volume_attachments(availability_domain=vol.availability_domain, compartment_id=comp.id, volume_id=vol.id).data
                if vas:
                    inst_name = compute_client.get_instance(vas[0].instance_id).data.display_name
            except Exception: pass

            vpu = str(v) if (v := getattr(vol, "vpus_per_gb", None)) is not None else "-"
            color = state_color_map.get(vol.lifecycle_state, "white")
            state_colored = f"[{color}]{vol.lifecycle_state}[/{color}]"
            block_rows.append({"region": region, "compartment_name": comp.name, "volume_name": vol.display_name, "state": state_colored, "size_gb": vol.size_in_gbs, "vpu": vpu, "attached": inst_name})
    except Exception: pass
    
    return boot_rows, block_rows

def collect_volumes_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=20):
    start_ts = time.time()
    log_info_non_console("collect_volumes_parallel_fast start")
    all_boot, all_block, jobs = [], [], [(reg, comp) for reg in region_list for comp in compartments]
    
    total_jobs = len(jobs)
    with ManualProgress(f"Collecting volumes from {len(region_list)} regions and {len(compartments)} compartments", total=total_jobs) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {executor.submit(fetch_volume_one_comp, config, r, c, name_filter): (r, c) for r, c in jobs}
            completed = 0
            
            for fut in concurrent.futures.as_completed(fut_map):
                try:
                    b_rows, blk_rows = fut.result()
                    all_boot.extend(b_rows)
                    all_block.extend(blk_rows)
                    completed += 1
                    region, comp = fut_map[fut]
                    progress.update(f"Processed {region}/{comp.name} - Found {len(b_rows)} boot + {len(blk_rows)} block volumes", advance=1)
                except Exception as e:
                    completed += 1
                    region, comp = fut_map[fut]
                    console.print(f"[red]Volume job failed[/red]: {region}/{comp.name}: {e}")
                    progress.advance(1)
                
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_volumes_parallel_fast complete ({elapsed:.2f}s)")
    return all_boot, all_block

def print_volume_table(console, rows, title):
    if not rows:
        console.print(f"(No {title})")
        return
    
    rows.sort(key=lambda x: (x["compartment_name"].lower(), x["region"].lower(), x["volume_name"].lower()))
    console.print(f"\n[bold underline]{title}[/bold underline]")
    table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
    headers = ["Compartment", "Region", "Volume Name", "State", "Size(GB)", "VPU", "Attached"]
    for h in headers:
        opts = {}
        if h == "Compartment": opts['style'] = "bold magenta"
        elif h == "Region": opts['style'] = "bold cyan"
        elif h == "State": opts['justify'] = "center"
        elif h in ["Size(GB)", "VPU"]: opts['justify'] = "right"
        table.add_column(h, **opts)

    curr_key = None
    for row in rows:
        key = (row["compartment_name"], row["region"])
        if key != curr_key:
            if curr_key is not None: table.add_section()
            curr_key = key
        table.add_row(row["compartment_name"], row["region"], row["volume_name"], row["state"], str(row["size_gb"]), row["vpu"], row["attached"])
    console.print(table)

@progress_bar("Initializing OCI volume information collection")
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
        if not region_list: console.print("[red]유효한 리전이 없어 종료합니다[/red]"); sys.exit(0)
    else:
        region_list = get_all_subscribed_regions(identity_client, config["tenancy"])
    
    compartments = get_compartments(identity_client, config["tenancy"], args.compartment.lower() if args.compartment else None, console)
    boot_rows, block_rows = collect_volumes_parallel_fast(config, compartments, region_list, args.name.lower() if args.name else None, console)
    print_volume_table(console, boot_rows, "Boot Volumes")
    print_volume_table(console, block_rows, "Block Volumes") 