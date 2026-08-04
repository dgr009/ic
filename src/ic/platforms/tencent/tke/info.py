#!/usr/bin/env python3
"""
TKE (Tencent Kubernetes Engine) 클러스터 정보 조회

AWS EKS info 에 대응.

Usage:
    ic tencent tke info
    ic tencent tke info -r ap-seoul
    ic tencent tke info -n "my-cluster"
    ic tencent tke info -v
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

_STATUS_COLORS = {
    "Running":    "[bold green]{s}[/bold green]",
    "Creating":   "[bold cyan]{s}[/bold cyan]",
    "Abnormal":   "[bold red]{s}[/bold red]",
    "Deleting":   "[bold magenta]{s}[/bold magenta]",
    "Upgrading":  "[bold yellow]{s}[/bold yellow]",
}

def color_status(status: str) -> str:
    tmpl = _STATUS_COLORS.get(status)
    return tmpl.format(s=status) if tmpl else status


def fetch_tke_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    account_name = account.get("name", account.get("id", "unknown"))
    log_info_non_console(f"[TKE] 수집 시작: account={account_name}, region={region}")

    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.tke.v20180525 import tke_client, models
    except ImportError:
        log_info_non_console("[TKE] TKE SDK 모듈 import 실패")
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    rows = []
    try:
        client = tke_client.TkeClient(cred, region, make_client_profile())

        offset = 0
        limit  = 100
        while True:
            req = models.DescribeClustersRequest()
            req.Offset = offset
            req.Limit  = limit
            resp = client.DescribeClusters(req)
            clusters = resp.Clusters or []

            for c in clusters:
                cluster_id   = c.ClusterId or "-"
                cluster_name = c.ClusterName or cluster_id

                if name_filter:
                    nf = name_filter.lower()
                    if nf not in cluster_name.lower() and nf not in cluster_id.lower():
                        continue
                status       = color_status(c.ClusterStatus or "Unknown")
                version      = c.ClusterVersion or "-"
                node_count   = str(c.ClusterNodeNum or 0)
                cluster_type = c.ClusterType or "-"   # MANAGED_CLUSTER / INDEPENDENT_CLUSTER
                vpc_id       = c.ClusterNetworkSettings.VpcId if c.ClusterNetworkSettings else "-"
                cidr         = c.ClusterNetworkSettings.ClusterCIDR if c.ClusterNetworkSettings else "-"
                description  = c.ClusterDescription or "-"
                os_name      = c.ClusterOs or "-"

                rows.append({
                    "account":       account_name,
                    "region":        region,
                    "cluster_name":  cluster_name,
                    "cluster_id":    cluster_id,
                    "status":        status,
                    "version":       version,
                    "node_count":    node_count,
                    "cluster_type":  cluster_type,
                    "vpc_id":        vpc_id,
                    "pod_cidr":      cidr,
                    "os":            os_name,
                    "description":   description,
                })

            offset += len(clusters)
            if offset >= (resp.TotalCount or 0) or len(clusters) < limit:
                break

    except TencentCloudSDKException as e:
        log_info_non_console(f"[TKE] 수집 실패: {account_name}/{region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ TKE 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[TKE] 수집 실패: {account_name}/{region}: {e}")

    log_info_non_console(f"[TKE] {len(rows)}개 수집 완료: account={account_name}, region={region}")
    return rows


def print_tke_table(all_rows: List[Dict[str, Any]], verbose: bool) -> None:
    if not all_rows:
        console.print("[yellow]표시할 TKE 클러스터 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["cluster_name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")

    if verbose:
        headers = ["Account", "Region", "Name", "Cluster ID", "Status", "Version", "Nodes", "Type", "VPC", "Pod CIDR", "OS", "Description"]
        keys    = ["account", "region", "cluster_name", "cluster_id", "status", "version", "node_count", "cluster_type", "vpc_id", "pod_cidr", "os", "description"]
    else:
        headers = ["Account", "Region", "Name", "Status", "Version", "Nodes", "Type"]
        keys    = ["account", "region", "cluster_name", "status", "version", "node_count", "cluster_type"]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
        elif h == "Nodes":
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
            else:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])

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
    verbose     = getattr(args, "verbose", False)
    total_ops   = len(accounts) * len(regions)
    all_rows: List[Dict[str, Any]] = []

    with ManualProgress("Collecting TKE clusters across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_tke_one_account_region, account, region, name_filter)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    progress.update(f"Processed {acct_name}/{region} - Found {len(result)} clusters", advance=1)
                except Exception as e:
                    log_info_non_console(f"[TKE] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    print_tke_table(all_rows, verbose)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
    parser.add_argument("-n", "--name",    help="클러스터 이름 필터")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 정보 출력")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent TKE 클러스터 정보 (병렬 수집)")
    add_arguments(p)
    main(p.parse_args())
