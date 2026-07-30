#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import datetime
import concurrent.futures
import time

import re
import oci
from common.log import log_info_non_console
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
    parser.add_argument("--policy", "-p", action="store_true", help="IAM Policy 정보만 표시")

    # 비용 조회
    parser.add_argument("--cost", action="store_true", help="비용 정보 표시 (Usage API)")
    parser.add_argument("--cost-start", default=None, help="비용 조회 시작 (YYYY-MM-DD)")
    parser.add_argument("--cost-end", default=None, help="비용 조회 종료 (YYYY-MM-DD)")

    # 크레딧 조회
    parser.add_argument("--credit", action="store_true", help="크레딧 사용 내역 표시")
    parser.add_argument("--credit-year", type=int, default=None, help="크레딧 연도 (예: 2025)")
    parser.add_argument("--credit-date", type=int, default=None, help="크레딧 시작일자 (예: 2025-05-22)")
    parser.add_argument("--credit-initial", type=float, default=0.0, help="처음 받은 크레딧 금액")

    # 필터
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")

    # 리전
    parser.add_argument("--regions", "-r", default=None,
                        help="조회할 리전(,) 예: ap-seoul-1,us-ashburn-1")
    # 인스턴스 출력 상세 모드
    parser.add_argument("--verb", action="store_true", help="인스턴스 상세 출력 (전체 컬럼 표시)")


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

    # --------------- 인스턴스 단위 병렬 처리 ---------------
    valid_insts = [i for i in insts if i.lifecycle_state != "TERMINATED" and ((name_filter is None) or (name_filter in i.display_name.lower()))]

    def process_instance(inst):
        """단일 인스턴스 정보를 수집하여 dict 로 반환"""
        start_ts = time.time()
        log_info_non_console(f"inst data collection start : {comp.name} - {region} : {inst.display_name}")

        try:
            # 각 스레드마다 자체 클라이언트 사용 (스레드 세이프)
            cmp_cli = oci.core.ComputeClient(config)
            cmp_cli.base_client.set_region(region)
            vnet_cli = oci.core.VirtualNetworkClient(config)
            vnet_cli.base_client.set_region(region)
            blk_cli = oci.core.BlockstorageClient(config)
            blk_cli.base_client.set_region(region)

            # shape
            vcpus = "-"
            memory_gbs = "-"
            ad_val = inst.availability_domain or "-"
            fault_domain = "-"
            try:
                details = cmp_cli.get_instance(inst.id).data
                sc = details.shape_config
                if sc and sc.ocpus is not None:
                    vcpus = str(int(sc.ocpus * 2))
                    memory_gbs = str(sc.memory_in_gbs)
                fault_domain = details.fault_domain or "-"
            except Exception:
                pass

            # VNIC
            private_ip, public_ip, subnet_str, nsg_str = "-", "-", "-", "-"
            try:
                va = cmp_cli.list_vnic_attachments(
                    compartment_id=comp.id,
                    instance_id=inst.id
                ).data
                if va:
                    vnic_id = va[0].vnic_id
                    vnic = vnet_cli.get_vnic(vnic_id).data
                    private_ip = vnic.private_ip or "-"
                    public_ip = vnic.public_ip or "-"
                    try:
                        sb = vnet_cli.get_subnet(vnic.subnet_id).data
                        subnet_str = sb.display_name
                    except Exception:
                        pass
                    if vnic.nsg_ids:
                        nsg_names = []
                        for nsg_id in vnic.nsg_ids:
                            try:
                                nsg_obj = vnet_cli.get_network_security_group(nsg_id).data
                                nsg_names.append(nsg_obj.display_name)
                            except Exception:
                                nsg_names.append("Unknown-NSG")
                        nsg_str = ",".join(nsg_names)
            except Exception:
                pass

            # Boot Volume
            boot_str = "-"
            try:
                bvas = cmp_cli.list_boot_volume_attachments(
                    availability_domain=inst.availability_domain,
                    compartment_id=comp.id,
                    instance_id=inst.id
                ).data
                if bvas:
                    bv_id = bvas[0].boot_volume_id
                    bv = blk_cli.get_boot_volume(bv_id).data
                    boot_str = f"{bv.size_in_gbs}GB"
            except Exception:
                pass

            # Block Volumes
            block_str = "-"
            try:
                vol_atts = cmp_cli.list_volume_attachments(
                    availability_domain=inst.availability_domain,
                    compartment_id=comp.id,
                    instance_id=inst.id
                ).data
                block_list = []
                for va2 in vol_atts:
                    if not isinstance(va2, oci.core.models.BootVolumeAttachment):
                        vol_id = va2.volume_id
                        vol_data = blk_cli.get_volume(vol_id).data
                        block_list.append(f"{vol_data.size_in_gbs}GB")
                if block_list:
                    block_str = ", ".join(block_list)
            except Exception:
                pass

            color = state_color_map.get(inst.lifecycle_state, "white")
            state_colored = f"[{color}]{inst.lifecycle_state}[/{color}]"

            row_data = {
                "compartment_name": comp.name,
                "region": region,
                "ad": ad_val,
                "fault_domain": fault_domain,
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
            }
            elapsed = time.time() - start_ts
            log_info_non_console(f"inst data collection complete : {inst.display_name} ({elapsed:.2f}s)")
            return row_data
        except Exception as e:
            console.print(f"[red]Instance processing failed[/red]: {inst.display_name} : {e}")
            return None

    # ThreadPool for instances in same comp/region
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as inst_executor:
        futs = [inst_executor.submit(process_instance, inst) for inst in valid_insts]
        for fut in concurrent.futures.as_completed(futs):
            data = fut.result()
            if data:
                results.append(data)
    return results

def collect_instances_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    """(region×comp) 병렬로 인스턴스 정보"""
    start_ts = time.time()
    log_info_non_console("collect_instances_parallel_fast start")
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

    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_instances_parallel_fast complete ({elapsed:.2f}s)")
    return all_rows


###############################################################################
# LB (region×comp) 병렬
###############################################################################
def fetch_lb_one_comp(config, region, comp, name_filter):
    console = Console()
    results = []

    lb_client_main = oci.load_balancer.LoadBalancerClient(config)
    try:
        lb_client_main.base_client.set_region(region)
    except Exception:
        pass

    try:
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
        except Exception:
            pass

        lb_state = lb_obj.lifecycle_state
        shape_name = lb_obj.shape_name or "-"
        ip_addr_str = ", ".join([ip.ip_address or "-" for ip in lb_obj.ip_addresses]) if lb_obj.ip_addresses else "-"
        lb_type = "PRIVATE" if (getattr(lb_obj, 'is_private', False)) else "PUBLIC"

        min_bw = max_bw = "-"
        sd = getattr(lb_obj, "shape_details", None)
        if sd:
            mbw = getattr(sd, "minimum_bandwidth_in_mbps", None)
            xbw = getattr(sd, "maximum_bandwidth_in_mbps", None)
            if mbw is not None:
                min_bw = str(mbw)
            if xbw is not None:
                max_bw = str(xbw)

        rows = []
        try:
            bsets = lb_client.list_backend_sets(load_balancer_id=lb_obj.id).data
        except Exception:
            bsets = []

        if not bsets:
            rows.append({
                "region": region,
                "compartment_name": comp.name,
                "lb_name": lb_obj.display_name,
                "lb_state": lb_state,
                "ip_addrs": ip_addr_str,
                "shape": shape_name,
                "min_bw": min_bw,
                "max_bw": max_bw,
                "lb_type": lb_type,
                "backend_set": "(No Backend Sets)",
                "backend_target": "-"
            })
        else:
            for bset in bsets:
                try:
                    backend_list = lb_client.list_backends(load_balancer_id=lb_obj.id, backend_set_name=bset.name).data
                except Exception:
                    backend_list = []
                if not backend_list:
                    rows.append({
                        "region": region,
                        "compartment_name": comp.name,
                        "lb_name": lb_obj.display_name,
                        "lb_state": lb_state,
                        "ip_addrs": ip_addr_str,
                        "shape": shape_name,
                        "min_bw": min_bw,
                        "max_bw": max_bw,
                        "lb_type": lb_type,
                        "backend_set": "(No Backends)",
                        "backend_target": "(No Backends)"
                    })
                else:
                    for backend in backend_list:
                        rows.append({
                            "region": region,
                            "compartment_name": comp.name,
                            "lb_name": lb_obj.display_name,
                            "lb_state": lb_state,
                            "ip_addrs": ip_addr_str,
                            "shape": shape_name,
                            "min_bw": min_bw,
                            "max_bw": max_bw,
                            "lb_type": lb_type,
                            "backend_set": bset.name,
                            "backend_target": backend.name
                        })

        elapsed = time.time() - start_ts
        log_info_non_console(f"lb data collection complete : {lb_obj.display_name} ({elapsed:.2f}s)")
        return rows

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as lb_pool:
        all_futs = [lb_pool.submit(process_lb, lb) for lb in lb_list]
        for fut in concurrent.futures.as_completed(all_futs):
            try:
                rows_chunk = fut.result()
                results.extend(rows_chunk)
            except Exception as e:
                console.print(f"[red]LB processing failed[/red] : {e}")

    return results

def collect_lb_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    start_ts = time.time()
    log_info_non_console("collect_lb_parallel_fast start")
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
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_lb_parallel_fast complete ({elapsed:.2f}s)")
    return all_rows


###############################################################################
# NSG (region×comp) 병렬
###############################################################################
def fetch_nsg_one_comp(config, region, comp, name_filter):
    start_ts = time.time()
    log_info_non_console(f"nsg data collection start : {comp.name} - {region}")
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
                if rule.source_type == "NETWORK_SECURITY_GROUP" and rule.source:
                    try:
                        # rule.source : 대상 NSG 의 OCID
                        ref_nsg = vcn_client.get_network_security_group(rule.source).data
                        source_str = f"{ref_nsg.display_name}"          # → 이름으로 치환
                    except Exception:
                        source_str = rule.source      
                else:
                    source_str = rule.source or "-"                       # 실패 시 OCID 그대로

                results.append({
                    "region": region,
                    "compartment_name": comp.name,
                    "nsg_name": nsg.display_name,
                    "desc": desc,
                    "proto": proto_str,
                    "port_range": port_range,
                    "source": source_str
                })
    elapsed = time.time() - start_ts
    log_info_non_console(f"nsg data collection complete : {comp.name} - {region} ({elapsed:.2f}s)")
    return results

def collect_nsg_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    start_ts = time.time()
    log_info_non_console("collect_nsg_parallel_fast start")
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
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_nsg_parallel_fast complete ({elapsed:.2f}s)")
    return all_rows


###############################################################################
# Volumes (region×comp) 병렬
###############################################################################
def fetch_volume_one_comp(config, region, comp, name_filter):
    start_ts = time.time()
    log_info_non_console(f"volume data collection start : {comp.name} - {region}")
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

    # ───── Availability Domain 목록 (리전마다 다르게) ─────
    try:
        idy_client = oci.identity.IdentityClient(config)
        # IdentityClient 도 조회 대상 리전으로 변경하지 않으면 tenancy 기본 리전 AD 만 반환
        try:
            idy_client.base_client.set_region(region)
        except Exception:
            pass

        ads = idy_client.list_availability_domains(config["tenancy"]).data
    except Exception as e:
        console.print(f"[red]AD 조회 실패[/red]: region={region}, comp={comp.name}: {e}")
        return boot_rows, block_rows

    # Boot volumes
    for ad in ads:
        try:
            bvas = blk_client.list_boot_volumes(
                availability_domain = ad.name,
                compartment_id      = comp.id
            ).data
        except Exception:
            bvas = []

        for bva in bvas:
            if name_filter and name_filter not in bva.display_name.lower():
                continue

            inst_name = "-"
            try:
                atts = compute_client.list_boot_volume_attachments(
                    availability_domain = ad.name,
                    compartment_id      = comp.id,
                    boot_volume_id      = bva.id
                ).data
                if atts:
                    inst_id   = atts[0].instance_id
                    inst_name = compute_client.get_instance(inst_id).data.display_name
            except Exception:
                pass

            color = state_color_map.get(bva.lifecycle_state, "white")
            st_colored = f"[{color}]{bva.lifecycle_state}[/{color}]"

            vpu_val = getattr(bva, "vpus_per_gb", None)
            vpu_str = str(vpu_val) if vpu_val is not None else "-"

            boot_rows.append({
                "region": region,
                "compartment_name": comp.name,
                "volume_name": bva.display_name,
                "state": st_colored,
                "size_gb": bva.size_in_gbs,
                "vpu": vpu_str,
                "attached": inst_name
            })

    # ───────────────── Block Volumes ────────────────────────────
    try:
        vols = blk_client.list_volumes(compartment_id = comp.id).data
    except Exception:
        vols = []

    for vol in vols:
        if name_filter and name_filter not in vol.display_name.lower():
            continue

        # ── 인스턴스 이름 찾기 ────────────────────────────────
        inst_name = "-"
        try:
            vas = compute_client.list_volume_attachments(
                availability_domain = vol.availability_domain,
                compartment_id      = comp.id,
                volume_id           = vol.id
            ).data
            if vas:
                inst_id   = vas[0].instance_id
                inst_name = compute_client.get_instance(inst_id).data.display_name
        except Exception:
            pass

        # VPU (volume performance level)
        vpu = str(vol.vpus_per_gb) if getattr(vol, "vpus_per_gb", None) is not None else "-"

        color         = state_color_map.get(vol.lifecycle_state, "white")
        state_colored = f"[{color}]{vol.lifecycle_state}[/{color}]"

        block_rows.append({
            "region"          : region,
            "compartment_name": comp.name,
            "volume_name"     : vol.display_name,
            "state"           : state_colored,
            "size_gb"         : vol.size_in_gbs,
            "vpu"             : vpu,
            "attached"        : inst_name
        })

    elapsed = time.time() - start_ts
    log_info_non_console(f"volume data collection complete : {comp.name} - {region} ({elapsed:.2f}s)")
    return (boot_rows, block_rows)

def collect_volumes_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=10):
    start_ts = time.time()
    log_info_non_console("collect_volumes_parallel_fast start")
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
    elapsed = time.time() - start_ts
    log_info_non_console(f"collect_volumes_parallel_fast complete ({elapsed:.2f}s)")
    return all_boot, all_block


###############################################################################
# Buckets (region×comp) 병렬
###############################################################################
def fetch_bucket_one_comp(config, region, comp, name_filter):
    console  = Console()
    results  = []
    obj      = oci.object_storage.ObjectStorageClient(config)

    # ---------- 리전 설정 ----------
    try:
        obj.base_client.set_region(region)
    except Exception:
        pass

    # ---------- 네임스페이스 ----------
    try:
        namespace = obj.get_namespace().data
    except Exception:
        return results                      # namespace 조회 실패 시 즉시 종료

    # ---------- 버킷 목록 ----------
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

        # ---------- 1차 : get_bucket() ----------
        try:
            bd = obj.get_bucket(
                namespace_name = namespace,
                bucket_name    = b.name
            ).data

            # public / tier
            if bd.public_access_type:
                access_str = bd.public_access_type
            if bd.storage_tier:
                tier_str   = bd.storage_tier

            # 값이 있으면 바로 문자열 변환
            if bd.approximate_size is not None:
                approx_size_str = f"{bd.approximate_size / 1024**3:.1f}"
            if bd.approximate_count is not None:
                approx_cnt_str  = f"{bd.approximate_count:,}"

        except Exception as e:
            console.print(f"[yellow]get_bucket 실패[/yellow] ({b.name}): {e}")

        # ---------- 2차 : 값이 없으면 직접 합산 ----------
        if approx_size_str == "-" or approx_cnt_str == "-":
            total_size  = 0
            total_count = 0
            next_token  = None

            try:
                while True:
                    resp = obj.list_objects(
                        namespace_name = namespace,
                        bucket_name    = b.name,
                        start          = next_token,
                        fields         = ["size"],   # 객체 크기만 필요
                        limit          = 1000        # 페이지 크기
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

        # ---------- 결과 누적 ----------
        results.append({
            "region"          : region,
            "compartment_name": comp.name,
            "bucket_name"     : b.name,
            "access_colored"  : access_str,
            "tier"            : tier_str,
            "approx_size"     : approx_size_str,
            "approx_count"    : approx_cnt_str
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
    currency_cd = "USD"   
    try:
        resp = usage_client.request_summarized_usages(details)
        items = resp.data.items or []
        if items:
            currency_cd = items[0].currency or currency_cd
        for it in items:
            cname= it.compartment_name or "(root)"
            sname= it.service or "(UnknownService)"
            cval = float(it.computed_amount or 0.0)
            cost_data.setdefault(cname, {})
            cost_data[cname].setdefault(sname, 0.0)
            cost_data[cname][sname]+= cval
    except Exception as e:
        console.print(f"[yellow][WARN][/yellow] Cost API 실패: {e}")
    return cost_data, currency_cd

def print_cost_table(cost_rows, console, start_time, end_time, currency_cd):
    end_time = end_time - datetime.timedelta(seconds=1)
    console.print(f"\n[bold underline]Cost Info ({start_time.strftime('%Y-%m-%d')}~{end_time.strftime('%Y-%m-%d')})[/bold underline]")
    if not cost_rows:
        console.print("(No Cost Data)")
        return

    tbl = Table(show_lines=False, box=box.HEAVY_EDGE)
    tbl.add_column("Compartment", style="bold magenta")
    tbl.add_column("Service", style="bold cyan")
    tbl.add_column(f"Cost({currency_cd})", justify="right")
    tbl.add_column(f"Total({currency_cd})", justify="right")
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
                    f"{val:,.0f}",
                    f"[yellow]{ctotal:,.0f}[/yellow]"
                )
                first=False
            else:
                if val>0:
                    tbl.add_row("", svc, f"{val:,.0f}")
        tbl.add_section()
    tbl.add_row("[green]총 합계[/green]","","",f"[green]{account_total:,.0f}[/green]")
    tbl.add_section()
    console.print(tbl)

def get_credit_usage(usage_client, tenancy_ocid, start_date, end_date, initial_credit, console):
    from oci.usage_api.models import RequestSummarizedUsagesDetails
    # Usage API 의 종료 시각은 exclusive 이므로, 다음 날 00:00 으로 맞춰줌
    adj_end_time = end_date + datetime.timedelta(days=1)

    details = RequestSummarizedUsagesDetails(
        tenant_id=tenancy_ocid,
        time_usage_started=start_date,
        time_usage_ended=adj_end_time,
        granularity="MONTHLY",
        query_type="COST",
        group_by=[],
        compartment_depth=6,
    )

    monthly_cost: dict[str, float] = {}
    currency_cd = "KRW"

    try:
        resp = usage_client.request_summarized_usages(details)
        items = resp.data.items or []
        if items:
            currency_cd = items[0].currency if items[0].currency!=" " else items[1].currency
        for it in items:
            cost_val = float(it.computed_amount or 0.0)
            mk = it.time_usage_started.strftime("%Y-%m")
            monthly_cost.setdefault(mk, 0.0)
            monthly_cost[mk] += cost_val
    except Exception as e:
        console.print(f"[yellow][WARN][/yellow] 크레딧조회 실패: {e}")
        return {}, currency_cd

    # ----- 월별 잔액 계산 -----
    credit_data: dict[str, tuple[float, float]] = {}
    remain = initial_credit

    curr = datetime.datetime(start_date.year, start_date.month, 1)
    end_month = datetime.datetime(end_date.year, end_date.month, 1)
    while curr <= end_month:
        mk = curr.strftime("%Y-%m")
        used = monthly_cost.get(mk, 0.0)
        remain -= used
        if remain < 0:
            remain = 0
        credit_data[mk] = (used, remain)

        # 다음 달로 이동
        if curr.month == 12:
            curr = datetime.datetime(curr.year + 1, 1, 1)
        else:
            curr = datetime.datetime(curr.year, curr.month + 1, 1)

    return credit_data, currency_cd

def print_credit_table(credit_data, console, year, initial_credit, currency_cd):
    console.print(f"[bold underline]\nCredit Usage for {year}[/bold underline]")
    if not credit_data:
        console.print("(No credit data)")
        return
    tbl= Table(show_lines=False, box=box.SIMPLE_HEAVY)
    tbl.add_column("Month", style="bold cyan")
    tbl.add_column(f"Monthly Cost({currency_cd})", justify="right")
    tbl.add_column(f"Remaining({currency_cd})", justify="right")
    tbl.add_section()
    tbl.add_row("[magenta bold]Initial[/magenta bold]", "-", f"{initial_credit:,.0f}")
    tbl.add_section()

    final_use=0.0
    for mk in sorted(credit_data.keys()):
        costv, rm= credit_data[mk]
        final_use+= costv
        tbl.add_row(mk, f"{costv:,.0f}", f"{rm:,.0f}")
    final_remain = list(credit_data.values())[-1][1]
    tbl.add_section()
    tbl.add_row("[bold]Summary[/bold]", f"[blue bold]{final_use:,.0f}[/blue bold]", f"[green bold]{final_remain:,.0f}[/green bold]")
    console.print(tbl)


# ─────────────────────────────────────────────────────────────────────────────
# IAM Policy (compartment 단위, 병렬 가능하지만 API 부하 작아 단순 loop 사용)
# ─────────────────────────────────────────────────────────────────────────────
def collect_policies(identity_client, compartments, name_filter, console):
    """각 컴파트먼트의 정책 이름·구문(statement)을 수집"""
    rows = []
    for comp in compartments:
        try:
            policies = identity_client.list_policies(compartment_id=comp.id,
                                                     lifecycle_state="ACTIVE").data
        except Exception as e:
            console.print(f"[red]Policy 조회 실패:[/red] {comp.name}: {e}")
            continue

        for pol in policies:
            if name_filter and name_filter not in pol.name.lower():
                continue
            stmt_joined = "\n".join(pol.statements) if pol.statements else "-"
            rows.append({
                "compartment_name": comp.name,
                "policy_name": pol.name,
                "statements": stmt_joined
            })
    return rows
# ─────────────────────────────────────────────────────────────────────────────
# IAM Policy 구문 분석
# ─────────────────────────────────────────────────────────────────────────────
stmt_pat = re.compile(
    r"""^(allow|endorse)\s+      # Action (group 1)
        (.*?)\s+                  # Subject (group 2, non-greedy)
        to\s+
        ([^{\s]+|\{[^\}]+\})\s+   # Verb (group 3, simple like 'read' or complex like '{read, WRITE}' or '{WLP_BOM_READ}')
        # Resource Type is optional - if next word is 'in', then no resource type
        (?:(?!in\s)(\S+)\s+)?     # Resource Type (group 4, optional, negative lookahead for 'in ')
        # Optional Scope: 'in compartment <name/id>' or 'in tenancy'
        # Group 5 captures the content of the scope (e.g., "compartment <name>", "tenancy")
        (?:in\s+(.+?))?           # Scope content (group 5, optional, non-greedy)
        \s*                       # Allow spaces between scope and where, or scope and EOL
        # Optional Condition: 'where <conditions>'
        # Group 6 captures the conditions string
        (?:\s+where\s+(.*))?$    # Condition (group 6, optional, greedy)
    """,
    re.I | re.X,
)

def parse_stmt(stmt: str):
    """IAM Policy 구문을 파싱하여 각 구성 요소를 추출"""
    m = stmt_pat.match(stmt.strip())
    if not m:
        # 정규식 매칭 실패 시 원본 구문을 적절히 분할하여 표시
        stmt_clean = stmt.strip()
        
        # 기본적인 키워드 기반 분할 시도
        action = "UNKNOWN"
        if stmt_clean.lower().startswith("allow"):
            action = "ALLOW"
            stmt_clean = stmt_clean[5:].strip()
        elif stmt_clean.lower().startswith("endorse"):
            action = "ENDORSE"
            stmt_clean = stmt_clean[7:].strip()
        
        # 'to' 키워드로 subject와 나머지 분리
        if " to " in stmt_clean.lower():
            parts = stmt_clean.split(" to ", 1)
            subject = parts[0].strip()
            remaining = parts[1].strip() if len(parts) > 1 else ""
        else:
            subject = stmt_clean[:50] + "..." if len(stmt_clean) > 50 else stmt_clean
            remaining = ""
        
        # 나머지 부분을 verb로 처리 (길이 제한)
        verb = remaining[:30] + "..." if len(remaining) > 30 else remaining
        
        return (
            action,
            subject[:40] + "..." if len(subject) > 40 else subject,
            verb,
            "UNPARSED",
            "-",
            "-"
        )
    
    action, subject, verb, resource, scope_content, condition_text = m.groups()
    
    # Verb 처리: { } 형태는 그대로 유지, 일반적인 경우만 대문자 변환
    if verb.startswith("{") and verb.endswith("}"):
        verb_processed = verb  # { } 형태는 그대로 유지
    else:
        verb_processed = verb.strip("{} ").upper()  # 일반적인 경우만 대문자 변환
    
    return (
        action.upper(),      # ALLOW / ENDORSE
        subject.strip(),     # e.g., service cloudguard / GROUP admins / any-user
        verb_processed,      # Verb - { } 형태는 그대로, 일반적인 경우는 대문자
        (resource.strip() if resource else "all-resources"),  # Resource type, default to "all-resources" if not specified
        (scope_content.strip() if scope_content else "-"), # Scope, e.g., compartment <name>, tenancy, or -
        (condition_text.strip() if condition_text else "-"), # Condition, or -
    )

###############################################################################
# main(args)
###############################################################################
def main(args):
    console = Console()
    start_ts = time.time()
    
    # 리소스 표시 여부 결정
    # 아무것도 안주면 인스턴스/LB/NSG/Volume/Object 다 표시
    if not (args.instance or args.lb or args.nsg or args.volume or args.object or args.cost or args.credit or args.policy):
        show_instance   = True
        show_lb         = True
        show_nsg        = True
        show_volume     = True
        show_object     = True
        show_policy     = False
        show_cost       = False
        show_credit     = False
    else:
        show_instance = args.instance
        show_lb       = args.lb
        show_nsg      = args.nsg
        show_volume   = args.volume
        show_object   = args.object
        show_policy   = args.policy
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
    pol_rows=[]

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

        if show_policy:
            fut_pol= executor.submit(collect_policies, identity_client, compartments, name_filter, console)
            futures.append(("policy", fut_pol))

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
                elif label=="policy":
                    pol_rows=data
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
                verbose_inst = args.verb
                t = Table(show_lines=False, box=box.SIMPLE_HEAVY)
                if verbose_inst:
                    # ───────── 상세(Verbose) 모드 ─────────
                    t.add_column("Comp", style="bold magenta")
                    t.add_column("Region", style="bold cyan")
                    t.add_column("AD", style="bold cyan")
                    t.add_column("Fault Domain", style="bold cyan")
                    t.add_column("Name", overflow="fold")
                    t.add_column("State", justify="center")
                    t.add_column("Subnet")
                    t.add_column("NSG")
                    t.add_column("PrivateIP")
                    t.add_column("PublicIP")
                    t.add_column("Shape")
                    t.add_column("vCPU", justify="right")
                    t.add_column("Mem", justify="right")
                    t.add_column("Boot")
                    t.add_column("Block")
                else:
                    # ───────── 요약(Default) 모드 ─────────
                    t.add_column("Comp", style="bold magenta")
                    t.add_column("Region", style="bold cyan")
                    t.add_column("Name", overflow="fold")
                    t.add_column("State", justify="center")
                    t.add_column("PrivateIP")
                    t.add_column("PublicIP")
                    t.add_column("Shape")
                    t.add_column("vCPU", justify="right")
                    t.add_column("Mem", justify="right")
                    t.add_column("Boot")
                    t.add_column("Block")
                # group by region, comp?
                curr_key=None
                for row in inst_rows:
                    key=(row["region"], row["compartment_name"])
                    if key!=curr_key:
                        if curr_key!=None:
                            t.add_section()
                        curr_key=key
                    if verbose_inst:
                        t.add_row(
                            row["compartment_name"],
                            row["region"],
                            row["ad"],
                            row["fault_domain"],
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
                    else:
                        t.add_row(
                            row["compartment_name"],
                            row["region"],
                            row["instance_name"],
                            row["state_colored"],
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
            # Compartment → Region → LoadBalancer Name 순으로 정렬
            lb_rows.sort(key=lambda x: (
                x["compartment_name"].lower(),
                x["region"].lower(),
                x["lb_name"].lower()
            ))
            console.print("\n[bold underline]LoadBalancer Info[/bold underline]")
            table= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            table.add_column("Compartment", style="bold magenta")
            table.add_column("Region", style="bold cyan")
            table.add_column("LB Name")
            table.add_column("LB State", justify="center")
            table.add_column("IP Addresses")
            table.add_column("Shape")
            table.add_column("Type")
            table.add_column("Min(Mbps)", justify="right")
            table.add_column("Max(Mbps)", justify="right")
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
                    row["min_bw"],
                    row["max_bw"],
                    row["backend_set"],
                    row["backend_target"]
                )
            console.print(table)
        else:
            console.print("(No LBs)")

    # 3) NSG
    if show_nsg:
        if nsg_rows:
            # Compartment → Region → NSG Name 순으로 정렬
            nsg_rows.sort(key=lambda x: (
                x["compartment_name"].lower(),
                x["region"].lower(),
                x["nsg_name"].lower()
            ))
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
            # Compartment → Region → Volume Name 순으로 정렬
            boot_rows.sort(key=lambda x: (
                x["compartment_name"].lower(),
                x["region"].lower(),
                x["volume_name"].lower()
            ))
            console.print("\n[bold underline]Boot Volumes[/bold underline]")
            bt= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            bt.add_column("Compartment", style="bold magenta")
            bt.add_column("Region", style="bold cyan")
            bt.add_column("Volume Name")
            bt.add_column("State", justify="center")
            bt.add_column("Size(GB)", justify="right")
            bt.add_column("VPU", justify="right")
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
                    row["vpu"],
                    row["attached"]
                )
            console.print(bt)
        else:
            console.print("(No Boot Volumes)")

        # block
        if block_rows:
            # Compartment → Region → Volume Name 순으로 정렬
            block_rows.sort(key=lambda x: (
                x["compartment_name"].lower(),
                x["region"].lower(),
                x["volume_name"].lower()
            ))
            console.print("\n[bold underline]Block Volumes[/bold underline]")
            bt2= Table(show_lines=False, box=box.SIMPLE_HEAVY)
            bt2.add_column("Compartment", style="bold magenta")
            bt2.add_column("Region", style="bold cyan")
            bt2.add_column("Volume Name")
            bt2.add_column("State", justify="center")
            bt2.add_column("Size(GB)", justify="right")
            bt2.add_column("VPU", justify="right")
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
                    row["vpu"],
                    row["attached"]
                )
            console.print(bt2)
        else:
            console.print("(No Block Volumes)")

    # 5) object
    if show_object:
        if obj_rows:
            # Compartment → Region → Bucket Name 순으로 정렬
            obj_rows.sort(key=lambda x: (
                x["compartment_name"].lower(),
                x["region"].lower(),
                x["bucket_name"].lower()
            ))
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

    # 6) policy
    if show_policy:
        if pol_rows:
            console.print("\n[bold underline]IAM Policies[/bold underline]")
            pt = Table(show_lines=False, box=box.SIMPLE_HEAVY)
            pt.add_column("Compartment", style="bold magenta")
            pt.add_column("Policy Name", style="bold cyan")
            pt.add_column("Action")      # ALLOW / ENDORSE
            pt.add_column("Subject")     # service cloudguard, GROUP admins, any-user
            pt.add_column("Verb")
            pt.add_column("Resource")
            pt.add_column("Scope")
            pt.add_column("Condition")
            curr_comp = curr_pol = None
            # pol_rows를 compartment_name, policy_name으로 정렬 (선택 사항이지만 권장)
            # pol_rows.sort(key=lambda x: (x["compartment_name"], x["policy_name"]))

            for row in pol_rows:
                # Compartment 변경 시 섹션 추가 및 curr_pol 초기화
                if row["compartment_name"] != curr_comp:
                    if curr_comp is not None:
                        pt.add_section()
                    curr_comp = row["compartment_name"]
                    curr_pol = None  # 새 compartment이므로 policy도 초기화

                # Policy 변경 시 (또는 첫 번째 policy일 때) curr_pol 업데이트
                # 이 부분은 실제 출력 로직에 직접적인 영향은 없으나, 상태 추적을 위해 유지
                if row["policy_name"] != curr_pol :
                    curr_pol = row["policy_name"]
                    # 여기서 새로운 policy가 시작됨을 알 수 있음.
                    # 만약 policy별로도 add_section()을 하고 싶다면 이 지점에서 처리 가능

                stmts = row["statements"].splitlines()
                first_statement_in_policy = True # 각 policy의 첫번째 statement인지 여부

                for stmt_str in stmts:
                    if not stmt_str.strip(): # 빈 statement 문자열은 건너뛰기
                        continue
                    action, subject, verb, resource, scope, cond = parse_stmt(stmt_str)

                    if first_statement_in_policy:
                        pt.add_row(
                            row["compartment_name"],
                            row["policy_name"],
                            action,
                            subject,
                            verb,
                            resource,
                            scope,
                            cond,
                        )
                        first_statement_in_policy = False
                    else:
                        pt.add_row(
                            "",  # 동일 policy 내 두 번째 statement부터는 Compartment 이름 생략
                            "",  # 동일 policy 내 두 번째 statement부터는 Policy 이름 생략
                            action,
                            subject,
                            verb,
                            resource,
                            scope,
                            cond,
                        )
            console.print(pt)
        else:
            console.print("(No Policies)")

    # 비용
    if show_cost:
        start_date, end_date = get_date_range(args.cost_start, args.cost_end)
        cost_data, currency_cd= get_compartment_costs(usage_client, config["tenancy"], start_date, end_date, console)
        if cost_data:
            print_cost_table(cost_data, console, start_date, end_date, currency_cd)
        else:
            console.print("(No Cost Data)")

    # 크레딧
    if show_credit:
        # ----- 날짜 범위 결정 -----
        if args.cost_start or args.cost_end:
            start_date, end_date = get_date_range(args.cost_start, args.cost_end)
        else:
            # 기본값: 2025-05-22 ~ 금일 00시
            start_date = datetime.datetime(2025, 5, 22)
            now = datetime.datetime.utcnow()
            end_date = datetime.datetime(now.year, now.month, now.day)

        if args.credit_initial is None or args.credit_initial == 0:
            args.credit_initial = 208698600.0

        cd, currency_cd = get_credit_usage(
            usage_client,
            config["tenancy"],
            start_date,
            end_date,
            args.credit_initial,
            console,
        )
        console.print(f"start_date: {start_date}, end_date: {end_date + datetime.timedelta(days=1)}")

        year_to_print = args.credit_year if args.credit_year else start_date.year
        if cd:
            print_credit_table(cd, console, year_to_print, args.credit_initial, currency_cd)
        else:
            console.print("(No Credit Data)")


    elapsed = time.time() - start_ts
    log_info_non_console(f"All OCI Info Collection Complete ({elapsed:.2f}s)")


if __name__=="__main__":
    import argparse
    parser= argparse.ArgumentParser(description="OCI Info (Highly Parallel)")
    add_arguments(parser)
    args= parser.parse_args()
    main(args)
    
