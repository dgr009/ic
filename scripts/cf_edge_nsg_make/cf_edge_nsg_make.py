#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Edge 80/443 방화벽(NSG) 생성 스크립트
------------------------------------------------
- Cloudflare IP 목록을 실시간으로 가져와 OCI NSG 인바운드 규칙(80/443) 생성
- 재실행 시 중복 룰을 자동으로 건너뛰어 **idempotent** 동작
- 모든 파라미터는 환경변수로 주입 (.env 지원)
"""

import os
import sys
import signal
from typing import List, Dict
from oci.core.models import (
    AddSecurityRuleDetails,
    AddNetworkSecurityGroupSecurityRulesDetails,
    PortRange,
    TcpOptions,
)
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from rich.logging import RichHandler
import logging
import oci

# ------------------------------------------------------------------------------
# 0. 공통 설정 (로그 · 콘솔)
# ------------------------------------------------------------------------------
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False, show_time=False)],
)
log = logging.getLogger("cf_edge_nsg")

# graceful Ctrl-C
signal.signal(signal.SIGINT, lambda sig, frame: sys.exit("\n[!] 작업이 취소되었습니다"))

# ------------------------------------------------------------------------------
# 1. 환경변수 로드
# ------------------------------------------------------------------------------
load_dotenv(override=True)

PROFILE          = os.getenv("OCI_PROFILE",       "DEFAULT")
REGION           = os.getenv("OCI_REGION")                   # 선택
COMPARTMENT_OCID = os.getenv("COMPARTMENT_OCID")
VCN_OCID         = os.getenv("VCN_OCID")
NSG_NAME         = os.getenv("NSG_NAME",          "cf-edge-web")
NSG_DISPLAY_NAME = os.getenv("NSG_DISPLAY_NAME",  "Cloudflare Edge Web NSG")
TCP_STATELESS    = os.getenv("TCP_STATELESS",     "false").lower() == "true"

REQUIRED_VARS = ["COMPARTMENT_OCID", "VCN_OCID"]

missing = [v for v in REQUIRED_VARS if globals()[v] in (None, "", "undefined")]
if missing:
    log.error(f"필수 환경변수 부족: {', '.join(missing)}")
    sys.exit(1)

# ------------------------------------------------------------------------------
# 2. OCI 클라이언트 초기화
# ------------------------------------------------------------------------------
try:
    if REGION:
        config = oci.config.from_file(profile_name=PROFILE)
        config["region"] = REGION
    else:
        config = oci.config.from_file(profile_name=PROFILE)
    vcn_client = oci.core.VirtualNetworkClient(config)
    identity_client = oci.identity.IdentityClient(config)
except Exception as e:
    log.exception("OCI 설정 로드 실패")
    sys.exit(1)

# ------------------------------------------------------------------------------
# 3. Cloudflare IP 목록 가져오기
# ------------------------------------------------------------------------------
CF_IP_URLS = {
    "ipv4": "https://www.cloudflare.com/ips-v4",
    "ipv6": "https://www.cloudflare.com/ips-v6",
}

def fetch_cf_ips() -> Dict[str, List[str]]:
    ip_dict: Dict[str, List[str]] = {}
    for ip_type, url in CF_IP_URLS.items():
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        cidrs = [l.strip() for l in resp.text.splitlines() if l.strip()]
        ip_dict[ip_type] = cidrs
        log.info(f"[Cloudflare] {ip_type.upper()} CIDR {len(cidrs)}개 수집 완료")
    return ip_dict

# ------------------------------------------------------------------------------
# 4. NSG 존재여부 확인 · 생성
# ------------------------------------------------------------------------------
def get_or_create_nsg() -> str:
    """이름 기준 NSG 조회·생성 후 OCID 반환"""
    existing = vcn_client.list_network_security_groups(
        compartment_id=COMPARTMENT_OCID,
        vcn_id=VCN_OCID,
        display_name=NSG_DISPLAY_NAME,
    ).data
    if existing:
        nsg = existing[0]
        log.info(f"기존 NSG 재사용: {nsg.id}")
        return nsg.id

    log.info("NSG가 없어 새로 만듭니다…")
    details = oci.core.models.CreateNetworkSecurityGroupDetails(
        compartment_id=COMPARTMENT_OCID,
        vcn_id=VCN_OCID,
        display_name=NSG_DISPLAY_NAME,
        defined_tags={},
        freeform_tags={"CreatedBy": "cf_edge_nsg_script"},
    )
    nsg = vcn_client.create_network_security_group(details).data
    oci.wait_until(vcn_client, vcn_client.get_network_security_group(nsg.id), "lifecycle_state", "AVAILABLE")
    console.print(f"[green]✅ NSG 생성 완료: {nsg.display_name} ({nsg.id})[/green]")
    return nsg.id

# ------------------------------------------------------------------------------
# 5. 보안 규칙 빌드
# ------------------------------------------------------------------------------
def build_rule_details(cidr: str, port: int) -> AddSecurityRuleDetails:
    return AddSecurityRuleDetails(
        direction="INGRESS",          # INGRESS / EGRESS
        protocol="6",                 # 6 = TCP, 17 = UDP, 1 = ICMP
        source=cidr,
        source_type="CIDR_BLOCK",     # 또는 "NETWORK_SECURITY_GROUP" 등
        description=f"CF edge {cidr}:{port}",
        is_stateless=False,
        tcp_options=TcpOptions(
            destination_port_range=PortRange(min=port, max=port)
        ),
    )

# ------------------------------------------------------------------------------
# 6. 규칙 중복 체크 & 추가
# ------------------------------------------------------------------------------
from itertools import islice

MAX_RULES_PER_CALL = 25   # OCI 제약


def vcn_supports_ipv6(vcn_id: str) -> bool:
    vcn = vcn_client.get_vcn(vcn_id).data
    # SDK 2.144↑ : ipv6_cidr_blocks / 2.143↓ : ipv6cidr_block
    return bool(getattr(vcn, "ipv6_cidr_blocks", None) or getattr(vcn, "ipv6cidr_block", None))

VCN_HAS_IPV6 = vcn_supports_ipv6(VCN_OCID)
if not VCN_HAS_IPV6:
    console.print("[yellow]⚠️  VCN이 IPv6 미지원 상태입니다 → IPv6 규칙을 건너뜁니다.[/yellow]")

def chunked(iterable, size):
    it = iter(iterable)
    while (chunk := list(islice(it, size))):
        yield chunk

def sync_rules(nsg_id: str, cf_ip_dict: dict):
    """
    cf_ip_dict = {"ipv4": [...], "ipv6": [...]}
    Cloudflare 전체 CIDR × (80, 443) 규칙을 동기화
    """
    merged_cidrs = cf_ip_dict["ipv4"] + (cf_ip_dict["ipv6"] if VCN_HAS_IPV6 else [])
    new_rules: list[AddSecurityRuleDetails] = []

    # ① 이미 존재하는 규칙 키 세트
    existing = vcn_client.list_network_security_group_security_rules(
        network_security_group_id=nsg_id
    ).data
    existing_keys = {
        (r.source, r.tcp_options.destination_port_range.min)
        for r in existing if r.direction == "INGRESS"
    }

    # ② 신규 규칙 빌드
    for cidr in merged_cidrs:
        for port in (80, 443):
            if (cidr, port) not in existing_keys:
                new_rules.append(build_rule_details(cidr, port))

    if not new_rules:
        console.print("[yellow]모든 Cloudflare 룰이 이미 존재합니다.[/yellow]")
        return

    # ③ 25개씩 나누어 호출
    added = 0
    for rules_chunk in chunked(new_rules, MAX_RULES_PER_CALL):
        add_details = AddNetworkSecurityGroupSecurityRulesDetails(
            security_rules=rules_chunk
        )
        vcn_client.add_network_security_group_security_rules(
            network_security_group_id=nsg_id,
            add_network_security_group_security_rules_details=add_details,
        )
        added += len(rules_chunk)

    console.print(f"[green]🎉 신규 룰 {added}개 추가 완료[/green]")


# ------------------------------------------------------------------------------
# 7. 출력 함수
# ------------------------------------------------------------------------------
def show_summary(cf_ip_dict: Dict[str, List[str]], nsg_id: str):
    table = Table(title="Cloudflare Edge NSG Summary", show_lines=True)
    table.add_column("항목")
    table.add_column("값", overflow="fold")
    table.add_row("NSG OCID", nsg_id)
    table.add_row("Cloudflare IPv4 CIDR 수", str(len(cf_ip_dict['ipv4'])))
    table.add_row("Cloudflare IPv6 CIDR 수", str(len(cf_ip_dict['ipv6'])))
    table.add_row("포트", "80, 443")
    table.add_row("Stateless", str(TCP_STATELESS))
    console.print(table)

# ------------------------------------------------------------------------------
# 8. 메인
# ------------------------------------------------------------------------------
def main():
    console.rule("[bold blue]Cloudflare Edge NSG 생성기", style="blue")
    cf_ip_dict = fetch_cf_ips()
    nsg_id = get_or_create_nsg()
    show_summary(cf_ip_dict, nsg_id)

    if not Confirm.ask("[cyan]위 정보로 규칙을 적용하시겠습니까?[/cyan]", default=True):
        console.print("[red]작업이 취소되었습니다.[/red]")
        return

    sync_rules(nsg_id, cf_ip_dict)
    console.print("\n[bold green]작업이 완료되었습니다.[/bold green]")

if __name__ == "__main__":
    main()

