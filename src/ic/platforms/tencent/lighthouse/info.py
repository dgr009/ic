#!/usr/bin/env python3
"""
Lighthouse (轻量应用服务器) 인스턴스 정보 조회

AWS Lightsail 과 유사한 Tencent Cloud 경량 서버 서비스.

Usage:
    ic tencent lighthouse info
    ic tencent lighthouse info -r ap-seoul
    ic tencent lighthouse info -n "my-server"
    ic tencent lighthouse info -v
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

_LH_STATE_COLORS = {
    "RUNNING":      "[bold green]{s}[/bold green]",
    "STOPPED":      "[bold yellow]{s}[/bold yellow]",
    "REBOOTING":    "[bold cyan]{s}[/bold cyan]",
    "SHUTDOWN":     "[bold red]{s}[/bold red]",
    "CREATING":     "[bold cyan]{s}[/bold cyan]",
    "RESETTING":    "[bold magenta]{s}[/bold magenta]",
    "STARTING":     "[bold cyan]{s}[/bold cyan]",
    "STOPPING":     "[bold magenta]{s}[/bold magenta]",
}

def color_state(state: str) -> str:
    tmpl = _LH_STATE_COLORS.get(state.upper())
    return tmpl.format(s=state) if tmpl else state


def fetch_lighthouse_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    account_name = account.get("name", account.get("id", "unknown"))
    log_info_non_console(f"[Lighthouse] 수집 시작: account={account_name}, region={region}")

    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.lighthouse.v20200324 import lighthouse_client, models
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    except ImportError:
        log_info_non_console("[Lighthouse] Lighthouse SDK 모듈 import 실패")
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    rows = []
    try:
        # Lighthouse 는 국제 리전용 endpoint 별도 사용
        profile = make_client_profile(endpoint="lighthouse.intl.tencentcloudapi.com")
        client  = lighthouse_client.LighthouseClient(cred, region, profile)

        offset = 0
        limit  = 100
        while True:
            req = models.DescribeInstancesRequest()
            req.Offset = offset
            req.Limit  = limit

            if name_filter:
                f = models.Filter()
                f.Name   = "instance-name"
                f.Values = [f"*{name_filter}*"]
                req.Filters = [f]

            resp = client.DescribeInstances(req)
            instances = resp.InstanceSet or []

            for inst in instances:
                inst_id   = inst.InstanceId or "-"
                inst_name = inst.InstanceName or inst_id
                state     = color_state(inst.InstanceState or "UNKNOWN")

                # CPU / Memory 스펙 정보
                cpu    = str(inst.CPU) if inst.CPU is not None else "-"
                mem_gb = str(inst.Memory) if inst.Memory is not None else "-"

                # 번들(스펙) 및 디스크 정보
                bundle_id = inst.BundleId or "-"
                disk      = "-"

                if inst.SystemDisk:
                    disk = f"{inst.SystemDisk.DiskSize or 0} GB"

                # 네트워크 정보
                public_ip  = "-"
                private_ip = "-"
                if inst.PublicAddresses:
                    public_ip = inst.PublicAddresses[0]
                if inst.PrivateAddresses:
                    private_ip = inst.PrivateAddresses[0]

                # 리전 / AZ
                zone = inst.Zone or region

                # 과금 / 만료
                charge_type  = inst.InstanceChargeType or "-"
                expired_time = (inst.ExpiredTime or "-")[:10]
                created_time = (inst.CreatedTime or "-")[:10]

                rows.append({
                    "account":      account_name,
                    "region":       region,
                    "zone":         zone,
                    "name":         inst_name,
                    "instance_id":  inst_id,
                    "state":        state,
                    "private_ip":   private_ip,
                    "public_ip":    public_ip,
                    "vcpu":         cpu,
                    "memory":       mem_gb,
                    "bundle_id":    bundle_id,
                    "disk":         disk,
                    "charge_type":  charge_type,
                    "expired_time": expired_time,
                    "created_time": created_time,
                })

            offset += len(instances)
            if offset >= (resp.TotalCount or 0) or len(instances) < limit:
                break

    except TencentCloudSDKException as e:
        log_info_non_console(f"[Lighthouse] 수집 실패: {account_name}/{region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ Lighthouse 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[Lighthouse] 수집 실패: {account_name}/{region}: {e}")
        return []

    log_info_non_console(f"[Lighthouse] {len(rows)}개 수집 완료: account={account_name}, region={region}")
    return rows


def print_lighthouse_table(all_rows: List[Dict[str, Any]], verbose: bool) -> None:
    if not all_rows:
        console.print("[yellow]표시할 Lighthouse 인스턴스 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")

    if verbose:
        headers = [
            "Account", "Region", "Zone", "Name", "Instance ID", "State",
            "Private IP", "Public IP", "vCPU", "Mem", "Bundle", "Disk",
            "Charge", "Expired", "Created"
        ]
        keys = [
            "account", "region", "zone", "name", "instance_id", "state",
            "private_ip", "public_ip", "vcpu", "memory", "bundle_id", "disk",
            "charge_type", "expired_time", "created_time"
        ]
    else:
        headers = [
            "Account", "Region", "Name", "State",
            "Private IP", "Public IP", "vCPU", "Mem", "Bundle", "Disk"
        ]
        keys = [
            "account", "region", "name", "state",
            "private_ip", "public_ip", "vcpu", "memory", "bundle_id", "disk"
        ]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
        elif h == "State":
            table.add_column(h, justify="center")
        elif h in ("vCPU", "Mem"):
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
        console.print("[yellow]   pip install tencentcloud-sdk-python[/yellow]")
        sys.exit(1)

    accounts    = get_accounts(getattr(args, "account", None))
    if not accounts:
        console.print("[red]❌ Tencent 계정 설정이 없습니다.[/red]")
        sys.exit(1)

    regions     = get_tencent_regions(getattr(args, "regions", None))
    name_filter = getattr(args, "name", None)
    verbose     = getattr(args, "verbose", False)
    total_ops   = len(accounts) * len(regions)
    all_rows: List[Dict[str, Any]] = []

    with ManualProgress("Collecting Lighthouse instances across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_lighthouse_one_account_region, account, region, name_filter)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    progress.update(f"Processed {acct_name}/{region} - Found {len(result)} instances", advance=1)
                except Exception as e:
                    log_info_non_console(f"[Lighthouse] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    print_lighthouse_table(all_rows, verbose)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
    parser.add_argument("-n", "--name", help="인스턴스 이름 필터 (부분 일치)")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 정보 출력 (Bundle ID, AZ, 만료일 등)")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent Lighthouse 인스턴스 정보 (병렬 수집)")
    add_arguments(p)
    main(p.parse_args())
