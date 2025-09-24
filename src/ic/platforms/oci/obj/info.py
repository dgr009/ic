#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import oci
import concurrent.futures
import time
from rich.console import Console
from rich.table import Table
from rich import box
from common.log import log_info_non_console
from common.progress_decorator import progress_bar, ManualProgress
from src.ic.platforms.oci.common.utils import get_compartments, get_all_subscribed_regions

def add_arguments(parser):
    parser.add_argument("--name", "-n", default=None, help="Bucket 이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")
    parser.add_argument("--regions","-r", default=None, help="조회할 리전(,) 예: ap-seoul-1,us-ashburn-1")

###############################################################################
# Buckets (region×comp) 병렬 (oci_info.py 에서 복원)
###############################################################################
def fetch_bucket_one_comp(config, region, comp, name_filter):
    console  = Console()
    results  = []
    obj      = oci.object_storage.ObjectStorageClient(config)

    try:
        obj.base_client.set_region(region)
    except Exception:
        pass

    try:
        namespace = obj.get_namespace().data
    except Exception:
        return results

    try:
        buckets = obj.list_buckets(namespace, comp.id).data
    except Exception as e:
        console.print(f"[red]Bucket 조회 실패[/red]: region={region}, comp={comp.name}: {e}")
        return results

    for b in buckets:
        if name_filter and name_filter not in b.name.lower():
            continue

        access_str      = "NoPublicAccess"
        tier_str        = "-"
        approx_size_str = "-"
        approx_cnt_str  = "-"

        try:
            bd = obj.get_bucket(
                namespace_name = namespace,
                bucket_name    = b.name
            ).data
            if bd.public_access_type:
                access_str = bd.public_access_type
            if bd.storage_tier:
                tier_str   = bd.storage_tier

            if bd.approximate_size is not None:
                approx_size_str = f"{bd.approximate_size / 1024**3:.1f}"
            if bd.approximate_count is not None:
                approx_cnt_str  = f"{bd.approximate_count:,}"
        except Exception as e:
            console.print(f"[yellow]get_bucket 실패[/yellow] ({b.name}): {e}")

        if approx_size_str == "-" or approx_cnt_str == "-":
            total_size, total_count, next_token = 0, 0, None
            try:
                while True:
                    resp = obj.list_objects(
                        namespace_name=namespace, bucket_name=b.name,
                        start=next_token, fields=["size"], limit=1000
                    ).data
                    for o in resp.objects:
                        total_size  += o.size
                        total_count += 1
                    if not resp.next_start_with:
                        break
                    next_token = resp.next_start_with
                if total_count:
                    approx_size_str = f"{total_size / 1024**3:.1f}"
                    approx_cnt_str  = f"{total_count:,}"
            except Exception as e:
                console.print(f"[yellow]list_objects 실패[/yellow] ({b.name}): {e}")

        access_color = "red" if access_str in ["ObjectRead", "ObjectReadWrite"] else "green"
        access_colored = f"[{access_color}]{access_str}[/{access_color}]"

        results.append({
            "region": region, "compartment_name": comp.name, "bucket_name": b.name,
            "access_colored": access_colored, "tier": tier_str,
            "approx_size": approx_size_str, "approx_count": approx_cnt_str
        })
    return results

def collect_buckets_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    all_rows = []
    jobs = [(reg, comp) for reg in region_list for comp in compartments]
    total_jobs = len(jobs)
    
    with ManualProgress(f"Collecting object storage buckets from {len(region_list)} regions and {len(compartments)} compartments", total=total_jobs) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {executor.submit(fetch_bucket_one_comp, config, r, c, name_filter): (r,c) for r,c in jobs}
            completed = 0
            
            for fut in concurrent.futures.as_completed(fut_map):
                try:
                    chunk = fut.result()
                    all_rows.extend(chunk)
                    completed += 1
                    region, comp = fut_map[fut]
                    progress.update(f"Processed {region}/{comp.name} - Found {len(chunk)} buckets", advance=1)
                except Exception as e:
                    completed += 1
                    region, comp = fut_map[fut]
                    console.print(f"[red]Bucket job failed[/red]: {region}/{comp.name}: {e}")
                    progress.advance(1)
    return all_rows

def print_object_table(console, buckets):
    if not buckets:
        console.print("(No Object Storage Buckets)")
        return

    buckets.sort(key=lambda x: (x["compartment_name"].lower(), x["region"].lower(), x["bucket_name"].lower()))
    
    console.print("\n[bold underline]Object Storage Buckets[/bold underline]")
    table = Table(show_lines=False, box=box.SIMPLE_HEAVY, expand=True)
    headers = ["Compartment", "Region", "Bucket Name", "Access", "Storage Tier", "Size(GB)", "Object Count"]
    
    for h in headers:
        opts = {}
        if h == "Compartment": opts['style'] = "bold magenta"
        elif h == "Region": opts['style'] = "bold cyan"
        elif h == "Bucket Name": opts['style'] = "bold white"
        elif h.endswith("(GB)") or h.endswith("Count"): opts['justify'] = "right"
        table.add_column(h, **opts)

    curr_key=None
    for row in buckets:
        key=(row["compartment_name"], row["region"])
        if key!=curr_key:
            if curr_key!=None:
                table.add_section()
            curr_key=key
        table.add_row(
            row["compartment_name"],
            row["region"],
            row["bucket_name"],
            row["access_colored"],
            row["tier"],
            row["approx_size"],
            row["approx_count"]
        )
    
    console.print(table)

@progress_bar("Initializing OCI object storage information collection")
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
    buckets = collect_buckets_parallel_fast(config, compartments, region_list, args.name.lower() if args.name else None, console)
    print_object_table(console, buckets) 