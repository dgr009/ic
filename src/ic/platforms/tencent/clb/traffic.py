#!/usr/bin/env python3
"""
CLB (Cloud Load Balancer) 네트워크 트래픽 / 대역폭(Bandwidth) 통계 조회

Tencent Cloud 모니터링 SDK (GetMonitorData)를 연동하여 각 CLB의
- Client-to-CLB (Client In / Client Out Bandwidth)
- CLB-to-backend (Backend In / Backend Out Bandwidth)
대역폭 통계(Avg, Min, Max in Mbps) 및 총 데이터 전송량을 조회합니다.

Usage:
    ic tencent clb traffic
    ic tencent clb traffic -a my-account
    ic tencent clb traffic -r ap-seoul
    ic tencent clb traffic -n "web,api"
    ic tencent clb traffic -d 7           # 최근 7일간의 트래픽 조회 (기본값)
    ic tencent clb traffic -d 30          # 최근 30일간의 트래픽 조회
    ic tencent clb traffic -v             # Min / Max 상세 지표 포함
"""

import sys
import socket
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

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

_LB_TYPE_COLORS = {
    "OPEN":     "[bold green]Public[/bold green]",
    "INTERNAL": "[bold cyan]Internal[/bold cyan]",
}

_LB_STATUS_MAP = {
    1: "[bold green]Active[/bold green]",
    0: "[bold yellow]Creating[/bold yellow]",
    2: "[bold red]Shutdown[/bold red]",
}


def _get_status_display(status_code: int) -> str:
    return _LB_STATUS_MAP.get(status_code, f"Status({status_code})")


def resolve_clb_vip(lb, eip_map: Optional[Dict[str, List[str]]] = None) -> Tuple[str, str, List[str]]:
    """
    CLB 객체로부터 (주 쿼리용 IP, 표시용 VIP 문자열, 바인딩된 EIP 목록)을 반환합니다.
    사설 VIP와 공인 EIP가 둘 다 있으면 "10.x.x.x / 43.x.x.x" 형식으로 표시합니다.
    """
    vips = lb.LoadBalancerVips or []
    lb_id = getattr(lb, "LoadBalancerId", "") or ""
    domain = getattr(lb, "LoadBalancerDomain", None) or getattr(lb, "Domain", None) or ""

    matched_eips: List[str] = []
    if eip_map:
        if lb_id in eip_map:
            for e in eip_map[lb_id]:
                if e not in matched_eips:
                    matched_eips.append(e)
        for vip_ip in vips:
            if vip_ip in eip_map:
                for e in eip_map[vip_ip]:
                    if e not in matched_eips:
                        matched_eips.append(e)

    # 표시용 VIP 문자열 구성
    if vips and matched_eips:
        display_vip = f"{', '.join(vips)} / {', '.join(matched_eips)}"
        primary_ip = vips[0]
    elif vips:
        display_vip = ", ".join(vips)
        primary_ip = vips[0]
    elif matched_eips:
        display_vip = ", ".join(matched_eips)
        primary_ip = matched_eips[0]
    elif domain:
        display_vip = domain
        try:
            primary_ip = socket.gethostbyname(domain)
        except Exception:
            primary_ip = domain
    else:
        display_vip = "-"
        primary_ip = "-"

    return primary_ip, display_vip, matched_eips


def format_bandwidth(val_mbps: Optional[float]) -> str:
    """
    대역폭 값을 텐센트 콘솔과 동일한 Mbps 단위(소수점 2자리)로 포맷팅합니다.
    예: 0.18 Mbps, 0.62 Mbps, 12.50 Mbps
    """
    if val_mbps is None or val_mbps < 0:
        return "-"
    if val_mbps == 0:
        return "0.00 Mbps"
    if val_mbps < 0.01:
        return f"{val_mbps:.3f} Mbps"
    return f"{val_mbps:.2f} Mbps"


def format_total_data(gbytes: Optional[float]) -> str:
    """총 데이터 전송량을 포맷팅합니다 (GB / TB)."""
    if gbytes is None or gbytes < 0:
        return "-"
    if gbytes >= 1024:
        return f"{gbytes / 1024:.2f} TB"
    elif gbytes >= 1:
        return f"{gbytes:.2f} GB"
    elif gbytes >= 0.001:
        return f"{gbytes * 1024:.1f} MB"
    else:
        return f"{gbytes:.2f} GB"


def get_monitor_period_and_range(days: int) -> Tuple[str, str, int]:
    """조회 일수에 따른 StartTime, EndTime, Period(초)를 반환합니다."""
    now = datetime.now()
    start = now - timedelta(days=days)

    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = now.strftime("%Y-%m-%d %H:%M:%S")

    if days <= 1:
        period = 300     # 5분 단위
    elif days <= 7:
        period = 3600    # 1시간 단위
    else:
        period = 3600    # 1시간 단위

    return start_str, end_str, period


def fetch_metric_timeseries(
    mon_client,
    namespace: str,
    metric_name: str,
    dimensions: List[Dict[str, str]],
    start_time: str,
    end_time: str,
    period: int
) -> Optional[List[float]]:
    """Cloud Monitor API를 호출하여 시계열 데이터 포인트 리스트를 반환합니다."""
    from tencentcloud.monitor.v20180724 import models as mon_models

    try:
        req = mon_models.GetMonitorDataRequest()
        req.Namespace = namespace
        req.MetricName = metric_name
        req.Period = period
        req.StartTime = start_time
        req.EndTime = end_time

        dim_objs = []
        for d in dimensions:
            dim = mon_models.Dimension()
            dim.Name = d["Name"]
            dim.Value = d["Value"]
            dim_objs.append(dim)

        inst = mon_models.Instance()
        inst.Dimensions = dim_objs

        req.Instances = [inst]

        resp = mon_client.GetMonitorData(req)
        data_points = resp.DataPoints or []
        if not data_points:
            return None

        dp = data_points[0]
        raw_values = dp.Values or []
        if not raw_values:
            return None

        values = [(v if v is not None else 0.0) for v in raw_values]

        # 만약 단위가 bps/Bps(100,000 이상)로 온 경우 Mbps로 변환
        max_v = max(values) if values else 0.0
        if max_v > 100000:
            values = [v / 1000000.0 for v in values]

        return values
    except Exception as e:
        log_info_non_console(f"[CLB Traffic] GetMonitorData ({namespace}:{metric_name}) 실패: {e}")
        return None


def query_best_metric_series(
    mon_client,
    namespace: str,
    metric_candidates: List[str],
    dimension_sets: List[List[Dict[str, str]]],
    start_time: str,
    end_time: str,
    period: int
) -> List[float]:
    """
    여러 메트릭 후보와 차원 조합 중 유효한 데이터가 있는 첫 번째 시계열을 반환합니다.
    """
    for dims in dimension_sets:
        for m_name in metric_candidates:
            series = fetch_metric_timeseries(mon_client, namespace, m_name, dims, start_time, end_time, period)
            if series:
                # 0보다 큰 데이터가 존재하는지 확인
                if any(v > 0 for v in series):
                    return series

    # 0만 있는 데이터라도 가져올 수 있다면 첫 번째 시도 반환
    for dims in dimension_sets:
        for m_name in metric_candidates:
            series = fetch_metric_timeseries(mon_client, namespace, m_name, dims, start_time, end_time, period)
            if series:
                return series

    return []


def calculate_stats(series: List[float], period: int) -> Dict[str, float]:
    """시계열 데이터로부터 min, avg, max, total_gb를 계산합니다."""
    if not series:
        return {"min": 0.0, "avg": 0.0, "max": 0.0, "total_gb": 0.0}

    valid_vals = [v for v in series if v is not None]
    if not valid_vals:
        return {"min": 0.0, "avg": 0.0, "max": 0.0, "total_gb": 0.0}

    min_v = min(valid_vals)
    avg_v = sum(valid_vals) / len(valid_vals)
    max_v = max(valid_vals)
    total_gb = (sum(valid_vals) * period) / (8.0 * 1024.0)

    return {
        "min": min_v,
        "avg": avg_v,
        "max": max_v,
        "total_gb": total_gb,
    }


def fetch_clb_traffic_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str],
    days: int
) -> List[Dict[str, Any]]:
    """단일 계정 + 리전의 CLB 트래픽 통계를 수집합니다."""
    account_id = account.get("id", "unknown")
    account_name = account.get("name", account_id)

    log_info_non_console(f"[CLB Traffic] 수집 시작: account={account_name}, region={region}, days={days}")

    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.clb.v20180317 import clb_client, models as clb_models
        from tencentcloud.monitor.v20180724 import monitor_client
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    except ImportError:
        log_info_non_console("[CLB Traffic] SDK 모듈 import 실패")
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    rows = []
    try:
        clb_cli = clb_client.ClbClient(cred, region, make_client_profile())
        mon_cli = monitor_client.MonitorClient(cred, region, make_client_profile())

        start_time, end_time, period = get_monitor_period_and_range(days)

        # 0. EIP 매핑 수집 (VPC DescribeAddresses with pagination)
        eip_map: Dict[str, List[str]] = {}
        try:
            from tencentcloud.vpc.v20170312 import vpc_client as t_vpc_client, models as vpc_models
            v_cli = t_vpc_client.VpcClient(cred, region, make_client_profile())
            offset_eip = 0
            limit_eip = 100
            while True:
                req_eip = vpc_models.DescribeAddressesRequest()
                req_eip.Offset = offset_eip
                req_eip.Limit = limit_eip
                resp_eip = v_cli.DescribeAddresses(req_eip)
                addrs = resp_eip.AddressSet or []
                for addr in addrs:
                    if addr.AddressIp:
                        if addr.InstanceId:
                            eip_map.setdefault(addr.InstanceId, []).append(addr.AddressIp)
                        if addr.PrivateAddressIp:
                            eip_map.setdefault(addr.PrivateAddressIp, []).append(addr.AddressIp)
                offset_eip += len(addrs)
                if offset_eip >= (resp_eip.TotalCount or 0) or len(addrs) < limit_eip:
                    break
        except Exception as e:
            log_info_non_console(f"[CLB Traffic] DescribeAddresses 실패: {e}")

        # 1. CLB 목록 조회
        offset = 0
        limit = 100
        all_lbs = []
        while True:
            req = clb_models.DescribeLoadBalancersRequest()
            req.Offset = offset
            req.Limit = limit
            resp = clb_cli.DescribeLoadBalancers(req)
            lbs = resp.LoadBalancerSet or []
            all_lbs.extend(lbs)

            offset += len(lbs)
            if offset >= (resp.TotalCount or 0) or len(lbs) < limit:
                break

        # 2. 각 CLB별 트래픽 메트릭 조회
        for lb in all_lbs:
            lb_id = lb.LoadBalancerId or "-"
            lb_name = lb.LoadBalancerName or "-"

            if name_filter:
                patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                if patterns and not any(p in lb_name.lower() or p in lb_id.lower() for p in patterns):
                    continue

            lb_type_raw = lb.LoadBalancerType or "OPEN"
            lb_type = _LB_TYPE_COLORS.get(lb_type_raw, lb_type_raw)

            # VIP IP 주소와 표시용 VIP 문자열 분리 (사설 VIP 및 바인딩된 EIP 함께 해석)
            resolved_ip, display_vip, matched_eips = resolve_clb_vip(lb, eip_map)

            status = _get_status_display(lb.Status if lb.Status is not None else 1)
            vpc_id = lb.VpcId or "-"

            namespace = "QCE/LB_PUBLIC" if lb_type_raw == "OPEN" else "QCE/LB_PRIVATE"

            # 차원(Dimension) 조합 후보군 생성
            dim_sets = []
            if resolved_ip and resolved_ip != "-":
                if lb_type_raw == "OPEN":
                    dim_sets.append([{"Name": "vip", "Value": resolved_ip}])
                else:
                    if vpc_id != "-":
                        dim_sets.append([{"Name": "vip", "Value": resolved_ip}, {"Name": "vpcId", "Value": vpc_id}])
                    dim_sets.append([{"Name": "vip", "Value": resolved_ip}])

            # 바인딩된 EIP가 있으면 EIP 차원도 추가
            for eip_val in matched_eips:
                dim_sets.append([{"Name": "vip", "Value": eip_val}])
                dim_sets.append([{"Name": "eip", "Value": eip_val}])

            if lb_id and lb_id != "-":
                dim_sets.append([{"Name": "loadBalancerId", "Value": lb_id}])

            # -------------------------------------------------------------
            # 1) Client-to-CLB (Client Input / Output Bandwidth)
            # -------------------------------------------------------------
            client_in_metrics = ["ClientIntraffic", "intraffic", "InTraffic", "VipIntraffic", "ClientAccIntraffic"]
            client_out_metrics = ["ClientOuttraffic", "outtraffic", "OutTraffic", "VipOuttraffic", "ClientAccOuttraffic"]

            c_in_series = query_best_metric_series(mon_cli, namespace, client_in_metrics, dim_sets, start_time, end_time, period)
            c_out_series = query_best_metric_series(mon_cli, namespace, client_out_metrics, dim_sets, start_time, end_time, period)

            # QCE/LB fallback (VipIntraffic/VipOuttraffic)
            if not any(v > 0 for v in c_in_series) and lb_type_raw == "OPEN" and resolved_ip != "-":
                s_vip_in = fetch_metric_timeseries(mon_cli, "QCE/LB", "VipIntraffic", [{"Name": "eip", "Value": resolved_ip}], start_time, end_time, period)
                if s_vip_in and any(v > 0 for v in s_vip_in):
                    c_in_series = s_vip_in

            if not any(v > 0 for v in c_out_series) and lb_type_raw == "OPEN" and resolved_ip != "-":
                s_vip_out = fetch_metric_timeseries(mon_cli, "QCE/LB", "VipOuttraffic", [{"Name": "eip", "Value": resolved_ip}], start_time, end_time, period)
                if s_vip_out and any(v > 0 for v in s_vip_out):
                    c_out_series = s_vip_out

            # -------------------------------------------------------------
            # 2) CLB-to-backend (Backend Input / Output Bandwidth)
            # -------------------------------------------------------------
            backend_in_metrics = ["InTraffic", "intraffic", "ClientInpkg"]
            backend_out_metrics = ["OutTraffic", "outtraffic", "ClientOutpkg"]

            b_in_series = query_best_metric_series(mon_cli, namespace, backend_in_metrics, dim_sets, start_time, end_time, period)
            b_out_series = query_best_metric_series(mon_cli, namespace, backend_out_metrics, dim_sets, start_time, end_time, period)

            # 통계 계산
            c_in_stats = calculate_stats(c_in_series, period)
            c_out_stats = calculate_stats(c_out_series, period)
            b_in_stats = calculate_stats(b_in_series, period)
            b_out_stats = calculate_stats(b_out_series, period)

            # 총 데이터량 (Client In + Client Out 기준)
            total_client_data_gb = c_in_stats["total_gb"] + c_out_stats["total_gb"]

            rows.append({
                "account": account_name,
                "region": region,
                "lb_name": lb_name,
                "lb_id": lb_id,
                "type": lb_type,
                "vip": display_vip,
                "status": status,
                "days": f"{days}d",
                # Client-to-CLB
                "c_min_in": format_bandwidth(c_in_stats["min"]),
                "c_avg_in": format_bandwidth(c_in_stats["avg"]),
                "c_max_in": format_bandwidth(c_in_stats["max"]),
                "c_min_out": format_bandwidth(c_out_stats["min"]),
                "c_avg_out": format_bandwidth(c_out_stats["avg"]),
                "c_max_out": format_bandwidth(c_out_stats["max"]),
                # CLB-to-backend
                "b_min_in": format_bandwidth(b_in_stats["min"]),
                "b_avg_in": format_bandwidth(b_in_stats["avg"]),
                "b_max_in": format_bandwidth(b_in_stats["max"]),
                "b_min_out": format_bandwidth(b_out_stats["min"]),
                "b_avg_out": format_bandwidth(b_out_stats["avg"]),
                "b_max_out": format_bandwidth(b_out_stats["max"]),
                # Total
                "total_traffic": format_total_data(total_client_data_gb),
            })

    except TencentCloudSDKException as e:
        log_info_non_console(f"[CLB Traffic] 수집 실패: {account_name}/{region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ CLB Traffic 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[CLB Traffic] 수집 실패: {account_name}/{region}: {e}")
        return []

    log_info_non_console(f"[CLB Traffic] {len(rows)}개 수집 완료: account={account_name}, region={region}")
    return rows


def print_traffic_table(all_rows: List[Dict[str, Any]], days: int, verbose: bool = False) -> None:
    """CLB 트래픽 통계를 Rich 테이블로 출력합니다."""
    if not all_rows:
        console.print("[yellow]표시할 CLB 트래픽 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["lb_name"]))

    table = Table(
        box=box.HORIZONTALS,
        expand=False,
        show_header=True,
        header_style="bold",
        title=f"📊 [bold cyan]Tencent CLB Network Bandwidth Statistics (Past {days} Days)[/bold cyan]\n"
    )
    table.show_edge = False

    if verbose:
        # 상세 모드: Min, Avg, Max (Client & Backend 전체 포함)
        headers = [
            "Account", "Region", "CLB Name", "VIP", "Type", "Status", "Period",
            "Client In (Min/Avg/Max)", "Client Out (Min/Avg/Max)",
            "Backend In (Min/Avg/Max)", "Backend Out (Min/Avg/Max)",
            "Total Data"
        ]
    else:
        # 기본 모드: Client In/Out + Backend In/Out (Avg 중심)
        headers = [
            "Account", "Region", "CLB Name", "VIP", "Type", "Status", "Period",
            "Client In (Avg)", "Client Out (Avg)",
            "Backend In (Avg)", "Backend Out (Avg)",
            "Total Data"
        ]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
        elif h == "CLB Name":
            table.add_column(h, style="bold green")
        elif h == "Status":
            table.add_column(h, justify="center")
        elif "In" in h or "Out" in h or h == "Total Data":
            table.add_column(h, justify="right")
        else:
            table.add_column(h)

    last_account = None
    last_region = None

    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])

        display = [
            row["account"] if account_changed else "",
            row["region"] if (account_changed or region_changed) else "",
            row["lb_name"],
            row["vip"],
            row["type"],
            row["status"],
            row["days"],
        ]

        if verbose:
            c_in_str = f"{row['c_min_in']} / [bold]{row['c_avg_in']}[/bold] / {row['c_max_in']}"
            c_out_str = f"{row['c_min_out']} / [bold]{row['c_avg_out']}[/bold] / {row['c_max_out']}"
            b_in_str = f"{row['b_min_in']} / [bold]{row['b_avg_in']}[/bold] / {row['b_max_in']}"
            b_out_str = f"{row['b_min_out']} / [bold]{row['b_avg_out']}[/bold] / {row['b_max_out']}"

            display.extend([c_in_str, c_out_str, b_in_str, b_out_str, row["total_traffic"]])
        else:
            display.extend([
                row["c_avg_in"],
                row["c_avg_out"],
                row["b_avg_in"],
                row["b_avg_out"],
                row["total_traffic"]
            ])

        table.add_row(*display)
        last_account = row["account"]
        last_region = row["region"]

    console.print(table)


def main(args) -> None:
    if not check_sdk_available():
        console.print("[red]❌ tencentcloud-sdk-python 이 설치되지 않았습니다.[/red]")
        sys.exit(1)

    accounts = get_accounts(getattr(args, "account", None))
    regions = get_tencent_regions(getattr(args, "regions", None))
    name_filter = getattr(args, "name", None)
    days = int(getattr(args, "days", 7) or 7)
    verbose = bool(getattr(args, "verbose", False))

    total_ops = len(accounts) * len(regions)
    all_rows: List[Dict[str, Any]] = []

    with ManualProgress(f"Collecting CLB traffic statistics (past {days} days) across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_clb_traffic_one_account_region, account, region, name_filter, days)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    progress.update(f"Processed {acct_name}/{region} - Found {len(result)} CLBs", advance=1)
                except Exception as e:
                    log_info_non_console(f"[CLB Traffic] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    print_traffic_table(all_rows, days, verbose)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
    parser.add_argument("-n", "--name", help="CLB 이름/ID 필터 (콤마(,)로 복수 검색 가능, 예: web,api)")
    parser.add_argument("-d", "--days", type=int, default=7, help="조회 기간 일수 (기본값: 7일, 예: -d 30)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Min, Max 등 상세 메트릭 포함 출력")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent CLB 네트워크 대역폭/트래픽 통계 조회")
    add_arguments(p)
    main(p.parse_args())
