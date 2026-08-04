#!/usr/bin/env python3
"""
VPC 정보 조회

AWS VPC info 에 대응.

Usage:
    ic tencent vpc info
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
    try:
        client = vpc_client.VpcClient(cred, region, make_client_profile())

        offset = 0
        limit = 100
        while True:
            req = models.DescribeVpcsRequest()
            req.Offset = str(offset)
            req.Limit = str(limit)
            resp = client.DescribeVpcs(req)
            vpcs = resp.VpcSet or []

            for vpc in vpcs:
                vpc_name = vpc.VpcName or "-"
                vpc_id   = vpc.VpcId or "-"

                if name_filter:
                    nf = name_filter.lower()
                    if nf not in vpc_name.lower() and nf not in vpc_id.lower():
                        continue
                cidr     = vpc.CidrBlock or "-"
                is_default = "[bold green]Yes[/bold green]" if vpc.IsDefault else "No"

                # 서브넷 수 조회
                try:
                    req2 = models.DescribeSubnetsRequest()
                    f2 = models.Filter()
                    f2.Name = "vpc-id"
                    f2.Values = [vpc_id]
                    req2.Filters = [f2]
                    resp2 = client.DescribeSubnets(req2)
                    subnet_count = str(resp2.TotalCount or 0)
                except Exception:
                    subnet_count = "?"

                rows.append({
                    "account":       account_name,
                    "region":        region,
                    "vpc_name":      vpc_name,
                    "vpc_id":        vpc_id,
                    "cidr":          cidr,
                    "is_default":    is_default,
                    "subnet_count":  subnet_count,
                    "create_time":   (vpc.CreatedTime or "-")[:10],
                })

            offset += len(vpcs)
            if offset >= (resp.TotalCount or 0) or len(vpcs) < limit:
                break

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

    return rows


def print_vpc_table(all_rows: List[Dict[str, Any]]) -> None:
    if not all_rows:
        console.print("[yellow]표시할 VPC 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["vpc_name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    headers = ["Account", "Region", "VPC Name", "VPC ID", "CIDR", "Default", "Subnets", "Created"]
    keys    = ["account", "region", "vpc_name", "vpc_id", "cidr", "is_default", "subnet_count", "create_time"]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
        elif h == "Subnets":
            table.add_column(h, justify="right")
        else:
            table.add_column(h)

    last_account = None
    last_region  = None

    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed  = row["region"] != last_region

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])

        display = [row["account"] if account_changed else "", row["region"] if (account_changed or region_changed) else ""]
        for k in keys[2:]:
            display.append(str(row.get(k, "-")))

        table.add_row(*display)
        last_account = row["account"]
        last_region  = row["region"]

    console.print(table)


def main(args) -> None:
    if not check_sdk_available():
        console.print("[red]❌ tencentcloud-sdk-python 이 설치되지 않았습니다.[/red]")
        sys.exit(1)

    accounts    = get_accounts(getattr(args, "account", None))
    regions     = get_tencent_regions(getattr(args, "regions", None))
    name_filter = getattr(args, "name", None)
    total_ops   = len(accounts) * len(regions)
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
                    progress.update(f"Processed {acct_name}/{region} - Found {len(result)} VPCs", advance=1)
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
    p = argparse.ArgumentParser(description="Tencent VPC 정보 (병렬 수집)")
    add_arguments(p)
    main(p.parse_args())
