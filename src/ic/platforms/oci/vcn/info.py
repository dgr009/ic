#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import oci
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.progress_decorator import progress_bar, ManualProgress
from src.ic.platforms.oci.common.utils import get_all_subscribed_regions, get_compartments

def add_arguments(parser):
    """
    vcn info 명령에 필요한 인수를 추가합니다.
    """
    parser.add_argument("-r", "--regions", help="조회할 리전 (없으면 모든 구독 리전)")
    parser.add_argument("-c", "--compartment", help="조회할 컴파트먼트 이름 (부분 일치)")
    parser.add_argument("--name", help="필터링할 VCN 이름 (부분 일치)")

def resolve_network_entity(network_client, entity_id):
    """
    라우팅 규칙의 network_entity_id를 해석하여 사람이 읽기 쉬운 형태로 반환합니다.
    """
    if not entity_id:
        return "None"
    
    entity_type = entity_id.split('.')[1]
    
    try:
        if entity_type == "internetgateway":
            entity = network_client.get_internet_gateway(entity_id).data
            return f"{entity.display_name} (igw)"
        elif entity_type == "natgateway":
            entity = network_client.get_nat_gateway(entity_id).data
            return f"{entity.display_name} (ngw: {entity.nat_ip})"
        elif entity_type == "servicegateway":
            entity = network_client.get_service_gateway(entity_id).data
            services = ", ".join([s.service_name for s in entity.services])
            return f"{entity.display_name} (sgw: {services})"
        elif entity_type == "drg":
            entity = network_client.get_drg(entity_id).data
            return f"{entity.display_name} (dgw)"
        elif entity_type == "localpeeringgateway":
            entity = network_client.get_local_peering_gateway(entity_id).data
            return f"{entity.display_name} (lpg)"
        elif entity_type == "privateip":
            return f"Private IP ({entity_id})"
        else:
            return entity_id
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            return f"{entity_id} (Not Found)"
        return f"{entity_id} (Error: {e.code})"
    except Exception:
        return entity_id


@progress_bar("Collecting VCN and subnet information from compartment")
def fetch_vcn_one_comp(config, region, comp, name_filter):
    """
    하나의 컴파트먼트에서 VCN 및 관련 리소스 정보를 가져옵니다.
    """
    vcn_rows = []
    try:
        network_client = oci.core.VirtualNetworkClient(config)
        network_client.base_client.set_region(region)
        
        vcns = oci.pagination.list_call_get_all_results(
            network_client.list_vcns,
            compartment_id=comp.id,
            display_name=name_filter if name_filter else None
        ).data

        for vcn in vcns:
            subnets = oci.pagination.list_call_get_all_results(
                network_client.list_subnets,
                compartment_id=comp.id,
                vcn_id=vcn.id
            ).data

            if not subnets:
                vcn_rows.append({
                    "compartment": comp.name, "region": region,
                    "vcn_name": vcn.display_name, "vcn_cidr": vcn.cidr_block,
                    "subnet_name": "No Subnets", "subnet_cidr": "-", "route_table": "-", "route_rule": "-"
                })
                continue

            for subnet in subnets:
                route_table = network_client.get_route_table(subnet.route_table_id).data
                
                if not route_table.route_rules:
                    vcn_rows.append({
                        "compartment": comp.name, "region": region,
                        "vcn_name": vcn.display_name, "vcn_cidr": vcn.cidr_block,
                        "subnet_name": subnet.display_name, "subnet_cidr": subnet.cidr_block,
                        "route_table": route_table.display_name, "route_rule": "No Rules (Only Local Route)"
                    })
                    continue

                for rule in route_table.route_rules:
                    destination = rule.destination
                    target = resolve_network_entity(network_client, rule.network_entity_id)
                    dest_padded = destination.ljust(18)
                    rule_str = f"{dest_padded} > {target}"
                    
                    vcn_rows.append({
                        "compartment": comp.name, "region": region,
                        "vcn_name": vcn.display_name, "vcn_cidr": vcn.cidr_block,
                        "subnet_name": subnet.display_name, "subnet_cidr": subnet.cidr_block,
                        "route_table": route_table.display_name,
                        "route_rule": rule_str
                    })

    except oci.exceptions.ServiceError as e:
        Console().print(f"[bold red]Error in {comp.name}({region}): {e.message}[/bold red]")
    
    return vcn_rows


@progress_bar("Collecting VCN information across compartments and regions")
def collect_vcn_parallel_fast(config, compartments, region_list, name_filter, console, max_workers=20):
    """
    ThreadPoolExecutor를 사용하여 여러 리전과 컴파트먼트에서 VCN 정보를 병렬로 수집합니다.
    """
    vcn_rows = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_vcn_one_comp, config, region, comp, name_filter): (region, comp.name)
            for region in region_list
            for comp in compartments
        }

        for future in as_completed(futures):
            try:
                vcn_rows.extend(future.result())
            except Exception as e:
                region, comp_name = futures[future]
                console.print(f"[bold red]Error in thread for {comp_name} ({region}): {e}[/bold red]")
    return vcn_rows

def print_vcn_table(console, vcn_rows):
    """
    VCN 정보를 계층적인 테이블로 출력합니다.
    """
    table = Table(show_lines=False, box=box.HORIZONTALS)
    headers = [
        "Compartment", "Region", "VCN Name", "VCN CIDR",
        "Subnet Name", "Subnet CIDR", "Route Rule (Destination > Target)"
    ]
    table.add_column("Compartment", style="bold magenta")
    table.add_column("Region", style="bold blue")
    table.add_column("VCN Name", style="bold green")
    table.add_column("VCN CIDR", style="green")
    table.add_column("Subnet Name", style="cyan")
    table.add_column("Subnet CIDR", style="cyan")
    table.add_column("Route Rule (Destination > Target)", style="white", no_wrap=False)

    # 정렬
    vcn_rows.sort(key=lambda x: (x['compartment'].lower(), x['region'].lower(), x['vcn_name'].lower(), x['subnet_name'].lower(), x['route_rule']))

    last_comp = last_region = last_vcn = last_subnet = None

    for row in vcn_rows:
        comp_display = row['compartment'] if row['compartment'] != last_comp else ""
        if comp_display:
            if last_comp is not None:
                table.add_row(*[Rule(style="dim") for _ in headers])
            last_comp = row['compartment']
            last_region = None
            last_vcn = None
            last_subnet = None

        region_display = row['region'] if row['region'] != last_region else ""
        if region_display:
            if last_region is not None:
                table.add_row("", *[Rule(style="dim") for _ in range(len(headers) - 1)])
            last_region = row['region']
            last_vcn = None
            last_subnet = None

        vcn_display = row['vcn_name'] if row['vcn_name'] != last_vcn else ""
        vcn_cidr_display = row['vcn_cidr'] if row['vcn_name'] != last_vcn else ""
        if vcn_display:
            if last_vcn is not None:
                table.add_row("", "", *[Rule(style="dim") for _ in range(len(headers) - 2)])
            last_vcn = row['vcn_name']
            last_subnet = None
        
        subnet_display = row['subnet_name'] if row['subnet_name'] != last_subnet else ""
        subnet_cidr_display = row['subnet_cidr'] if row['subnet_name'] != last_subnet else ""
        if subnet_display:
            if last_subnet is not None and row['subnet_name'] != 'No Subnets':
                 table.add_row(*[""] * 4, *[Rule(style="dim") for _ in range(len(headers) - 4)])
            last_subnet = row['subnet_name']

        table.add_row(
            comp_display,
            region_display,
            vcn_display,
            vcn_cidr_display,
            subnet_display,
            subnet_cidr_display,
            row['route_rule']
        )
        
    console.print(table)

@progress_bar("OCI VCN Information Collection")
def main(args):
    """
    OCI VCN 정보 조회 메인 함수
    """
    console = Console()
    
    try:
        config = oci.config.from_file()
        identity_client = oci.identity.IdentityClient(config)
    except Exception as e:
        console.print(f"[bold red]OCI 설정 파일 로드 실패: {e}[/bold red]")
        sys.exit(1)

    # 컴파트먼트 및 리전 목록 가져오기
    compartments = get_compartments(identity_client, config["tenancy"], args.compartment)
    if args.regions:
        region_list = args.regions.split(',')
    else:
        region_list = get_all_subscribed_regions(identity_client, config["tenancy"])

    vcn_data = collect_vcn_parallel_fast(config, compartments, region_list, args.name, console)

    if vcn_data:
        print_vcn_table(console, vcn_data)
    else:
        console.print("[yellow]조회된 VCN 정보가 없습니다.[/yellow]")
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OCI VCN Info')
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
