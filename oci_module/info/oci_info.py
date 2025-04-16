#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import datetime
import concurrent.futures

import oci
import oci.usage_api
from rich.console import Console
from rich.table import Table
from rich import box

###############################################################################
# CLI 인자 정의
###############################################################################
def add_arguments(parser):
    parser.add_argument("--instance", "-i", action="store_true", help="인스턴스 정보만 표시")
    parser.add_argument("--lb", "-l", action="store_true", help="로드 밸런서 정보만 표시")
    parser.add_argument("--nsg", "-s", action="store_true", help="NSG 인바운드 룰만 표시")
    parser.add_argument("--volume", "-v", action="store_true", help="볼륨 정보만 표시 (부팅/블록)")
    parser.add_argument("--object", "-o", action="store_true", help="오브젝트 스토리지(버킷) 정보만 표시")

    # 비용 조회
    parser.add_argument("--cost", action="store_true", help="비용 정보 표시 (Usage API)")
    parser.add_argument("--cost-start", default=None, help="비용 조회 시작 (YYYY-MM-DD)")
    parser.add_argument("--cost-end", default=None, help="비용 조회 종료 (YYYY-MM-DD)")

    # 크레딧 조회
    parser.add_argument("--credit", action="store_true", help="크레딧 사용 내역 표시")
    parser.add_argument("--credit-year", type=int, default=None, help="크레딧 연도 (예: 2025)")
    parser.add_argument("--credit-initial", type=float, default=0.0, help="처음 받은 크레딧 금액")

    # 필터
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")

    # 리전
    parser.add_argument("--regions", default=None,
                        help="조회할 리전(,) 예: ap-seoul-1,us-ashburn-1")


###############################################################################
# 리전 구독 / 컴파트먼트 목록
###############################################################################
def get_all_subscribed_regions(identity_client, tenancy_ocid):
    resp = identity_client.list_region_subscriptions(tenancy_ocid)
    return [r.region_name for r in resp.data]

def get_compartments(identity_client, tenancy_ocid, compartment_filter=None, console=None):
    try:
        comps = []
        resp = identity_client.list_compartments(
            tenancy_ocid,
            compartment_id_in_subtree=True,
            lifecycle_state="ACTIVE"
        )
        comps.extend(resp.data)
        root_comp = identity_client.get_compartment(tenancy_ocid).data
        comps.append(root_comp)
    except Exception as e:
        if console:
            console.print(f"[red]컴파트먼트 조회 실패: {e}[/red]")
        else:
            print(f"[ERROR] 컴파트먼트 조회 실패: {e}")
        sys.exit(1)

    if compartment_filter:
        comps = [c for c in comps if compartment_filter in c.name.lower()]
    return comps


###############################################################################
# 인스턴스 (region×comp) 병렬
###############################################################################
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
        compute_client = oci.core.ComputeClient(config)
        compute_client.base_client.set_region(region)
        vnet_client = oci.core.VirtualNetworkClient(config)
        vnet_client.base_client.set_region(region)
        blk_client = oci.core.BlockstorageClient(config)
        blk_client.base_client.set_region(region)

        insts = compute_client.list_instances(compartment_id=comp.id).data
    except Exception as e:
        console.print(f"[red][ERROR] 인스턴스 조회 실패:[/red] region={region}, comp={comp.name}: {e}")
        return results

    for inst in insts:
        if inst.lifecycle_state == "TERMINATED":
            continue
        if name_filter and (name_filter not in inst.display_name.lower()):
            continue

        # shape
        vcpus = "-"
        memory_gbs = "-"
        try:
            details = compute_client.get_instance(inst.id).data
            sc = details.shape_config
            if sc and sc.ocpus is not None:
                vcpus = str(int(sc.ocpus * 2))
                memory_gbs = str(sc.memory_in_gbs)
        except:
            pass

        # VNIC
        private_ip, public_ip, subnet_str, nsg_str = "-", "-", "-", "-"
        try:
            va = compute_client.list_vnic_attachments(
                compartment_id=comp.id,
                instance_id=inst.id
            ).data
            if va:
                vnic_id = va[0].vnic_id
                vnic = vnet_client.get_vnic(vnic_id).data
                private_ip = vnic.private_ip or "-"
                public_ip = vnic.public_ip or "-"
                try:
                    sb = vnet_client.get_subnet(vnic.subnet_id).data
                    subnet_str = sb.display_name
                except:
                    pass
                if vnic.nsg_ids:
                    nsg_names = []
                    for nsg_id in vnic.nsg_ids:
                        try:
                            nsg_obj = vnet_client.get_network_security_group(nsg_id).data
                            nsg_names.append(nsg_obj.display_name)
                        except:
                            nsg_names.append("Unknown-NSG")
                    nsg_str = ",".join(nsg_names)
        except:
            pass

        # Boot Volume
        boot_str = "-"
        try:
            bvas = compute_client.list_boot_volume_attachments(
                availability_domain=inst.availability_domain,
                compartment_id=comp.id,
                instance_id=inst.id
            ).data
            if bvas:
                bv_id = bvas[0].boot_volume_id
                bv = blk_client.get_boot_volume(bv_id).data
                boot_str = f"{bv.size_in_gbs}GB"
        except:
            pass

        # Block Volume
        block_str = "-"
        try:
            vol_atts = compute_client.list_volume_attachments(comp.id, inst.id).data
            block_list = []
            for va2 in vol_atts:
                if not isinstance(va2, oci.core.models.BootVolumeAttachment):
                    vol_id = va2.volume_id
                    vol_data = blk_client.get_volume(vol_id).data
                    block_list.append(f"{vol_data.size_in_gbs}GB")
            if block_list:
                block_str = ", ".join(block_list)
        except:
            pass

        color = state_color_map.get(inst.lifecycle_state, "white")
        state_colored = f"[{color}]{inst.lifecycle_state}[/{color}]"

        results.append({
            "compartment_name": comp.name,
            "region": region,
            "instance_name": inst.display_name,
            "state_colored": state_colored,
            "subnet": subnet_str,
            "nsg": nsg_str,
            "private_ip": private_ip,
            "public_ip": public_ip,
            "shape": inst.shape,
            "vcpus": vcpus,
            "memory": memory_gbs,
            "boot": boot_str,
            "block": block_str
        })
    return results

def collect_instances_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    """(region×comp) 병렬로 인스턴스 정보"""
    all_rows = []
    jobs = []
    for reg in region_list:
        for comp in compartments:
            jobs.append((reg, comp))

    def worker(reg, comp):
        return fetch_instances_one_comp(config, reg, comp, name_filter)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(worker, r, c): (r,c) for (r,c) in jobs}
        for fut in concurrent.futures.as_completed(fut_map):
            rcomp = fut_map[fut]
            try:
                chunk = fut.result()
                all_rows.extend(chunk)
            except Exception as e:
                console.print(f"[red]Job failed[/red] {rcomp} : {e}")

    return all_rows


###############################################################################
# LB (region×comp) 병렬
###############################################################################
def fetch_lb_one_comp(config, region, comp, name_filter):
    console = Console()
    results = []

    lb_client = oci.load_balancer.LoadBalancerClient(config)
    try:
        lb_client.base_client.set_region(region)
    except:
        pass

    try:
        lb_list = lb_client.list_load_balancers(compartment_id=comp.id).data
    except Exception as e:
        console.print(f"[red][ERROR] LB 조회 실패:[/red] region={region}, comp={comp.name}: {e}")
        return results

    for lb in lb_list:
        if name_filter and (name_filter not in lb.display_name.lower()):
            continue
        lb_state = lb.lifecycle_state
        shape_name = lb.shape_name or "-"
        ip_list = []
        if lb.ip_addresses:
            ip_list = [ip.ip_address or "-" for ip in lb.ip_addresses]
        ip_addr_str = ", ".join(ip_list) if ip_list else "-"
        lb_type = "PRIVATE" if (getattr(lb, 'is_private', False)) else "PUBLIC"

        # backend sets
        bsets = []
        try:
            bsets = lb_client.list_backend_sets(load_balancer_id=lb.id).data
        except:
            pass
        if not bsets:
            results.append({
                "region": region,
                "compartment_name": comp.name,
                "lb_name": lb.display_name,
                "lb_state": lb_state,
                "ip_addrs": ip_addr_str,
                "shape": shape_name,
                "lb_type": lb_type,
                "backend_set": "(No Backend Sets)",
                "backend_target": "-"
            })
        else:
            for bset in bsets:
                # list backends
                try:
                    backend_list = lb_client.list_backends(load_balancer_id=lb.id, backend_set_name=bset.name).data
                except:
                    backend_list = []

                if not backend_list:
                    results.append({
                        "region": region,
                        "compartment_name": comp.name,
                        "lb_name": lb.display_name,
                        "lb_state": lb_state,
                        "ip_addrs": ip_addr_str,
                        "shape": shape_name,
                        "lb_type": lb_type,
                        "backend_set": "(No Backends)",
                        "backend_target": "(No Backends)"
                    })
                else:
                    for backend in backend_list:
                        tgt = backend.name
                        results.append({
                            "region": region,
                            "compartment_name": comp.name,
                            "lb_name": lb.display_name,
                            "lb_state": lb_state,
                            "ip_addrs": ip_addr_str,
                            "shape": shape_name,
                            "lb_type": lb_type,
                            "backend_set": bset.name,
                            "backend_target": tgt
                        })

    return results

def collect_lb_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    all_rows = []
    jobs = []
    for reg in region_list:
        for comp in compartments:
            jobs.append((reg, comp))

    def worker(reg, comp):
        return fetch_lb_one_comp(config, reg, comp, name_filter)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(worker, r, c): (r,c) for (r,c) in jobs}
        for fut in concurrent.futures.as_completed(fut_map):
            try:
                chunk = fut.result()
                all_rows.extend(chunk)
            except Exception as e:
                console.print(f"[red]LB job failed[/red] : {e}")
    return all_rows


###############################################################################
# NSG (region×comp) 병렬
###############################################################################
def fetch_nsg_one_comp(config, region, comp, name_filter):
    console = Console()
    results = []
    vcn_client = oci.core.VirtualNetworkClient(config)
    try:
        vcn_client.base_client.set_region(region)
    except:
        pass

    try:
        nsg_list = vcn_client.list_network_security_groups(compartment_id=comp.id).data
    except Exception as e:
        console.print(f"[red][ERROR] NSG 조회 실패:[/red] region={region}, comp={comp.name}: {e}")
        return results

    for nsg in nsg_list:
        if name_filter and (name_filter not in nsg.display_name.lower()):
            continue
        try:
            rules = vcn_client.list_network_security_group_security_rules(nsg.id).data
            ing = [r for r in rules if r.direction=="INGRESS"]
        except:
            ing = []

        if not ing:
            results.append({
                "region": region,
                "compartment_name": comp.name,
                "nsg_name": nsg.display_name,
                "desc": "(No Ingress Rules)",
                "proto": "-",
                "port_range": "-",
                "source": "-"
            })
        else:
            for rule in ing:
                desc = rule.description or "-"
                proto_str = rule.protocol
                if proto_str=="6": proto_str="TCP"
                elif proto_str=="17": proto_str="UDP"
                elif proto_str=="1": proto_str="ICMP"
                port_range = "-"
                if rule.tcp_options and rule.tcp_options.destination_port_range:
                    rng = rule.tcp_options.destination_port_range
                    port_range=f"{rng.min}-{rng.max}"
                elif rule.udp_options and rule.udp_options.destination_port_range:
                    rng = rule.udp_options.destination_port_range
                    port_range=f"{rng.min}-{rng.max}"

                results.append({
                    "region": region,
                    "compartment_name": comp.name,
                    "nsg_name": nsg.display_name,
                    "desc": desc,
                    "proto": proto_str,
                    "port_range": port_range,
                    "source": rule.source or "-"
                })
    return results

def collect_nsg_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    all_rows = []
    jobs = []
    for reg in region_list:
        for comp in compartments:
            jobs.append((reg, comp))
    def worker(reg, comp):
        return fetch_nsg_one_comp(config, reg, comp, name_filter)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(worker, r, c): (r,c) for (r,c) in jobs}
        for fut in concurrent.futures.as_completed(fut_map):
            try:
                chunk = fut.result()
                all_rows.extend(chunk)
            except Exception as e:
                console.print(f"[red]NSG job failed[/red]: {e}")
    return all_rows


###############################################################################
# Volumes (region×comp) 병렬
###############################################################################
def fetch_volume_one_comp(config, region, comp, name_filter):
    console = Console()
    boot_rows = []
    block_rows = []
    blk_client = oci.core.BlockstorageClient(config)
    compute_client = oci.core.ComputeClient(config)

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
        blk_client.base_client.set_region(region)
        compute_client.base_client.set_region(region)
    except:
        pass

    # AD 목록
    try:
        idy_client = oci.identity.IdentityClient(config)
        ads = idy_client.list_availability_domains(config["tenancy"]).data
    except Exception as e:
        console.print(f"[red]AD 조회 실패[/red]: region={region}, comp={comp.name}: {e}")
        return boot_rows, block_rows

    # Boot volumes
    for ad in ads:
        try:
            bvs = blk_client.list_boot_volumes(ad.name, comp.id).data
        except:
            bvs = []
        for bv in bvs:
            if name_filter and (name_filter not in bv.display_name.lower()):
                continue
            color = state_color_map.get(bv.lifecycle_state, "white")
            st_colored = f"[{color}]{bv.lifecycle_state}[/{color}]"
            boot_rows.append({
                "region": region,
                "compartment_name": comp.name,
                "volume_name": bv.display_name,
                "state": st_colored,
                "size_gb": bv.size_in_gbs,
                "attached": "-"
            })

    # Block volumes
    try:
        vols = blk_client.list_volumes(compartment_id=comp.id).data
    except:
        vols = []

    for vol in vols:
        if name_filter and (name_filter not in vol.display_name.lower()):
            continue
        c = state_color_map.get(vol.lifecycle_state, "white")
        st_colored = f"[{c}]{vol.lifecycle_state}[/{c}]"
        block_rows.append({
            "region": region,
            "compartment_name": comp.name,
            "volume_name": vol.display_name,
            "state": st_colored,
            "size_gb": vol.size_in_gbs,
            "attached": "-"
        })

    return (boot_rows, block_rows)

def collect_volumes_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    all_boot = []
    all_block = []
    jobs = []
    for reg in region_list:
        for comp in compartments:
            jobs.append((reg, comp))

    def worker(reg, comp):
        return fetch_volume_one_comp(config, reg, comp, name_filter)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(worker, r, c): (r,c) for (r,c) in jobs}
        for fut in concurrent.futures.as_completed(fut_map):
            try:
                b_rows, blk_rows = fut.result()
                all_boot.extend(b_rows)
                all_block.extend(blk_rows)
            except Exception as e:
                console.print(f"[red]Volume job failed[/red]: {e}")
    return all_boot, all_block


###############################################################################
# Buckets (region×comp) 병렬
###############################################################################
def fetch_bucket_one_comp(config, region, comp, name_filter):
    console = Console()
    results = []
    obj_client = oci.object_storage.ObjectStorageClient(config)

    try:
        obj_client.base_client.set_region(region)
    except:
        pass

    # namespace
    namespace = None
    try:
        namespace = obj_client.get_namespace().data
    except:
        pass

    if not namespace:
        return results

    try:
        bks = obj_client.list_buckets(namespace, comp.id).data
    except Exception as e:
        console.print(f"[red]Bucket 조회 실패[/red]: region={region}, comp={comp.name}: {e}")
        return results

    for b in bks:
        if name_filter and (name_filter not in b.name.lower()):
            continue
        access_str = "NoPublicAccess"
        tier_str = "-"
        try:
            bd = obj_client.get_bucket(namespace, b.name).data
            if bd.public_access_type:
                access_str=bd.public_access_type
            if bd.storage_tier:
                tier_str=bd.storage_tier
        except:
            pass

        results.append({
            "region": region,
            "compartment_name": comp.name,
            "bucket_name": b.name,
            "access_colored": access_str,
            "tier": tier_str,
            "approx_size": "-",
            "approx_count": "-"
        })
    return results

def collect_buckets_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    all_rows = []
    jobs = []
    for reg in region_list:
        for comp in compartments:
            jobs.append((reg, comp))
    def worker(reg, comp):
        return fetch_bucket_one_comp(config, reg, comp, name_filter)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(worker, r,c): (r,c) for (r,c) in jobs}
        for fut in concurrent.futures.as_completed(fut_map):
            try:
                chunk = fut.result()
                all_rows.extend(chunk)
            except Exception as e:
                console.print(f"[red]Bucket job failed[/red]: {e}")
    return all_rows


###############################################################################
# 비용 / 크레딧
###############################################################################
def get_date_range(start_str, end_str):
    now = datetime.datetime.utcnow()
    try:
        if start_str:
            y,m,d = map(int, start_str.split('-'))
            start_date = datetime.datetime(y,m,d)
        else:
            start_date = datetime.datetime(now.year, now.month, 1)
        if end_str:
            y,m,d = map(int, end_str.split('-'))
            end_date = datetime.datetime(y,m,d) + datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(days=1)
    except:
        start_date = datetime.datetime(now.year, now.month, 1)
        end_date   = datetime.datetime(now.year, now.month, now.day)+datetime.timedelta(days=1)
    return start_date, end_date

def get_compartment_costs(usage_client, tenancy_ocid, start_time, end_time, console):
    from oci.usage_api.models import RequestSummarizedUsagesDetails
    details = RequestSummarizedUsagesDetails(
        tenant_id=tenancy_ocid,
        time_usage_started=start_time,
        time_usage_ended=end_time,
        granularity="DAILY",
        group_by=["compartmentName", "service"],
        query_type="COST",
        compartment_depth=6
    )
    cost_data={}
    try:
        resp = usage_client.request_summarized_usages(details)
        items = resp.data.items or []
        for it in items:
            cname= it.compartment_name or "(root)"
            sname= it.service or "(UnknownService)"
            cval = float(it.computed_amount or 0.0)
            cost_data.setdefault(cname, {})
            cost_data[cname].setdefault(sname, 0.0)
            cost_data[cname][sname]+= cval
    except Exception as e:
        console.print(f"[yellow][WARN][/yellow] Cost API 실패: {e}")
    return cost_data

def print_cost_table(cost_rows, console, start_time, end_time):
    end_time = end_time - datetime.timedelta(seconds=1)
    console.print(f"\n[bold underline]Cost Info ({start_time.strftime('%Y-%m-%d')}~{end_time.strftime('%Y-%m-%d')})[/bold underline]")
    if not cost_rows:
        console.print("(No Cost Data)")
        return

    tbl = Table(show_lines=False, box=box.HEAVY_EDGE)
    tbl.add_column("Compartment", style="bold magenta")
    tbl.add_column("Service", style="bold cyan")
    tbl.add_column("Cost($)", justify="right")
    tbl.add_column("Total($)", justify="right")
    account_total=0
    for ckey in sorted(cost_rows.keys(), key=lambda x:x.lower()):
        services = cost_rows[ckey]
        ctotal = sum(services.values())
        if ctotal==0:
            continue
        account_total+=ctotal
        first=True
        for svc, val in sorted(services.items(), key=lambda x:x[1], reverse=True):
            if first:
                tbl.add_row(
                    ckey,
                    svc,
                    f"{val:.2f}",
                    f"[yellow]{ctotal:.2f}[/yellow]"
                )
                first=False
            else:
                if val>0:
                    tbl.add_row("", svc, f"{val:.2f}")
        tbl.add_section()
    tbl.add_row("[green]총 합계[/green]","","",f"[green]{account_total:.2f}[/green]")
    tbl.add_section()
    console.print(tbl)

def get_credit_usage(usage_client, tenancy_ocid, year, month, initial_credit, console):
    from oci.usage_api.models import RequestSummarizedUsagesDetails
    start_time = datetime.datetime(year,1,1)
    if month:
        end_time = datetime.datetime(year, month,1)+datetime.timedelta(days=31)
    else:
        end_time = datetime.datetime(year+1,1,1)
        month=12
    details = RequestSummarizedUsagesDetails(
        tenant_id=tenancy_ocid,
        time_usage_started=start_time,
        time_usage_ended=end_time,
        granularity="MONTHLY",
        query_type="COST",
        group_by=[],
        compartment_depth=6
    )
    monthly_cost={}
    try:
        resp = usage_client.request_summarized_usages(details)
        for it in resp.data.items or []:
            cost_val= float(it.computed_amount or 0.0)
            st = it.time_usage_started
            mk= st.strftime("%Y-%m")
            monthly_cost.setdefault(mk,0.0)
            monthly_cost[mk]+=cost_val
    except Exception as e:
        console.print(f"[yellow][WARN][/yellow] 크레딧조회 실패: {e}")
        return {}

    credit_data={}
    remain = initial_credit
    for m in range(1, month+1):
        mk= f"{year}-{m:02d}"
        cst= monthly_cost.get(mk, 0.0)
        remain-= cst
        if remain<0: remain=0
        credit_data[mk]= (cst, remain)
    return credit_data

def print_credit_table(credit_data, console, year, initial_credit):
    console.print(f"[bold underline]\nCredit Usage for {year}[/bold underline]")
    if not credit_data:
        console.print("(No credit data)")
        return
    tbl= Table(show_lines=False, box=box.SIMPLE_HEAVY)
    tbl.add_column("Month", style="bold cyan")
    tbl.add_column("Monthly Cost($)", justify="right")
    tbl.add_column("Remaining($)", justify="right")
    tbl.add_section()
    tbl.add_row("[magenta bold]Initial[/magenta bold]", "-", f"{initial_credit:.2f}")
    tbl.add_section()

    final_use=0.0
    for mk in sorted(credit_data.keys()):
        costv, rm= credit_data[mk]
        final_use+= costv
        tbl.add_row(mk, f"{costv:.2f}", f"{rm:.2f}")
    final_remain = list(credit_data.values())[-1][1]
    tbl.add_section()
    tbl.add_row("[bold]Summary[/bold]", f"[blue bold]{final_use:.2f}[/blue bold]", f"[green bold]{final_remain:.2f}[/green bold]")
    console.print(tbl)


###############################################################################
# main(args)
###############################################################################
def main(args):
    console = Console()

    # 리소스 표시 여부 결정
    # 아무것도 안주면 인스턴스/LB/NSG/Volume/Object 다 표시
    if not (args.instance or args.lb or args.nsg or args.volume or args.object or args.cost or args.credit):
        show_instance=True
        show_lb=True
        show_nsg=True
        show_volume=True
        show_object=True
        show_cost=False
        show_credit=False
    else:
        show_instance = args.instance
        show_lb       = args.lb
        show_nsg      = args.nsg
        show_volume   = args.volume
        show_object   = args.object
        show_cost     = args.cost
        show_credit   = args.credit

    name_filter = args.name.lower() if args.name else None
    compartment_filter = args.compartment.lower() if args.compartment else None

    # OCI 설정
    config = oci.config.from_file("~/.oci/config", "DEFAULT")
    identity_client = oci.identity.IdentityClient(config)
    usage_client = oci.usage_api.UsageapiClient(config)

    # 리전 목록
    if args.regions:
        input_regs= [r.strip() for r in args.regions.split(',') if r.strip()]
        subscribed= get_all_subscribed_regions(identity_client, config["tenancy"])
        region_list=[]
        for rr in input_regs:
            if rr in subscribed:
                region_list.append(rr)
            else:
                console.print(f"[yellow]{rr}는 구독되지 않은 리전[/yellow]")
        if not region_list:
            console.print("[red]유효한 리전이 없어 종료합니다[/red]")
            sys.exit(0)
    else:
        region_list= get_all_subscribed_regions(identity_client, config["tenancy"])

    # compartment 목록
    compartments = get_compartments(identity_client, config["tenancy"], compartment_filter, console)

    # 병렬로 각 리소스 조회
    inst_rows=[]
    lb_rows=[]
    nsg_rows=[]
    boot_rows=[]
    block_rows=[]
    obj_rows=[]

    futures=[]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        if show_instance:
            fut_inst= executor.submit(collect_instances_parallel_fast, config, compartments, region_list, name_filter, console, 10)
            futures.append(("instance", fut_inst))

        if show_lb:
            fut_lb= executor.submit(collect_lb_parallel_fast, config, compartments, region_list, name_filter, console, 10)
            futures.append(("lb", fut_lb))

        if show_nsg:
            fut_nsg= executor.submit(collect_nsg_parallel_fast, config, compartments, region_list, name_filter, console, 10)
            futures.append(("nsg", fut_nsg))

        if show_volume:
            fut_vol= executor.submit(collect_volumes_parallel_fast, config, compartments, region_list, name_filter, console, 10)
            futures.append(("volume", fut_vol))

        if show_object:
            fut_obj= executor.submit(collect_buckets_parallel_fast, config, compartments, region_list, name_filter, console, 10)
            futures.append(("object", fut_obj))

        for label, fut in futures:
            try:
                data = fut.result()
                if label=="instance":
                    inst_rows=data
                elif label=="lb":
                    lb_rows=data
                elif label=="nsg":
                    nsg_rows=data
                elif label=="volume":
                    # data=(boot,block)
                    boot_rows, block_rows = data
                elif label=="object":
                    obj_rows=data
            except Exception as e:
                console.print(f"[red]{label} 병렬 작업 실패[/red]: {e}")


    # ---------------- 출력 -------------------
    # 1) 인스턴스
    if show_instance:
        if inst_rows:
            # 정렬
            inst_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["region"].lower(), x["instance_name"].lower()))
            if inst_rows:
                console.print("[bold underline]Instance Info[/bold underline]")
                t= Table(show_lines=False, box=box.SIMPLE_HEAVY)
                t.add_column("Compartment", style="bold magenta")
                t.add_column("Region", style="bold cyan")
                t.add_column("Instance Name")
                t.add_column("State", justify="center")
                t.add_column("Subnet")
                t.add_column("NSG")
                t.add_column("Private IP")
                t.add_column("Public IP")
                t.add_column("Shape")
                t.add_column("vCPUs", justify="right")
                t.add_column("Memory(GB)", justify="right")
                t.add_column("Boot Volume")
                t.add_column("Block Volumes")
                # group by region, comp?
                curr_key=None
                for row in inst_rows:
                    key=(row["region"], row["compartment_name"])
                    if key!=curr_key:
                        if curr_key!=None:
                            t.add_section()
                        curr_key=key
                    t.add_row(
                        row["compartment_name"],
                        row["region"],
                        row["instance_name"],
                        row["state_colored"],
                        row["subnet"],
                        row["nsg"],
                        row["private_ip"],
                        row["public_ip"],
                        row["shape"],
                        row["vcpus"],
                        row["memory"],
                        row["boot"],
                        row["block"]
                    )
                console.print(t)
        else:
            console.print("(No Instances)")

    # 2) LB
    if show_lb:
        if lb_rows:
            lb_rows.sort(key=lambda x: (x["compartment_name"].lower()))
            console.print("\n[bold underline]LoadBalancer Info[/bold underline]")
            table= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            table.add_column("Compartment", style="bold magenta")
            table.add_column("Region", style="bold cyan")
            table.add_column("LB Name")
            table.add_column("LB State", justify="center")
            table.add_column("IP Addresses")
            table.add_column("Shape")
            table.add_column("Type")
            table.add_column("Backend Set")
            table.add_column("Backend Target")

            curr_comp=None
            for row in lb_rows:
                if row["compartment_name"]!=curr_comp:
                    if curr_comp!=None:
                        table.add_section()
                    curr_comp= row["compartment_name"]
                # 색상 예시
                lb_state_map= {
                    "ACTIVE": "green",
                    "PROVISIONING": "cyan",
                    "FAILED": "red",
                    "UPDATING": "yellow",
                    "TERMINATED": "red"
                }
                c= lb_state_map.get(row["lb_state"],"white")
                st_col= f"[{c}]{row['lb_state']}[/{c}]"
                table.add_row(
                    row["compartment_name"],
                    row["region"],
                    row["lb_name"],
                    st_col,
                    row["ip_addrs"],
                    row["shape"],
                    row["lb_type"],
                    row["backend_set"],
                    row["backend_target"]
                )
            console.print(table)
        else:
            console.print("(No LBs)")

    # 3) NSG
    if show_nsg:
        if nsg_rows:
            console.print("\n[bold underline]NSG Inbound Rules[/bold underline]")
            t= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            t.add_column("Compartment", style="bold magenta")
            t.add_column("Region", style="bold cyan")
            t.add_column("NSG Name", style="bold cyan")
            t.add_column("Rule Desc")
            t.add_column("Protocol")
            t.add_column("Port Range")
            t.add_column("Source")
            curr_comp=None
            for row in nsg_rows:
                if row["compartment_name"]!=curr_comp:
                    if curr_comp!=None:
                        t.add_section()
                    curr_comp= row["compartment_name"]
                t.add_row(
                    row["compartment_name"],
                    row["region"],
                    row["nsg_name"],
                    row["desc"],
                    row["proto"],
                    row["port_range"],
                    row["source"]
                )
            console.print(t)
        else:
            console.print("(No NSG)")

    # 4) Volumes
    if show_volume:
        # boot
        if boot_rows:
            console.print("\n[bold underline]Boot Volumes[/bold underline]")
            bt= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            bt.add_column("Compartment", style="bold magenta")
            bt.add_column("Region", style="bold cyan")
            bt.add_column("Volume Name")
            bt.add_column("State", justify="center")
            bt.add_column("Size(GB)", justify="right")
            bt.add_column("Attached")
            curr=None
            for row in boot_rows:
                key=(row["compartment_name"], row["region"])
                if key!=curr:
                    if curr!=None:
                        bt.add_section()
                    curr=key
                bt.add_row(
                    row["compartment_name"],
                    row["region"],
                    row["volume_name"],
                    row["state"],
                    str(row["size_gb"]),
                    row["attached"]
                )
            console.print(bt)
        else:
            console.print("(No Boot Volumes)")

        # block
        if block_rows:
            console.print("\n[bold underline]Block Volumes[/bold underline]")
            bt2= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            bt2.add_column("Compartment", style="bold magenta")
            bt2.add_column("Region", style="bold cyan")
            bt2.add_column("Volume Name")
            bt2.add_column("State", justify="center")
            bt2.add_column("Size(GB)", justify="right")
            bt2.add_column("Attached")
            curr=None
            for row in block_rows:
                key=(row["compartment_name"], row["region"])
                if key!=curr:
                    if curr!=None:
                        bt2.add_section()
                    curr=key
                bt2.add_row(
                    row["compartment_name"],
                    row["region"],
                    row["volume_name"],
                    row["state"],
                    str(row["size_gb"]),
                    row["attached"]
                )
            console.print(bt2)
        else:
            console.print("(No Block Volumes)")

    # 5) object
    if show_object:
        if obj_rows:
            console.print("\n[bold underline]Object Storage Buckets[/bold underline]")
            ot= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            ot.add_column("Compartment", style="bold magenta")
            ot.add_column("Region", style="bold cyan")
            ot.add_column("Bucket Name", style="bold white")
            ot.add_column("Access")
            ot.add_column("Storage Tier")
            ot.add_column("Size(GB)", justify="right")
            ot.add_column("Object Count", justify="right")
            curr=None
            for row in obj_rows:
                key=(row["compartment_name"], row["region"])
                if key!=curr:
                    if curr!=None:
                        ot.add_section()
                    curr=key
                ot.add_row(
                    row["compartment_name"],
                    row["region"],
                    row["bucket_name"],
                    row["access_colored"],
                    row["tier"],
                    row["approx_size"],
                    row["approx_count"]
                )
            console.print(ot)
        else:
            console.print("(No Buckets)")

    # 비용
    if show_cost:
        start_date, end_date = get_date_range(args.cost_start, args.cost_end)
        cost_data= get_compartment_costs(usage_client, config["tenancy"], start_date, end_date, console)
        if cost_data:
            print_cost_table(cost_data, console, start_date, end_date)
        else:
            console.print("(No Cost Data)")

    # 크레딧
    if show_credit:
        start_date, end_date = get_date_range(args.cost_start, args.cost_end)
        if args.credit_year and args.credit_year != end_date.year:
            year = args.credit_year
            month=12
        else: 
            year = end_date.year
            month = end_date.month

        year= args.credit_year if args.credit_year else end_date.year
        cd= get_credit_usage(usage_client, config["tenancy"], year, month, args.credit_initial, console)
        if cd:
            print_credit_table(cd, console, year, args.credit_initial)
        else:
            console.print("(No Credit Data)")


if __name__=="__main__":
    import argparse
    parser= argparse.ArgumentParser(description="OCI Info (Highly Parallel)")
    add_arguments(parser)
    args= parser.parse_args()
    main(args)
