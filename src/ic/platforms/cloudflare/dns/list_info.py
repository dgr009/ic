#!/usr/bin/env python3
"""
Cloudflare DNS 조회 스크립트

기존 dns_info.py를 공통 log/utils 모듈에 맞춰 수정했습니다.
- add_arguments(parser) : CLI 인자 정의
- main(args) : 실제 DNS 조회 로직
- Cloudflare API : /accounts → /zones → /dns_records
"""
import os
import argparse
import requests
from datetime import datetime
from ic.config.manager import ConfigManager
from rich.table import Table
from rich import box

# 공통 모듈
from common.log import log_error, console
from common.progress_decorator import progress_bar, ManualProgress

# Initialize config manager
_config_manager = ConfigManager()
_config = _config_manager.load_all_configs()
_cf_config = _config.get('cloudflare', {})

API_ENDPOINT = "https://api.cloudflare.com/client/v4"

# CloudFlare API 인증 정보 읽기
CF_EMAIL = _cf_config.get('email')
CF_TOKEN = _cf_config.get('api_token')

headers = {
    "X-Auth-Email": CF_EMAIL,
    "Authorization": f"Bearer {CF_TOKEN}",
    "Content-Type": "application/json",
}

def add_arguments(parser: argparse.ArgumentParser):
    """
    CLI에서 사용할 인자를 정의합니다.
    -a, --account : 특정 Account만 조회(부분 일치)
    -z, --zone    : 특정 Zone만 조회(부분 일치)
    """
    parser.add_argument("-a", "--account",  help="Filter accounts by name (case-insensitive substring)")
    parser.add_argument("-z", "--zone",  help="Filter zones by name (case-insensitive substring)")

@progress_bar("Fetching CloudFlare accounts")
def get_accounts():
    """
    Cloudflare /accounts 엔드포인트를 통해 계정 목록을 가져옵니다.
    """
    url = f"{API_ENDPOINT}/accounts"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json().get("result", [])
    log_error(f"Failed to fetch accounts: {response.text}")
    return []

@progress_bar("Fetching zones for account")
def get_zones(account_id):
    """
    특정 Account에 대한 Zone 목록을 가져옵니다.
    """
    url = f"{API_ENDPOINT}/zones?account.id={account_id}&per_page=100"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json().get("result", [])
    log_error(f"Failed to fetch zones for account {account_id}: {response.text}")
    return []

@progress_bar("Fetching DNS records for zone")
def get_dns_records(zone_id):
    """
    특정 Zone에 대한 DNS 레코드 목록을 가져옵니다.
    """
    url = f"{API_ENDPOINT}/zones/{zone_id}/dns_records?per_page=100"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json().get("result", [])
    log_error(f"Failed to fetch DNS records for zone {zone_id}: {response.text}")
    return []

def type_color(record_type: str) -> str:
    """
    레코드 타입(A, CNAME 등)에 따라 컬러 태그 반환
    """
    colors = {
        "A": "cyan",
        "CNAME": "green",
        "MX": "yellow",
        "TXT": "magenta",
        "AAAA": "blue",
        "NS": "bright_black",
        "SRV": "bright_magenta",
    }
    return colors.get(record_type, "white")

def proxy_color(proxied: bool) -> str:
    """
    proxied 여부에 따른 컬러 태그 반환
    """
    return "bright_green" if proxied else "bright_red"

def simplify_name(name: str, zone_name: str) -> str:
    """
    DNS 레코드의 name이 zone_name과 동일하거나 zone_name으로 끝나면
    zone_name 부분을 생략하여 간략화
    """
    if name == zone_name:
        return name
    if name.endswith(f".{zone_name}"):
        return name.replace(f".{zone_name}", "")
    return name

def format_time(time_str: str) -> str:
    """
    2023-12-31T12:34:56.789Z 같은 문자열을
    YYYY-MM-DD HH:MM 형태로 변환
    """
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return time_str

def display_dns_table(account_name, zone_name, records):
    """
    하나의 Zone에 대한 DNS 레코드들을 Rich Table로 출력
    """
    table = Table(
        title=f"[bold blue]{account_name}[/bold blue] - [bold yellow]{zone_name}[/bold yellow]",
        show_lines=True,
        box=box.HORIZONTALS,
        title_justify="left"
    )
    columns = ["Type", "Name", "Content", "Priority", "Proxy", "TTL", "Created", "Modified", "Comment"]
    for col in columns:
        table.add_column(col, style="white")

    for record in records:
        rtype = record.get("type", "")
        proxied = record.get("proxied", False)
        priority = record.get("priority", "-")
        comment = record.get("comment", "")

        table.add_row(
            f"[{type_color(rtype)}]{rtype}[/{type_color(rtype)}]",
            f"{simplify_name(record.get('name',''), zone_name)}",
            f"[blue]{record.get('content','')}[/blue]",
            str(priority),
            f"[{proxy_color(proxied)}]{proxied}[/{proxy_color(proxied)}]",
            str(record.get("ttl", "")),
            f"[bright_black]{format_time(record.get('created_on',''))}[/bright_black]",
            f"[bright_black]{format_time(record.get('modified_on',''))}[/bright_black]",
            comment
        )

    console.print(table)
    console.print("")  # 빈 줄

def info(args):
    """
    Cloudflare DNS 목록 조회 메인 진입점
    --account / --zone 인자를 기준으로 필터 적용
    """
    # 인증 정보 검사
    if not CF_EMAIL or not CF_TOKEN:
        log_error("CloudFlare 인증 정보가 설정되지 않았습니다. .ic/config/secrets.yaml 또는 config/secrets.yaml을 확인하세요.")
        return

    env_accounts = []
    accounts_config = _cf_config.get('cloudflare_accounts')
    if accounts_config:
        if isinstance(accounts_config, list):
            env_accounts = [a.strip().lower() for a in accounts_config if a.strip()]
        else:
            env_accounts = [a.strip().lower() for a in accounts_config.split(",") if a.strip()]

    env_zones = []
    zones_config = _cf_config.get('cloudflare_zones')
    if zones_config:
        if isinstance(zones_config, list):
            env_zones = [z.strip().lower() for z in zones_config if z.strip()]
        else:
            env_zones = [z.strip().lower() for z in zones_config.split(",") if z.strip()]

    with ManualProgress("Processing CloudFlare DNS information") as progress:
        # 1) 계정 목록 조회
        progress.set_description("Fetching CloudFlare accounts")
        accounts = get_accounts()
        if not accounts:
            console.print("[bold red]No Cloudflare accounts found.[/bold red]")
            return

        # 2) 설정 & CLI 인자를 통해 Filter 수행
        if args.account:
            # 사용자가 직접 --account 옵션 입력 => 단일 string
            # 그걸 리스트화해서 일관되게 사용
            filter_account = [args.account.lower()]
        else:
            # 설정에서 가져온 리스트
            filter_account = env_accounts

        if args.zone:
            filter_zone = [args.zone.lower()]
        else:
            filter_zone = env_zones

        # Filter accounts first to get accurate count
        filtered_accounts = []
        for acct in accounts:
            account_name = acct.get("name", "")
            if filter_account:
                lower_acct_name = account_name.lower()
                if not any(fa in lower_acct_name for fa in filter_account):
                    continue
                filtered_accounts.append(acct)
            else:
                # No account filter configured, include all accounts
                filtered_accounts.append(acct)

        progress.set_description(f"Processing {len(filtered_accounts)} CloudFlare accounts")
        
        # 3) 계정별 Zone → DNS 레코드 수집 & 출력
        total_zones_processed = 0
        for acct_idx, acct in enumerate(filtered_accounts, 1):
            account_name = acct.get("name", "")
            account_id = acct.get("id", "")

            progress.set_description(f"Processing account {acct_idx}/{len(filtered_accounts)}: {account_name}")
            
            zones = get_zones(account_id)
            
            # Filter zones for this account
            filtered_zones = []
            for z in zones:
                zone_name = z.get("name", "")
                if filter_zone: 
                    lower_zone_name = zone_name.lower()
                    if not any(fz in lower_zone_name for fz in filter_zone):
                        continue
                    filtered_zones.append(z)
                else:
                    # No zone filter configured, include all zones
                    filtered_zones.append(z)
            
            # Process each zone
            for zone_idx, z in enumerate(filtered_zones, 1):
                zone_name = z.get("name", "")
                zone_id = z.get("id", "")
                
                progress.set_description(f"Processing zone {zone_idx}/{len(filtered_zones)} in {account_name}: {zone_name}")
                
                records = get_dns_records(zone_id)
                display_dns_table(account_name, zone_name, records)
                total_zones_processed += 1
        
        progress.set_description(f"Completed processing {total_zones_processed} zones from {len(filtered_accounts)} accounts")


if __name__ == "__main__":
    """
    단독 실행(로컬 테스트) 시 argparse 사용
    실제로는 cli.py에서 add_arguments/parser로 분기하는 구조
    """
    parser = argparse.ArgumentParser(description="Cloudflare DNS Info")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    info(parsed_args)
