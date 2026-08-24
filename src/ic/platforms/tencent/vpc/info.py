#!/usr/bin/env python3
"""
VPC 정보 조회 (상세 계층 및 라우팅 룰 분석)

AWS VPC info와 완벽히 동일한 스타일로 계정, 리전, VPC, Subnet, Route Table, Route Rule 정보 제공.

Usage:
    ic tencent vpc info
    ic tencent vpc info -a my-account
    ic tencent vpc info -r ap-seoul
    ic tencent vpc info -n "my-vpc"
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

try:
    from common.log import log_info_non_console
    from common.progress_decorator import ManualProgress
except ImportError:
    def log_info_non_console(msg): pass
    class ManualProgress:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def update(self, *a, **kw): pass

from ic.platforms.tencent.client import (
    get_accounts, get_credential_for_account, get_tencent_regions,
    make_client_profile, check_sdk_available, TENCENT_SDK_AVAILABLE,
    TencentCloudSDKException
)

console = Console()


def resolve_route_target(route, vpc_client_obj, target_cache: Dict[tuple, str], cred, region: str) -> str:
    """
    Tencent Cloud Route 객체를 받아 타겟의 이름과 유형, IP를 반환합니다.
    """
    gw_type = (route.GatewayType or "").upper()
    gw_id = route.GatewayId or ""

    if not gw_id and not gw_type:
        return "N/A"

    if gw_type == "LOCAL" or gw_id == "local":
        return "local"

    if gw_type in ("INTERNET", "IGW") or gw_id.startswith("igw-"):
        return "(igw)"

    cache_key = (gw_type, gw_id)
    if cache_key in target_cache:
        return target_cache[cache_key]

    target_str = f"{gw_id} ({gw_type.lower()})" if gw_type else gw_id

    try:
        from tencentcloud.vpc.v20170312 import models as vpc_models

        if gw_type == "NAT" or gw_id.startswith("nat-"):
            try:
                req = vpc_models.DescribeNatGatewaysRequest()
                req.NatGatewayIds = [gw_id]
                resp = vpc_client_obj.DescribeNatGateways(req)
                nats = resp.NatGatewaySet or []
                if nats:
                    nat = nats[0]
                    nat_name = nat.NatGatewayName or gw_id
                    eips = ", ".join(nat.PublicIpAddressSet or [])
                    ip_str = f": {eips}" if eips else ""
                    target_str = f"{nat_name} (nat{ip_str})"
                else:
                    target_str = f"{gw_id} (nat)"
            except Exception:
                target_str = f"{gw_id} (nat)"

        elif gw_type in ("VPN", "VGW") or gw_id.startswith("vpngw-"):
            try:
                req = vpc_models.DescribeVpnGatewaysRequest()
                req.VpnGatewayIds = [gw_id]
                resp = vpc_client_obj.DescribeVpnGateways(req)
                vgws = resp.VpnGatewaySet or []
                if vgws:
                    vgw = vgws[0]
                    vgw_name = vgw.VpnGatewayName or gw_id
                    pub_ip = vgw.PublicIpAddress or ""
                    ip_str = f": {pub_ip}" if pub_ip else ""
                    target_str = f"{vgw_name} (vpn{ip_str})"
                else:
                    target_str = f"{gw_id} (vpn)"
            except Exception:
                target_str = f"{gw_id} (vpn)"

        elif gw_type == "PEERCONNECTION" or gw_id.startswith("pcx-"):
            try:
                req = vpc_models.DescribeVpcPeeringConnectionsRequest()
                req.PeeringConnectionIds = [gw_id]
                resp = vpc_client_obj.DescribeVpcPeeringConnections(req)
                pcxs = resp.PeerConnectionSet or []
                if pcxs:
                    pcx_name = pcxs[0].PeeringConnectionName or gw_id
                    target_str = f"{pcx_name} (pcx)"
                else:
                    target_str = f"{gw_id} (pcx)"
            except Exception:
                target_str = f"{gw_id} (pcx)"

        elif gw_type == "DIRECTCONNECT" or gw_id.startswith("dcg-"):
            try:
                req = vpc_models.DescribeDirectConnectGatewaysRequest()
                req.DirectConnectGatewayIds = [gw_id]
                resp = vpc_client_obj.DescribeDirectConnectGateways(req)
                dcgs = resp.DirectConnectGatewaySet or []
                if dcgs:
                    dcg_name = dcgs[0].DirectConnectGatewayName or gw_id
                    target_str = f"{dcg_name} (dcg)"
                else:
                    target_str = f"{gw_id} (dcg)"
            except Exception:
                target_str = f"{gw_id} (dcg)"

        elif gw_type == "CCN" or gw_id.startswith("ccn-"):
            try:
                req = vpc_models.DescribeCcnsRequest()
                req.CcnIds = [gw_id]
                resp = vpc_client_obj.DescribeCcns(req)
                ccns = resp.CcnSet or []
                if ccns:
                    ccn_name = ccns[0].CcnName or gw_id
                    target_str = f"{ccn_name} (ccn)"
                else:
                    target_str = f"{gw_id} (ccn)"
            except Exception:
                target_str = f"{gw_id} (ccn)"

        elif gw_type in ("NORMAL_CVM", "CVM") or gw_id.startswith("ins-"):
            try:
                from tencentcloud.cvm.v20170312 import cvm_client, models as cvm_models
                c_client = cvm_client.CvmClient(cred, region, make_client_profile())
                req = cvm_models.DescribeInstancesRequest()
                req.InstanceIds = [gw_id]
                resp = c_client.DescribeInstances(req)
                insts = resp.InstanceSet or []
                if insts:
                    inst = insts[0]
                    inst_name = inst.InstanceName or gw_id
                    pub_ip = (inst.PublicIpAddresses or [None])[0]
                    priv_ip = (inst.PrivateIpAddresses or [None])[0]
                    ip = pub_ip or priv_ip or ""
                    ip_str = f": {ip}" if ip else ""
                    target_str = f"{inst_name} (instance{ip_str})"
                else:
                    target_str = f"{gw_id} (instance)"
            except Exception:
                target_str = f"{gw_id} (instance)"

        elif gw_type == "HAVIP" or gw_id.startswith("havip-"):
            target_str = f"{gw_id} (havip)"

    except Exception:
        pass

    target_cache[cache_key] = target_str
    return target_str


def fetch_vpc_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    account_name = account.get("name", account.get("id", "unknown"))
    log_info_non_console(f"[VPC] 수집 시작: account={account_name}, region={region}")

    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.vpc.v20170312 import vpc_client, models
    except ImportError:
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    rows = []
    target_cache: Dict[tuple, str] = {}

    try:
        client = vpc_client.VpcClient(cred, region, make_client_profile())

        # 1. VPC 목록 조회
        offset = 0
        limit = 100
        all_vpcs = []
        while True:
            req = models.DescribeVpcsRequest()
            req.Offset = str(offset)
            req.Limit = str(limit)
            resp = client.DescribeVpcs(req)
            vpcs = resp.VpcSet or []
            all_vpcs.extend(vpcs)
            offset += len(vpcs)
            if offset >= (resp.TotalCount or 0) or len(vpcs) < limit:
                break

        for vpc in all_vpcs:
            vpc_name = vpc.VpcName or vpc.VpcId or "-"
            vpc_id = vpc.VpcId or "-"
            vpc_cidr = vpc.CidrBlock or "-"

            if name_filter:
                nf = name_filter.lower()
                if nf not in vpc_name.lower() and nf not in vpc_id.lower():
                    continue

            # 2. 해당 VPC의 Subnet 목록 조회
            try:
                req_sub = models.DescribeSubnetsRequest()
                f_sub = models.Filter()
                f_sub.Name = "vpc-id"
                f_sub.Values = [vpc_id]
                req_sub.Filters = [f_sub]
                req_sub.Limit = "100"
                resp_sub = client.DescribeSubnets(req_sub)
                subnets = resp_sub.SubnetSet or []
            except Exception as e:
                log_info_non_console(f"[VPC] 서브넷 조회 실패 ({vpc_id}): {e}")
                subnets = []

            # 3. 해당 VPC의 Route Table 목록 조회
            try:
                req_rt = models.DescribeRouteTablesRequest()
                f_rt = models.Filter()
                f_rt.Name = "vpc-id"
                f_rt.Values = [vpc_id]
                req_rt.Filters = [f_rt]
                req_rt.Limit = "100"
                resp_rt = client.DescribeRouteTables(req_rt)
                route_tables = resp_rt.RouteTableSet or []
            except Exception as e:
                log_info_non_console(f"[VPC] 라우트 테이블 조회 실패 ({vpc_id}): {e}")
                route_tables = []

            rt_map = {rt.RouteTableId: rt for rt in route_tables}
            main_rt = next((rt for rt in route_tables if rt.Main), None) or (route_tables[0] if route_tables else None)

            if not subnets:
                rows.append({
                    "account": account_name,
                    "region": region,
                    "vpc_name": vpc_name,
                    "vpc_cidr": vpc_cidr,
                    "subnet_name": "No Subnets",
                    "subnet_cidr": "-",
                    "route_table": "-",
                    "route_rule": "-"
                })
                continue

            for subnet in subnets:
                subnet_name = subnet.SubnetName or subnet.SubnetId or "-"
                subnet_cidr = subnet.CidrBlock or "-"

                # 서브넷의 라우팅 테이블 찾기 (없으면 Main RT)
                rt_id = subnet.RouteTableId
                rt = rt_map.get(rt_id) or main_rt

                if not rt:
                    rows.append({
                        "account": account_name,
                        "region": region,
                        "vpc_name": vpc_name,
                        "vpc_cidr": vpc_cidr,
                        "subnet_name": subnet_name,
                        "subnet_cidr": subnet_cidr,
                        "route_table": "Not Found",
                        "route_rule": "-"
                    })
                    continue

                rt_name = rt.RouteTableName or rt.RouteTableId or "-"
                routes = rt.RouteSet or []

                if not routes:
                    rows.append({
                        "account": account_name,
                        "region": region,
                        "vpc_name": vpc_name,
                        "vpc_cidr": vpc_cidr,
                        "subnet_name": subnet_name,
                        "subnet_cidr": subnet_cidr,
                        "route_table": rt_name,
                        "route_rule": "No explicit routes"
                    })
                else:
                    for route in routes:
                        dest = route.DestinationCidrBlock or route.DestinationIpv6CidrBlock or "0.0.0.0/0"
                        target = resolve_route_target(route, client, target_cache, cred, region)
                        dest_padded = dest.ljust(18)
                        rows.append({
                            "account": account_name,
                            "region": region,
                            "vpc_name": vpc_name,
                            "vpc_cidr": vpc_cidr,
                            "subnet_name": subnet_name,
                            "subnet_cidr": subnet_cidr,
                            "route_table": rt_name,
                            "route_rule": f"{dest_padded} -> {target}"
                        })

    except TencentCloudSDKException as e:
        log_info_non_console(f"[VPC] 수집 실패: {account_name}/{region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ VPC 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[VPC] 수집 실패: {account_name}/{region}: {e}")
        return []

    return rows


def print_vpc_table(all_rows: List[Dict[str, Any]]) -> None:
    if not all_rows:
        console.print("[yellow]표시할 VPC 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["vpc_name"], x["subnet_name"], x["route_table"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.show_edge = False

    headers = ["Account", "Region", "VPC Name", "VPC CIDR", "Subnet Name", "Subnet CIDR", "Route Table", "Route Rule"]
    keys = ["account", "region", "vpc_name", "vpc_cidr", "subnet_name", "subnet_cidr", "route_table", "route_rule"]

    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("VPC Name", max_width=25, overflow="ellipsis", style="bold green")
    table.add_column("VPC CIDR", style="green")
    table.add_column("Subnet Name", max_width=35, overflow="ellipsis", style="cyan")
    table.add_column("Subnet CIDR", style="cyan")
    table.add_column("Route Table", max_width=35, overflow="ellipsis", style="white")
    table.add_column("Route Rule")

    last_account, last_region, last_vpc, last_subnet, last_route_table = None, None, None, None, None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region
        vpc_changed = row["vpc_name"] != last_vpc
        subnet_changed = row["subnet_name"] != last_subnet
        route_table_changed = row["route_table"] != last_route_table

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif vpc_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])
            elif subnet_changed:
                table.add_row("", "", "", "", *[Rule(style="dim") for _ in headers[4:]])
            elif route_table_changed:
                table.add_row("", "", "", "", "", "", *[Rule(style="dim") for _ in headers[6:]])

        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")
        display_values.append(row["vpc_name"] if account_changed or region_changed or vpc_changed else "")
        display_values.append(row["vpc_cidr"] if account_changed or region_changed or vpc_changed else "")
        display_values.append(row["subnet_name"] if account_changed or region_changed or vpc_changed or subnet_changed else "")
        display_values.append(row["subnet_cidr"] if account_changed or region_changed or vpc_changed or subnet_changed else "")
        display_values.append(row["route_table"] if account_changed or region_changed or vpc_changed or subnet_changed or route_table_changed else "")

        for k in keys[7:]:
            display_values.append(str(row.get(k, "-")))

        table.add_row(*display_values)
        last_account, last_region, last_vpc, last_subnet, last_route_table = row["account"], row["region"], row["vpc_name"], row["subnet_name"], row["route_table"]

    console.print(table)


def main(args) -> None:
    if not check_sdk_available():
        console.print("[red]❌ tencentcloud-sdk-python 이 설치되지 않았습니다.[/red]")
        sys.exit(1)

    accounts = get_accounts(getattr(args, "account", None))
    regions = get_tencent_regions(getattr(args, "regions", None))
    name_filter = getattr(args, "name", None)
    total_ops = len(accounts) * len(regions)
    all_rows: List[Dict[str, Any]] = []

    with ManualProgress("Collecting VPC information across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_vpc_one_account_region, account, region, name_filter)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    vpc_count = len(set(row['vpc_name'] for row in result))
                    progress.update(f"Processed {acct_name}/{region} - Found {vpc_count} VPCs", advance=1)
                except Exception as e:
                    log_info_non_console(f"[VPC] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    print_vpc_table(all_rows)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
    parser.add_argument("-n", "--name", help="VPC 이름 필터")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent VPC 정보 (상세 계층 및 라우팅 분석)")
    add_arguments(p)
    main(p.parse_args())
