#!/usr/bin/env python3
"""
CVM (Cloud Virtual Machine) 인스턴스 정보 조회

AWS EC2 info 에 대응하는 명령어.
멀티계정 + 멀티리전을 병렬로 수집하여 Rich 테이블로 출력합니다.

Usage:
    ic tencent cvm info
    ic tencent cvm info -r ap-seoul
    ic tencent cvm info -n "my-server"
    ic tencent cvm info -v
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

# CVM 인스턴스 상태 컬러링 (EC2 color_state 대응)
_STATE_COLORS = {
    "RUNNING":          "[bold green]{s}[/bold green]",
    "STOPPED":          "[bold yellow]{s}[/bold yellow]",
    "REBOOTING":        "[bold cyan]{s}[/bold cyan]",
    "PENDING":          "[bold cyan]{s}[/bold cyan]",
    "STOPPING":         "[bold magenta]{s}[/bold magenta]",
    "STARTING":         "[bold cyan]{s}[/bold cyan]",
    "SHUTDOWN":         "[bold red]{s}[/bold red]",
    "TERMINATING":      "[bold red]{s}[/bold red]",
    "TERMINATED":       "[bold red]{s}[/bold red]",
}

def color_state(state: str) -> str:
    template = _STATE_COLORS.get(state.upper())
    if template:
        return template.format(s=state)
    return state


def fetch_cvm_one_account_region(
    account: Dict[str, Any],
    region: str,
    name_filter: Optional[str]
) -> List[Dict[str, Any]]:
    """단일 계정 + 리전의 CVM 인스턴스 목록을 수집합니다."""
    account_id = account.get("id", "unknown")
    account_name = account.get("name", account_id)

    log_info_non_console(f"[CVM] 수집 시작: account={account_name}, region={region}")

    if not TENCENT_SDK_AVAILABLE:
        log_info_non_console("[CVM] tencentcloud SDK 미설치")
        return []

    try:
        from tencentcloud.cvm.v20170312 import cvm_client, models
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    except ImportError:
        log_info_non_console("[CVM] CVM SDK 모듈 import 실패")
        return []

    cred = get_credential_for_account(account)
    if not cred:
        log_info_non_console(f"[CVM] 자격증명 없음: account={account_name}")
        return []

    try:
        client = cvm_client.CvmClient(cred, region, make_client_profile())

        all_instances = []
        offset = 0
        limit = 100

        while True:
            req = models.DescribeInstancesRequest()
            req.Offset = offset
            req.Limit = limit

            resp = client.DescribeInstances(req)
            instances = resp.InstanceSet or []

            for inst in instances:
                # 상태가 TERMINATED 면 스킵
                state = inst.InstanceState or "UNKNOWN"
                if state.upper() == "TERMINATED":
                    continue

                inst_name = inst.InstanceName or inst.InstanceId or "-"

                if name_filter:
                    nf = name_filter.lower()
                    if nf not in inst_name.lower() and nf not in (inst.InstanceId or "").lower():
                        continue

                all_instances.append(inst)

            # 페이지네이션
            offset += len(instances)
            if offset >= (resp.TotalCount or 0) or len(instances) < limit:
                break

        if not all_instances:
            return []

        # VPC / Subnet / Security Group 이름 조회를 위한 ID 수집
        vpc_ids = set()
        subnet_ids = set()
        sg_ids = set()

        for inst in all_instances:
            if inst.VirtualPrivateCloud:
                v_id = getattr(inst.VirtualPrivateCloud, "VpcId", None)
                s_id = getattr(inst.VirtualPrivateCloud, "SubnetId", None)
                if v_id:
                    vpc_ids.add(v_id)
                if s_id:
                    subnet_ids.add(s_id)
            for sg in (inst.SecurityGroupIds or []):
                sg_id_str = sg if isinstance(sg, str) else getattr(sg, "SecurityGroupId", str(sg))
                if sg_id_str:
                    sg_ids.add(sg_id_str)

        vpc_map = {}
        subnet_map = {}
        sg_map = {}

        if vpc_ids or subnet_ids or sg_ids:
            try:
                from tencentcloud.vpc.v20170312 import vpc_client as tencent_vpc_client, models as vpc_models
                v_client = tencent_vpc_client.VpcClient(cred, region, make_client_profile())

                if vpc_ids:
                    try:
                        req_vpc = vpc_models.DescribeVpcsRequest()
                        req_vpc.VpcIds = list(vpc_ids)
                        req_vpc.Limit = str(len(vpc_ids))
                        resp_vpc = v_client.DescribeVpcs(req_vpc)
                        for v in (resp_vpc.VpcSet or []):
                            vpc_map[v.VpcId] = v.VpcName if v.VpcName else v.VpcId
                    except Exception as e:
                        log_info_non_console(f"[CVM] VPC 이름 조회 실패: {e}")

                if subnet_ids:
                    try:
                        req_sub = vpc_models.DescribeSubnetsRequest()
                        req_sub.SubnetIds = list(subnet_ids)
                        req_sub.Limit = str(len(subnet_ids))
                        resp_sub = v_client.DescribeSubnets(req_sub)
                        for s in (resp_sub.SubnetSet or []):
                            subnet_map[s.SubnetId] = s.SubnetName if s.SubnetName else s.SubnetId
                    except Exception as e:
                        log_info_non_console(f"[CVM] Subnet 이름 조회 실패: {e}")

                if sg_ids:
                    try:
                        req_sg = vpc_models.DescribeSecurityGroupsRequest()
                        req_sg.SecurityGroupIds = list(sg_ids)
                        req_sg.Limit = str(len(sg_ids))
                        resp_sg = v_client.DescribeSecurityGroups(req_sg)
                        for g in (resp_sg.SecurityGroupSet or []):
                            sg_map[g.SecurityGroupId] = g.SecurityGroupName if g.SecurityGroupName else g.SecurityGroupId
                    except Exception as e:
                        log_info_non_console(f"[CVM] SecurityGroup 이름 조회 실패: {e}")
            except Exception as e:
                log_info_non_console(f"[CVM] VPC 클라이언트 초기화 실패: {e}")

        rows = []
        for inst in all_instances:
            state = inst.InstanceState or "UNKNOWN"
            inst_name = inst.InstanceName or inst.InstanceId or "-"

            # 스펙 정보
            itype = inst.InstanceType or "-"
            cpu = str(inst.CPU) if inst.CPU is not None else "?"
            mem_gb = str(inst.Memory) if inst.Memory is not None else "?"

            # 디스크 크기
            disk_size = "-"
            if inst.SystemDisk:
                disk_size = str(inst.SystemDisk.DiskSize or 0)
                if inst.DataDisks:
                    extra = sum(d.DiskSize or 0 for d in inst.DataDisks)
                    disk_size = str((inst.SystemDisk.DiskSize or 0) + extra)

            # IP 주소
            private_ip = "-"
            if inst.PrivateIpAddresses:
                private_ip = inst.PrivateIpAddresses[0]

            public_ip = "-"
            if inst.PublicIpAddresses:
                public_ip = inst.PublicIpAddresses[0]

            # VPC / 서브넷 (이름 우선, 없으면 ID)
            raw_vpc_id = getattr(inst.VirtualPrivateCloud, "VpcId", None) if inst.VirtualPrivateCloud else None
            raw_subnet_id = getattr(inst.VirtualPrivateCloud, "SubnetId", None) if inst.VirtualPrivateCloud else None

            vpc_display = vpc_map.get(raw_vpc_id, raw_vpc_id) if raw_vpc_id else "-"
            subnet_display = subnet_map.get(raw_subnet_id, raw_subnet_id) if raw_subnet_id else "-"

            # Security Groups (이름 우선, 없으면 ID)
            sg_display_list = []
            for sg in (inst.SecurityGroupIds or []):
                sg_id_str = sg if isinstance(sg, str) else getattr(sg, "SecurityGroupId", str(sg))
                if sg_id_str:
                    sg_display_list.append(sg_map.get(sg_id_str, sg_id_str))
            sg_names = ", ".join(sg_display_list) or "-"

            rows.append({
                "account":      account_name,
                "region":       region,
                "name":         inst_name,
                "instance_id":  inst.InstanceId or "-",
                "state":        color_state(state),
                "private_ip":   private_ip,
                "public_ip":    public_ip,
                "itype":        itype,
                "vcpu":         cpu,
                "memory":       mem_gb,
                "disk":         disk_size,
                "vpc_id":       vpc_display,
                "subnet_id":    subnet_display,
                "sgs":          sg_names,
                "charge_type":  inst.InstanceChargeType or "-",
                "created_time": (inst.CreatedTime or "-")[:10],
            })

        log_info_non_console(f"[CVM] {len(rows)}개 수집 완료: account={account_name}, region={region}")
        return rows

    except TencentCloudSDKException as e:
        log_info_non_console(f"[CVM] 수집 실패: account={account_name}, region={region}: {e}")
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ CVM 조회 실패 ({account_name}/{region}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return []
    except Exception as e:
        log_info_non_console(f"[CVM] 수집 실패: account={account_name}, region={region}: {e}")
        return []


def print_cvm_table(all_rows: List[Dict[str, Any]], verbose: bool) -> None:
    """CVM 인스턴스를 Rich 테이블로 출력합니다."""
    if not all_rows:
        console.print("[yellow]표시할 CVM 인스턴스 정보가 없습니다.[/yellow]")
        return

    all_rows.sort(key=lambda x: (x["account"], x["region"], x["name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")

    if verbose:
        headers = [
            "Account", "Region", "Name", "Instance ID", "State",
            "Private IP", "Public IP", "Type", "vCPU", "Mem(GB)", "Disk(GB)",
            "VPC", "Subnet", "Security Groups", "Charge", "Created"
        ]
        keys = [
            "account", "region", "name", "instance_id", "state",
            "private_ip", "public_ip", "itype", "vcpu", "memory", "disk",
            "vpc_id", "subnet_id", "sgs", "charge_type", "created_time"
        ]
    else:
        headers = [
            "Account", "Region", "Name", "State",
            "Private IP", "Public IP", "Type", "vCPU", "Mem", "Disk"
        ]
        keys = [
            "account", "region", "name", "state",
            "private_ip", "public_ip", "itype", "vcpu", "memory", "disk"
        ]

    for h in headers:
        if h == "Account":
            table.add_column(h, style="bold magenta")
        elif h == "Region":
            table.add_column(h, style="bold cyan")
        elif h in ("vCPU", "Mem", "Mem(GB)", "Disk", "Disk(GB)"):
            table.add_column(h, justify="right")
        elif h == "State":
            table.add_column(h, justify="center")
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
            else:
                table.add_row("", "", *[Rule(style="dim") for _ in headers[2:]])

        display = []
        display.append(row["account"] if account_changed else "")
        display.append(row["region"] if (account_changed or region_changed) else "")
        for k in keys[2:]:
            display.append(str(row.get(k, "-")))

        table.add_row(*display)

        last_account = row["account"]
        last_region = row["region"]

    console.print(table)


def main(args) -> None:
    if not check_sdk_available():
        console.print("[red]❌ tencentcloud-sdk-python 이 설치되지 않았습니다.[/red]")
        console.print("[yellow]   pip install tencentcloud-sdk-python[/yellow]")
        sys.exit(1)

    accounts    = get_accounts(getattr(args, "account", None))
    if not accounts:
        console.print("[red]❌ Tencent 계정 설정이 없습니다.[/red]")
        console.print("[yellow]   환경변수 TENCENT_SECRET_ID / TENCENT_SECRET_KEY 또는")
        console.print("   ic config 의 tencent.accounts 를 설정하세요.[/yellow]")
        sys.exit(1)

    regions = get_tencent_regions(getattr(args, "regions", None))
    name_filter = getattr(args, "name", None)
    verbose = getattr(args, "verbose", False)

    total_ops = len(accounts) * len(regions)
    all_rows: List[Dict[str, Any]] = []

    with ManualProgress("Collecting CVM instances across accounts and regions", total=total_ops) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            for account in accounts:
                for region in regions:
                    f = executor.submit(fetch_cvm_one_account_region, account, region, name_filter)
                    futures[f] = (account.get("name", account.get("id")), region)

            for future in as_completed(futures):
                acct_name, region = futures[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    progress.update(
                        f"Processed {acct_name}/{region} - Found {len(result)} instances",
                        advance=1
                    )
                except Exception as e:
                    log_info_non_console(f"[CVM] Future 실패: {acct_name}/{region}: {e}")
                    progress.update(f"Failed {acct_name}/{region}", advance=1)

    print_cvm_table(all_rows, verbose)


def add_arguments(parser) -> None:
    parser.add_argument("-a", "--account", help="계정 이름 또는 ID 목록(,) (없으면 전체 계정 조회)")
    parser.add_argument("-r", "--regions", help="리전 목록(,) 예: ap-seoul,ap-tokyo")
    parser.add_argument("-n", "--name", help="인스턴스 이름 필터 (부분 일치)")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 정보 출력")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tencent CVM 인스턴스 정보 (병렬 수집)")
    add_arguments(p)
    main(p.parse_args())
