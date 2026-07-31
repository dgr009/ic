#!/usr/bin/env python3
"""
Security Group 정보 조회 (트리/테이블 출력)

AWS SG info 에 대응. Ingress/Egress 룰을 tree 또는 table 형식으로 출력.

Usage:
    ic tencent sg info
    ic tencent sg info -o tree
    ic tencent sg info -n "my-sg"
    ic tencent sg info --ingress
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.rule import Rule
from rich import box

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


def _parse_policy(policy: Any, direction: str) -> Dict[str, str]:
    """SecurityGroupPolicy 객체를 dict 로 변환합니다."""
    proto = policy.Protocol or "ALL"
    if proto.upper() == "ALL":
        port_range = "ALL"
    else:
        port_range = policy.Port or "-"

    # 소스/대상
    if policy.CidrBlock:
        target = policy.CidrBlock
    elif policy.Ipv6CidrBlock:
        target = policy.Ipv6CidrBlock
    elif policy.SecurityGroupId:
        target = f"sg:{policy.SecurityGroupId}"
    elif policy.AddressTemplate:
        target = f"template:{policy.AddressTemplate.AddressId or ''}"
    else:
        target = "-"

    action = policy.Action or "-"
    action_style = "[bold green]ACCEPT[/bold green]" if action.upper() == "ACCEPT" else "[bold red]DROP[/bold red]"

    return {
        "direction":  direction,
        "proto":      proto.upper(),
        "port_range": port_range,
        "target":     target,
        "action":     action_style,
        "desc":       policy.PolicyDescription or "-",
    }


def fetch_sg_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str],
    rule_type: str = "all"
) -> List[Dict[str, Any]]:
    account_name = account.get("name", account.get("id", "unknown"))
    log_info_non_console(f"[SG] 수집 시작: account={account_name}, region={region}")

    if not TENCENT_SDK_AVAILABLE:
        return []

    try:
        from tencentcloud.vpc.v20170312 import vpc_client, models
    except ImportError:
        return []

    cred = get_credential_for_account(account)
    if not cred:
        return []

    results = []
    try:
        client = vpc_client.VpcClient(cred, region, make_client_profile())

        offset = 0
        limit  = 100
        while True:
            req = models.DescribeSecurityGroupsRequest()
            req.Offset = str(offset)
            req.Limit  = str(limit)
            if name_filter:
                f = models.Filter()
                f.Name = "security-group-name"
                f.Values = [f"*{name_filter}*"]
                req.Filters = [f]

            resp = client.DescribeSecurityGroups(req)
            sgs  = resp.SecurityGroupSet or []

            for sg in sgs:
                sg_id   = sg.SecurityGroupId or "-"
                sg_name = sg.SecurityGroupName or sg_id

                # 룰 조회
                try:
                    req2 = models.DescribeSecurityGroupPoliciesRequest()
                    req2.SecurityGroupId = sg_id
                    resp2 = client.DescribeSecurityGroupPolicies(req2)
                    policy_set = resp2.SecurityGroupPolicySet

                    if rule_type in ("all", "ingress") and policy_set and policy_set.Ingress:
                        for p in policy_set.Ingress:
                            r = _parse_policy(p, "Ingress")
                            r.update({"account_id": account_name, "region": region, "sg_name": sg_name, "sg_id": sg_id})
                            results.append(r)

                    if rule_type in ("all", "egress") and policy_set and policy_set.Egress:
                        for p in policy_set.Egress:
                            r = _parse_policy(p, "Egress")
                            r.update({"account_id": account_name, "region": region, "sg_name": sg_name, "sg_id": sg_id})
                            results.append(r)

                    if not results or (results and results[-1].get("sg_id") != sg_id):
                        # 룰이 없는 SG 표시
                        if rule_type in ("all", "ingress"):
                            results.append({"account_id": account_name, "region": region, "sg_name": sg_name, "sg_id": sg_id,
                                            "direction": "Ingress", "proto": "-", "port_range": "-", "target": "-",
                                            "action": "-", "desc": "(No Ingress Rules)"})
                except Exception as e:
                    log_info_non_console(f"[SG] 룰 조회 실패: {sg_id}: {e}")

            offset += len(sgs)
            if offset >= (resp.TotalCount or 0) or len(sgs) < limit:
                break

    except TencentCloudSDKException as e:
        log_info_non_console(f"[SG] 수집 실패: {account_name}/{region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ SG 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[SG] 수집 실패: {account_name}/{region}: {e}")

    return results


def print_sg_table(sg_rows: List[Dict[str, Any]]) -> None:
    if not sg_rows:
        console.print("[yellow](No Security Groups)[/yellow]")
        return

    sg_rows.sort(key=lambda x: (
        x["account_id"], x["region"], x["sg_name"],
        0 if x["direction"] == "Ingress" else 1
    ))

    table = Table(show_lines=False, box=box.HORIZONTALS)
    headers = ["Account", "Region", "SG Name", "Type", "Proto", "Port Range", "Source/Dest", "Action", "Desc"]
    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h in ("Region", "SG Name"):
            table.add_column(h, style="bold cyan")
        else:
            table.add_column(h)

    last_account = last_region = last_sg = None

    for row in sg_rows:
        account_display = row["account_id"] if row["account_id"] != last_account else ""
        if account_display and last_account is not None:
            table.add_row(*[Rule(style="dim") for _ in headers])
        if account_display:
            last_account = row["account_id"]
            last_region  = None
            last_sg      = None

        region_display = row["region"] if row["region"] != last_region else ""
        if region_display and last_region is not None:
            table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
        if region_display:
            last_region = row["region"]
            last_sg     = None

        sg_display = row["sg_name"] if row["sg_name"] != last_sg else ""
        if sg_display and last_sg is not None:
            table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])
        if sg_display:
            last_sg = row["sg_name"]

        dir_style = "[green]Ingress[/green]" if row["direction"] == "Ingress" else "[cyan]Egress[/cyan]"

        table.add_row(
            account_display, region_display, sg_display,
            dir_style, row["proto"], row["port_range"],
            row["target"], row["action"], row["desc"]
        )

    console.print(table)


def print_sg_tree(sg_rows: List[Dict[str, Any]]) -> None:
    if not sg_rows:
        console.print("[yellow](No Security Groups)[/yellow]")
        return

    # 계층 구조로 그룹화
    grouped: Dict = {}
    for row in sg_rows:
        grouped\
            .setdefault(row["account_id"], {})\
            .setdefault(row["region"], {})\
            .setdefault(row["sg_name"], [])\
            .append(row)

    tree = Tree("Tencent Account", guide_style="bold cyan")
    for account_id, regions in sorted(grouped.items()):
        ab = tree.add(f"[magenta bold]{account_id}[/magenta bold]")
        for region_name, sgs in sorted(regions.items()):
            rb = ab.add(f"[cyan]{region_name}[/cyan]")
            for sg_name, rules in sorted(sgs.items()):
                sb = rb.add(f"[bold white]{sg_name}[/bold white]")
                for rule in rules:
                    dir_tag = "[green]Ingress[/green]" if rule["direction"] == "Ingress" else "[cyan]Egress[/cyan]"
                    arrow   = "←" if rule["direction"] == "Ingress" else "→"
                    sb.add(f"[{dir_tag}] [{rule['proto']:<4}] {rule['port_range']:<11} {arrow} [yellow]{rule['target']}[/yellow]  {rule['action']}")

    console.print(tree)


def main(args) -> None:
    if not check_sdk_available():
        console.print("[red]❌ tencentcloud-sdk-python 이 설치되지 않았습니다.[/red]")
        sys.exit(1)

    accounts = get_accounts(getattr(args, "account", None))
    regions  = get_tencent_regions(getattr(args, "regions", None))

    rule_type = getattr(args, "rule_type", "all")
    if getattr(args, "ingress", False):
        rule_type = "ingress"
    elif getattr(args, "egress", False):
        rule_type = "egress"

    name_filter = getattr(args, "name", None)
    output_fmt  = getattr(args, "output", "table")
    total_ops   = len(accounts) * len(regions)
    all_rows: List[Dict[str, Any]] = []

    with ManualProgress("Collecting Security Group information across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_sg_one_account_region, account, region, name_filter, rule_type)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    sg_count = len(set(r["sg_name"] for r in result))
                    progress.update(f"Processed {acct_name}/{region} - Found {sg_count} SGs", advance=1)
                except Exception as e:
                    log_info_non_console(f"[SG] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    if output_fmt == "tree":
        print_sg_tree(all_rows)
    else:
        print_sg_table(all_rows)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account",   help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions",   help="리전 목록(,)")
    parser.add_argument("-n", "--name",      help="SG 이름 필터")
    parser.add_argument("-o", "--output",    default="table", choices=["table", "tree"], help="출력 형식 (기본: table)")
    parser.add_argument("-t", "--rule-type", default="all",   choices=["all", "ingress", "egress"], help="룰 타입")
    parser.add_argument("-i", "--ingress",   action="store_true", help="Ingress 룰만")
    parser.add_argument("-e", "--egress",    action="store_true", help="Egress 룰만")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent Security Group 정보 (병렬 수집)")
    add_arguments(p)
    main(p.parse_args())
