#!/usr/bin/env python3
"""
NAT Gateway 정보 조회

AWS NAT info 에 대응.

Usage:
    ic tencent nat info
    ic tencent nat info -r ap-seoul
    ic tencent nat info -n "my-nat"
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
    make_client_profile, check_sdk_available, TENCENT_SDK_AVAILABLE
)

console = Console()

_NAT_STATE_COLORS = {
    "AVAILABLE": "[bold green]{s}[/bold green]",
    "UNAVAILABLE": "[bold red]{s}[/bold red]",
    "RUNNING": "[bold green]{s}[/bold green]",
}

def color_state(state: str) -> str:
    tmpl = _NAT_STATE_COLORS.get(state.upper())
    return tmpl.format(s=state) if tmpl else state


def fetch_nat_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    account_name = account.get("name", account.get("id", "unknown"))
    log_info_non_console(f"[NAT] 수집 시작: account={account_name}, region={region}")

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
        limit  = 100
        while True:
            req = models.DescribeNatGatewaysRequest()
            req.Offset = offset
            req.Limit  = limit
            if name_filter:
                f = models.Filter()
                f.Name   = "nat-gateway-name"
                f.Values = [f"*{name_filter}*"]
                req.Filters = [f]

            resp = client.DescribeNatGateways(req)
            nats = resp.NatGatewaySet or []

            for nat in nats:
                nat_id   = nat.NatGatewayId or "-"
                nat_name = nat.NatGatewayName or nat_id
                state    = color_state(nat.State or "UNKNOWN")
                vpc_id   = nat.VpcId or "-"

                # 대역폭 (Mbps)
                bandwidth = f"{nat.InternetMaxBandwidthOut or 0} Mbps"

                # EIP 목록
                eips = ", ".join(
                    addr.PublicIpAddress for addr in (nat.PublicIpAddressSet or [])
                ) or "-"

                # 타입
                nat_type = nat.NatProductVersion or "-"

                rows.append({
                    "account":    account_name,
                    "region":     region,
                    "nat_name":   nat_name,
                    "nat_id":     nat_id,
                    "state":      state,
                    "vpc_id":     vpc_id,
                    "eips":       eips,
                    "bandwidth":  bandwidth,
                    "nat_type":   nat_type,
                    "created":    (nat.CreatedTime or "-")[:10],
                })

            offset += len(nats)
            if offset >= (resp.TotalCount or 0) or len(nats) < limit:
                break

    except TencentCloudSDKException as e:
        log_info_non_console(f"[NAT] 수집 실패: {account_name}/{region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ NAT Gateway 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[NAT] 수집 실패: {account_name}/{region}: {e}")

    return rows


def print_nat_table(all_rows: List[Dict[str, Any]]) -> None:
    if not all_rows:
        console.print("[yellow]표시할 NAT Gateway 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["nat_name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    headers = ["Account", "Region", "Name", "NAT ID", "State", "VPC", "EIP(s)", "Bandwidth", "Type", "Created"]
    keys    = ["account", "region", "nat_name", "nat_id", "state", "vpc_id", "eips", "bandwidth", "nat_type", "created"]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
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

    with ManualProgress("Collecting NAT Gateway information across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_nat_one_account_region, account, region, name_filter)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    progress.update(f"Processed {acct_name}/{region} - Found {len(result)} NAT Gateways", advance=1)
                except Exception as e:
                    log_info_non_console(f"[NAT] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    print_nat_table(all_rows)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
    parser.add_argument("-n", "--name",    help="NAT Gateway 이름 필터")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent NAT Gateway 정보 (병렬 수집)")
    add_arguments(p)
    main(p.parse_args())
