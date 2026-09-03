#!/usr/bin/env python3
"""
CLB (Cloud Load Balancer) 상세 정보 조회

AWS LB info 에 대응하는 명령어.
Listener, Target Group, Target Instance, Health Check Path, Health Status 정보 제공.

Usage:
    ic tencent clb info
    ic tencent clb info -a my-account
    ic tencent clb info -r ap-seoul
    ic tencent clb info -n "my-lb"
    ic tencent clb info -v
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


def fetch_clb_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    account_id = account.get("id", "unknown")
    account_name = account.get("name", account_id)

    log_info_non_console(f"[CLB] 수집 시작: account={account_name}, region={region}")

    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.clb.v20180317 import clb_client, models
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    except ImportError:
        log_info_non_console("[CLB] CLB SDK 모듈 import 실패")
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    rows = []
    try:
        client = clb_client.ClbClient(cred, region, make_client_profile())

        # 0. EIP 매핑 수집 (VPC DescribeAddresses with pagination)
        eip_map = {}
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
            log_info_non_console(f"[CLB] DescribeAddresses 실패: {e}")

        offset = 0
        limit = 100
        while True:
            req = models.DescribeLoadBalancersRequest()
            req.Offset = offset
            req.Limit = limit
            resp = client.DescribeLoadBalancers(req)
            lbs = resp.LoadBalancerSet or []

            for lb in lbs:
                lb_id = lb.LoadBalancerId or "-"
                lb_name = lb.LoadBalancerName or "-"

                if name_filter:
                    patterns = [p.strip().lower() for p in name_filter.split(",") if p.strip()]
                    if patterns and not any(p in lb_name.lower() or p in lb_id.lower() for p in patterns):
                        continue
                lb_type_raw = lb.LoadBalancerType or "-"
                lb_type = _LB_TYPE_COLORS.get(lb_type_raw, lb_type_raw)

                raw_vips = lb.LoadBalancerVips or []
                matched_eips = eip_map.get(lb_id, [])
                for vip_ip in raw_vips:
                    if vip_ip in eip_map:
                        for e in eip_map[vip_ip]:
                            if e not in matched_eips:
                                matched_eips.append(e)

                if raw_vips and matched_eips:
                    vips = f"{', '.join(raw_vips)} / {', '.join(matched_eips)}"
                elif raw_vips:
                    vips = ", ".join(raw_vips)
                elif matched_eips:
                    vips = ", ".join(matched_eips)
                else:
                    vips = "-"

                dns = lb.LoadBalancerDomain or "-"
                status = _get_status_display(lb.Status if lb.Status is not None else 1)
                vpc_id = lb.VpcId or "-"
                charge_type = lb.ChargeType or "-"
                create_time = (lb.CreateTime or "-")[:10]

                # 1. Listener 및 HealthCheck 정보 수집
                hc_map = {}
                try:
                    req_l = models.DescribeListenersRequest()
                    req_l.LoadBalancerId = lb_id
                    resp_l = client.DescribeListeners(req_l)
                    for l in (resp_l.Listeners or []):
                        if l.Rules:
                            for r in l.Rules:
                                hc = r.HealthCheck
                                hc_path = (hc.HttpCheckPath if hc and getattr(hc, "HealthSwitch", 0) == 1 else None) or "-"
                                hc_map[(l.Protocol, l.Port, r.Domain or "", r.Url or "")] = hc_path
                        else:
                            # 4계층 리스너 (TCP, UDP 등)
                            hc = getattr(l, "HealthCheck", None)
                            if hc and getattr(hc, "HealthSwitch", 0) == 1:
                                path = getattr(hc, "HttpCheckPath", None)
                                hc_path = path if path else "-"
                            else:
                                hc_path = "-"
                            hc_map[(l.Protocol, l.Port, "", "")] = hc_path
                except Exception as e:
                    log_info_non_console(f"[CLB] DescribeListeners 실패 ({lb_id}): {e}")

                # 2. Target Health 정보 수집 (HealthStatus & Detail)
                health_map = {}
                try:
                    req_h = models.DescribeTargetHealthRequest()
                    req_h.LoadBalancerIds = [lb_id]
                    resp_h = client.DescribeTargetHealth(req_h)
                    for lb_h in (resp_h.LoadBalancers or []):
                        for l_h in (lb_h.Listeners or []):
                            proto = l_h.Protocol or ""
                            port = l_h.Port

                            # 7계층 및 4계층 (Tencent DescribeTargetHealth는 4계층도 Rules 내의 가상 Rule로 반환됨)
                            for r_h in (l_h.Rules or []):
                                domain_val = r_h.Domain or ""
                                url_val = r_h.Url or ""
                                for t_h in (r_h.Targets or []):
                                    val = (t_h.HealthStatus, t_h.HealthStatusDetail or "")
                                    health_map[(proto, port, domain_val, url_val, t_h.TargetId or "", t_h.Port)] = val
                                    if getattr(t_h, "IP", None):
                                        health_map[(proto, port, domain_val, url_val, t_h.IP, t_h.Port)] = val
                                    # 4계층 fallback (domain이나 url이 없는 경우 ("", "")으로도 매핑)
                                    if not domain_val and not url_val:
                                        health_map[(proto, port, "", "", t_h.TargetId or "", t_h.Port)] = val
                                        if getattr(t_h, "IP", None):
                                            health_map[(proto, port, "", "", t_h.IP, t_h.Port)] = val

                            # Listener에 직접 Targets가 있는 경우 대비
                            for t_h in (getattr(l_h, "Targets", None) or []):
                                val = (t_h.HealthStatus, t_h.HealthStatusDetail or "")
                                health_map[(proto, port, "", "", t_h.TargetId or "", t_h.Port)] = val
                                if getattr(t_h, "IP", None):
                                    health_map[(proto, port, "", "", t_h.IP, t_h.Port)] = val
                except Exception as e:
                    log_info_non_console(f"[CLB] DescribeTargetHealth 실패 ({lb_id}): {e}")

                # 3. Targets 상세 정보 수집
                try:
                    req_t = models.DescribeTargetsRequest()
                    req_t.LoadBalancerId = lb_id
                    resp_t = client.DescribeTargets(req_t)
                    listeners_t = resp_t.Listeners or []

                    if not listeners_t:
                        rows.append({
                            "account": account_name, "region": region, "lb_name": lb_name, "lb_id": lb_id,
                            "type": lb_type, "vips": vips, "dns": dns, "status": status, "vpc_id": vpc_id,
                            "listener": "(No Listeners)", "domain_url": "-", "hc_path": "-",
                            "targets": "-", "target_health": "-", "charge_type": charge_type, "create_time": create_time,
                        })
                        continue

                    for l_t in listeners_t:
                        listener_str = f"{l_t.Protocol}:{l_t.Port}"
                        rules_t = l_t.Rules or []

                        def _create_target_row(target, domain_url, hc_path, domain_key, url_key):
                            inst_name = target.InstanceName or target.InstanceId or "-"
                            ip = target.PrivateIpAddresses[0] if target.PrivateIpAddresses else "-"
                            target_port = target.Port
                            target_str = f"{inst_name} ({ip}:{target_port})"

                            h_key1 = (l_t.Protocol, l_t.Port, domain_key, url_key, target.InstanceId or "", target_port)
                            h_key2 = (l_t.Protocol, l_t.Port, domain_key, url_key, ip, target_port)
                            h_status, h_detail = health_map.get(h_key1) or health_map.get(h_key2) or (None, "")

                            if h_status is True:
                                target_health = "[bold green]Healthy[/bold green]"
                            elif h_status is False:
                                detail_str = f" ({h_detail})" if h_detail else ""
                                target_health = f"[bold red]Unhealthy{detail_str}[/bold red]"
                            else:
                                target_health = "-"

                            return {
                                "account": account_name, "region": region, "lb_name": lb_name, "lb_id": lb_id,
                                "type": lb_type, "vips": vips, "dns": dns, "status": status, "vpc_id": vpc_id,
                                "listener": listener_str, "domain_url": domain_url, "hc_path": hc_path,
                                "targets": target_str, "target_health": target_health,
                                "charge_type": charge_type, "create_time": create_time,
                            }

                        if rules_t:
                            # 7계층 리스너 (HTTP, HTTPS 등)
                            for r_t in rules_t:
                                domain_val = r_t.Domain or "*"
                                url_val = r_t.Url or "/"
                                domain_url = f"{domain_val}{url_val}" if domain_val != "*" or url_val != "/" else "*"
                                hc_path = hc_map.get((l_t.Protocol, l_t.Port, r_t.Domain or "", r_t.Url or ""), "-")

                                targets_t = r_t.Targets or []
                                if not targets_t:
                                    rows.append({
                                        "account": account_name, "region": region, "lb_name": lb_name, "lb_id": lb_id,
                                        "type": lb_type, "vips": vips, "dns": dns, "status": status, "vpc_id": vpc_id,
                                        "listener": listener_str, "domain_url": domain_url, "hc_path": hc_path,
                                        "targets": "(No Targets)", "target_health": "-", "charge_type": charge_type, "create_time": create_time,
                                    })
                                    continue

                                for target in targets_t:
                                    rows.append(_create_target_row(target, domain_url, hc_path, r_t.Domain or "", r_t.Url or ""))
                        else:
                            # 4계층 리스너 (TCP, UDP, TCP_SSL 등)
                            domain_url = "-"
                            hc_path = hc_map.get((l_t.Protocol, l_t.Port, "", ""), "-")
                            targets_t = l_t.Targets or []

                            if not targets_t:
                                rows.append({
                                    "account": account_name, "region": region, "lb_name": lb_name, "lb_id": lb_id,
                                    "type": lb_type, "vips": vips, "dns": dns, "status": status, "vpc_id": vpc_id,
                                    "listener": listener_str, "domain_url": domain_url, "hc_path": hc_path,
                                    "targets": "(No Targets)", "target_health": "-", "charge_type": charge_type, "create_time": create_time,
                                })
                                continue

                            for target in targets_t:
                                rows.append(_create_target_row(target, domain_url, hc_path, "", ""))

                except Exception as e:
                    log_info_non_console(f"[CLB] DescribeTargets 실패 ({lb_id}): {e}")
                    rows.append({
                        "account": account_name, "region": region, "lb_name": lb_name, "lb_id": lb_id,
                        "type": lb_type, "vips": vips, "dns": dns, "status": status, "vpc_id": vpc_id,
                        "listener": "-", "domain_url": "-", "hc_path": "-",
                        "targets": "-", "target_health": "-", "charge_type": charge_type, "create_time": create_time,
                    })

            offset += len(lbs)
            if offset >= (resp.TotalCount or 0) or len(lbs) < limit:
                break

    except TencentCloudSDKException as e:
        log_info_non_console(f"[CLB] 수집 실패: {account_name}/{region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ CLB 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[CLB] 수집 실패: {account_name}/{region}: {e}")
        return []

    log_info_non_console(f"[CLB] {len(rows)}개 수집 완료: account={account_name}, region={region}")
    return rows


def print_clb_table(all_rows: List[Dict[str, Any]], verbose: bool) -> None:
    if not all_rows:
        console.print("[yellow]표시할 CLB 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["lb_name"], x["listener"], x["domain_url"], x["targets"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")

    if verbose:
        headers = ["Account", "Region", "LB Name", "LB ID", "Type", "Status", "VIP(s)", "DNS", "Listener", "Domain/Url", "Health Path", "Target (Instance / IP:Port)", "Target Health", "VPC", "Charge", "Created"]
        keys    = ["account", "region", "lb_name", "lb_id", "type", "status", "vips",   "dns", "listener", "domain_url", "hc_path",    "targets",                       "target_health", "vpc_id", "charge_type", "create_time"]
    else:
        headers = ["Account", "Region", "LB Name", "Type", "Status", "VIP(s)", "Listener", "Domain/Url", "Health Path", "Target (Instance / IP:Port)", "Target Health"]
        keys    = ["account", "region", "lb_name", "type", "status", "vips",   "listener", "domain_url", "hc_path",    "targets",                       "target_health"]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
        elif h == "Status":
            table.add_column(h, justify="center")
        elif h == "Target Health":
            table.add_column(h, justify="center")
        else:
            table.add_column(h)

    last_account = None
    last_region = None
    last_lb = None
    last_listener = None

    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed  = row["region"] != last_region
        lb_changed      = row["lb_name"] != last_lb or account_changed or region_changed
        listener_changed = row["listener"] != last_listener or lb_changed

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            elif lb_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])
            elif listener_changed:
                table.add_row("", "", "", "", "", "", *[Rule(style="dim") for _ in headers[6:]])

        display = []
        display.append(row["account"] if account_changed else "")
        display.append(row["region"] if (account_changed or region_changed) else "")
        display.append(row["lb_name"] if lb_changed else "")
        
        # verbose 인지에 따른 인덱스 오프셋 처리
        if verbose:
            display.append(row["lb_id"] if lb_changed else "")
            display.append(row["type"] if lb_changed else "")
            display.append(row["status"] if lb_changed else "")
            display.append(row["vips"] if lb_changed else "")
            display.append(row["dns"] if lb_changed else "")
            display.append(row["listener"] if listener_changed else "")
            display.append(row["domain_url"] if listener_changed else "")
            display.append(row["hc_path"] if listener_changed else "")
            display.append(row["targets"])
            display.append(row["target_health"])
            display.append(row["vpc_id"] if lb_changed else "")
            display.append(row["charge_type"] if lb_changed else "")
            display.append(row["create_time"] if lb_changed else "")
        else:
            display.append(row["type"] if lb_changed else "")
            display.append(row["status"] if lb_changed else "")
            display.append(row["vips"] if lb_changed else "")
            display.append(row["listener"] if listener_changed else "")
            display.append(row["domain_url"] if listener_changed else "")
            display.append(row["hc_path"] if listener_changed else "")
            display.append(row["targets"])
            display.append(row["target_health"])

        table.add_row(*display)

        last_account  = row["account"]
        last_region   = row["region"]
        last_lb       = row["lb_name"]
        last_listener = row["listener"]

    console.print(table)


def main(args) -> None:
    if not check_sdk_available():
        console.print("[red]❌ tencentcloud-sdk-python 이 설치되지 않았습니다.[/red]")
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

    with ManualProgress("Collecting CLB instances across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_clb_one_account_region, account, region, name_filter)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    progress.update(f"Processed {acct_name}/{region} - Found {len(result)} LBs", advance=1)
                except Exception as e:
                    log_info_non_console(f"[CLB] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    print_clb_table(all_rows, verbose)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
    parser.add_argument("-n", "--name", help="CLB 이름/ID 필터 (콤마(,)로 복수 검색 가능, 예: web,api)")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 정보 출력 (LB ID, DNS, VPC, 과금 방식 등)")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent CLB 상세 정보 (병렬 수집)")
    add_arguments(p)
    main(p.parse_args())
