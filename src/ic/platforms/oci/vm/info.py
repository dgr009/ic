#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import datetime
import concurrent.futures
import time

import oci
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule
from common.log import log_info_non_console
from common.progress_decorator import progress_bar, ManualProgress
from src.ic.platforms.oci.common.utils import get_all_subscribed_regions, get_compartments

# ###############################################################################
# # CLI 인자 정의
# ###############################################################################
def add_arguments(parser):
    """VM Info 에 필요한 인자만 추가"""
    parser.add_argument("-v", "--verbose", action="store_true", help="인스턴스 상세 출력 (전체 컬럼 표시)")
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")
    parser.add_argument("--regions","-r", default=None, help="조회할 리전(,) 예: ap-seoul-1,us-ashburn-1")


###############################################################################
# 인스턴스 정보 수집
###############################################################################
@progress_bar("Collecting instances from compartment")
def fetch_instances_one_comp(config, region, comp, name_filter):
    console = Console()
    results = []
    state_color_map = {
        "RUNNING": "green",
        "STOPPED": "yellow",
        "STOPPING": "yellow",
        "STARTING": "cyan",
        "PROVISIONING": "cyan",
        "TERMINATED": "red",
        "AVAILABLE": "green"
    }

    try:
        # Initial client setup to list instances
        compute_client = oci.core.ComputeClient(config)
        compute_client.base_client.set_region(region)
        insts = compute_client.list_instances(compartment_id=comp.id).data
    except Exception as e:
        console.print(f"[red][ERROR] 인스턴스 목록 조회 실패:[/red] region={region}, comp={comp.name}: {e}")
        return results

    valid_insts = [i for i in insts if i.lifecycle_state != "TERMINATED" and (not name_filter or name_filter in i.display_name.lower())]

    if not valid_insts:
        return results

    def process_instance(inst):
        start_ts = time.time()
        log_info_non_console(f"inst data collection : {comp.name} - {region} : {inst.display_name}")
        
        try:
            # Thread-safe clients
            cmp_cli = oci.core.ComputeClient(config)
            cmp_cli.base_client.set_region(region)
            vnet_cli = oci.core.VirtualNetworkClient(config)
            vnet_cli.base_client.set_region(region)
            blk_cli = oci.core.BlockstorageClient(config)
            blk_cli.base_client.set_region(region)

            # Shape, vCPU, Memory
            vcpus, memory_gbs, ad_val, fault_domain = "-", "-", inst.availability_domain or "-", "-"
            try:
                details = cmp_cli.get_instance(inst.id).data
                sc = details.shape_config
                if sc and sc.ocpus is not None:
                    vcpus = str(int(sc.ocpus * 2))
                    memory_gbs = str(int(sc.memory_in_gbs))
                fault_domain = details.fault_domain or "-"
            except Exception: pass

            # VNIC, IP, Subnet, NSG
            private_ip, public_ip, subnet_str, nsg_str = "-", "-", "-", "-"
            try:
                va = cmp_cli.list_vnic_attachments(compartment_id=comp.id, instance_id=inst.id).data
                if va:
                    vnic = vnet_cli.get_vnic(va[0].vnic_id).data
                    private_ip, public_ip = vnic.private_ip or "-", vnic.public_ip or "-"
                    try:
                        subnet_str = vnet_cli.get_subnet(vnic.subnet_id).data.display_name
                    except Exception: pass
                    if vnic.nsg_ids:
                        nsg_names = [vnet_cli.get_network_security_group(nsg_id).data.display_name for nsg_id in vnic.nsg_ids]
                        nsg_str = ",".join(nsg_names)
            except Exception: pass

            # Boot Volume
            boot_gb = "-"
            try:
                bvas = cmp_cli.list_boot_volume_attachments(availability_domain=inst.availability_domain, compartment_id=comp.id, instance_id=inst.id).data
                if bvas:
                    bv = blk_cli.get_boot_volume(bvas[0].boot_volume_id).data
                    boot_gb = str(bv.size_in_gbs)
            except Exception: pass

            # Block Volumes
            block_gb = "-"
            try:
                vol_atts = cmp_cli.list_volume_attachments(availability_domain=inst.availability_domain, compartment_id=comp.id, instance_id=inst.id).data
                block_list = [blk_cli.get_volume(va2.volume_id).data.size_in_gbs for va2 in vol_atts if not isinstance(va2, oci.core.models.BootVolumeAttachment)]
                if block_list:
                    block_gb = str(sum(block_list))
            except Exception: pass

            state_colored = f"[{state_color_map.get(inst.lifecycle_state, 'white')}]{inst.lifecycle_state}[/{state_color_map.get(inst.lifecycle_state, 'white')}]"
            
            # CreatedBy Tag
            created_by = inst.freeform_tags.get('CreatedBy', '-')
            if created_by == '-':
                created_by = inst.defined_tags.get('Oracle-Tags', {}).get('CreatedBy', '-')

            row_data = {
                "compartment_name": comp.name, "region": region, "ad": ad_val, "fault_domain": fault_domain,
                "instance_name": inst.display_name, "state_colored": state_colored, "subnet": subnet_str, "nsg": nsg_str,
                "private_ip": private_ip, "public_ip": public_ip, "shape": inst.shape, "vcpus": vcpus,
                "memory": memory_gbs, "boot": boot_gb, "block": block_gb, "created_by": created_by
            }
            elapsed = time.time() - start_ts
            log_info_non_console(f"inst data collection complete : {inst.display_name} ({elapsed:.2f}s)")
            return row_data
        except Exception as e:
            console.print(f"[red]Instance processing failed[/red]: {inst.display_name} : {e}")
            return None

    # Use manual progress for detailed instance processing tracking
    with ManualProgress(f"Processing {len(valid_insts)} instances in {comp.name} ({region})", total=len(valid_insts)) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as inst_executor:
            futs = [inst_executor.submit(process_instance, inst) for inst in valid_insts]
            completed = 0
            for fut in concurrent.futures.as_completed(futs):
                if data := fut.result():
                    results.append(data)
                completed += 1
                progress.update(f"Processed {completed}/{len(valid_insts)} instances", advance=1)
    
    return results

@progress_bar("Collecting instances across compartments and regions")
def collect_instances_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=20):
    start_ts = time.time()
    log_info_non_console("collect_instances_parallel_fast start")
    all_rows = []
    jobs = [(reg, comp) for reg in region_list for comp in compartments]
    
    if not jobs:
        return all_rows

    # Use manual progress for detailed compartment/region traversal tracking
    with ManualProgress(f"Processing {len(jobs)} compartment-region combinations", total=len(jobs)) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {executor.submit(fetch_instances_one_comp, config, r, c, name_filter): (r, c) for r, c in jobs}
            completed = 0
            
            for fut in concurrent.futures.as_completed(fut_map):
                region, comp = fut_map[fut]
                try:
                    result = fut.result()
                    all_rows.extend(result)
                    completed += 1
                    progress.update(f"Completed {comp.name} in {region} - Found {len(result)} instances", advance=1)
                except Exception as e:
                    completed += 1
                    progress.update(f"Failed {comp.name} in {region} - {str(e)}", advance=1)
                    console.print(f"[red]Job failed[/red] {comp.name} in {region}: {e}")
    
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_instances_parallel_fast complete ({elapsed:.2f}s)")
    return all_rows

###############################################################################
# 테이블 출력
###############################################################################
def print_instance_table(console, inst_rows, verbose):
    if not inst_rows:
        console.print("(No Instances)")
        return
        
    inst_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["region"].lower(), x["instance_name"].lower()))
    console.print("[bold underline]Instance Info[/bold underline]")
    t = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, header_style="bold", expand=False)
    t.show_edge = False
  
    if verbose:
        headers = ["Compartment", "Region", "AD", "Fault Domain", "Instance Name", "State", "Subnet", "NSG", "Private IP", "Public IP", "Shape", "vCPU", "Mem", "Boot", "Block", "CreatedBy"]
        keys = ["compartment_name", "region", "ad", "fault_domain", "instance_name", "state_colored", "subnet", "nsg", "private_ip", "public_ip", "shape", "vcpus", "memory", "boot", "block", "created_by"]
    else:
        headers = ["Comp", "Region", "Name", "State", "PrivateIP", "PublicIP", "Shape", "CPU", "Mem", "Boot", "Block"]
        keys = ["compartment_name", "region", "instance_name", "state_colored", "private_ip", "public_ip", "shape", "vcpus", "memory", "boot", "block"]

    for h in headers:
        style_opts = {}
        if h in ["Compartment", "Comp"]: style_opts = {"style": "bold magenta"}
        if h in ["Region", "AD", "Fault Domain"]: style_opts = {"style": "bold cyan"}
        if h == "State": style_opts = {"justify": "center"}
        if h in ["vCPU", "Mem", "CPU", "Boot", "Block"]: style_opts = {"justify": "right"}
        if h in ["Instance Name", "Name"]: style_opts = {"overflow": "fold"}
        t.add_column(h, **style_opts)

    last_comp = None
    last_region = None
    for i, row in enumerate(inst_rows):
        comp_changed = row["compartment_name"] != last_comp
        region_changed = row["region"] != last_region

        if i > 0:
            if comp_changed:
                t.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                t.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif not comp_changed and not region_changed:
                t.add_row("", "", *[Rule(style="dim") for _ in range(len(headers) - 2)])
        
        display_values = []
        display_values.append(row["compartment_name"] if comp_changed else "")
        display_values.append(row["region"] if comp_changed or region_changed else "")

        for k in keys[2:]:
            display_values.append(str(row.get(k, "-")))
        
        t.add_row(*display_values)

        last_comp = row["compartment_name"]
        last_region = row["region"]
    
    console.print(t)

###############################################################################
# main
###############################################################################
@progress_bar("OCI VM Information Collection")
def main(args):
    console = Console()
    name_filter = args.name.lower() if args.name else None
    compartment_filter = args.compartment.lower() if args.compartment else None

    # Use manual progress for initialization and setup
    with ManualProgress("Initializing OCI configuration and discovering resources", total=4) as progress:
        try:
            progress.update("Loading OCI configuration", advance=1)
            config = oci.config.from_file("~/.oci/config", "DEFAULT")
            identity_client = oci.identity.IdentityClient(config)
        except Exception as e:
            console.print(f"[red]OCI 설정 파일 로드 실패: {e}[/red]")
            sys.exit(1)

        progress.update("Discovering available regions", advance=1)
        if args.regions:
            subscribed = get_all_subscribed_regions(identity_client, config["tenancy"])
            region_list = [r.strip() for r in args.regions.split(',') if r.strip() and r in subscribed]
            if not region_list:
                console.print("[red]유효한 리전이 없어 종료합니다[/red]")
                sys.exit(0)
        else:
            region_list = get_all_subscribed_regions(identity_client, config["tenancy"])

        progress.update("Discovering compartments", advance=1)
        compartments = get_compartments(identity_client, config["tenancy"], compartment_filter, console)
        
        progress.update(f"Found {len(compartments)} compartments and {len(region_list)} regions", advance=1)

    # Collect instance information with progress tracking
    inst_rows = collect_instances_parallel_fast(config, compartments, region_list, name_filter, console)
    
    # Display results
    console.print(f"\n[bold green]Collection complete![/bold green] Found {len(inst_rows)} instances.")
    print_instance_table(console, inst_rows, args.verbose)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="OCI Instance Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
