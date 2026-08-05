#!/usr/bin/env python3
"""
AWS Health Dashboard EC2 Reboot Maintenance Schedule Command
`ic aws healthdashboard reboot`

AWS Health API를 사용하여 EC2 인스턴스의 예정된 재부팅 유지보수 일정
("EC2 instance reboot maintenance scheduled")을 조회합니다.
"""

import sys
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import get_valid_accounts, get_profiles, DEFINED_REGIONS

console = Console()

# 대상 타겟 이벤트 코드 정의 (EC2 인스턴스 예정된 재부팅 유지보수)
TARGET_EVENT_CODES = [
    "AWS_EC2_INSTANCE_REBOOT_MAINTENANCE_SCHEDULED",
    "AWS_EC2_PERSISTENT_INSTANCE_REBOOT_SCHEDULED",
    "AWS_EC2_SCHEDULED_REBOOT"
]

TARGET_DESCRIPTION_KEYWORD = "ec2 instance reboot maintenance scheduled"

def format_datetime_short(dt):
    """datetime 객체를 YY-MM-DD HH:MM UTC 형태로 압축하여 표 가로폭을 최적화합니다."""
    if not dt:
        return "-"
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    try:
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(dt)

def get_instance_details(session, instance_id, region):
    """
    EC2 API를 호출하여 인스턴스의 Name 태그, 현재 상태(State), 실제 리전을 조회합니다.
    """
    if not instance_id or not instance_id.startswith("i-"):
        return "-", "unknown", region

    regions_to_try = [region] if region and region != "global" else DEFINED_REGIONS
    
    for reg in regions_to_try:
        try:
            ec2_client = session.client("ec2", region_name=reg)
            response = ec2_client.describe_instances(InstanceIds=[instance_id])
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    state = instance.get("State", {}).get("Name", "unknown")
                    name = "-"
                    for tag in instance.get("Tags", []):
                        if tag.get("Key") == "Name":
                            name = tag.get("Value", "-")
                            break
                    return name, state, reg
        except ClientError:
            continue
        except Exception as e:
            log_info_non_console(f"EC2 인스턴스 세부 정보 조회 오류 ({instance_id}/{reg}): {e}")
            continue

    return "-", "unknown", region

def parse_region_from_arn_or_event(event, entity):
    """이벤트 또는 엔티티 ARN에서 AWS Region 정보를 추출합니다."""
    event_region = event.get("region")
    if event_region and event_region != "global":
        return event_region

    entity_arn = entity.get("entityArn", "")
    if entity_arn and entity_arn.startswith("arn:aws:"):
        parts = entity_arn.split(":")
        if len(parts) >= 4 and parts[3]:
            return parts[3]

    return "global"

def fetch_reboot_events_for_account(account_id, profile_name, include_closed=False):
    """단일 계정에 대해 AWS Health API(us-east-1)를 사용하여 EC2 재부팅 유지보수 이벤트를 수집합니다."""
    log_info_non_console(f"AWS Health API 조회 시작: Account={account_id}, Profile={profile_name}")
    
    events_found = []
    error_message = None

    try:
        session = boto3.Session(profile_name=profile_name, region_name="us-east-1")
        health_client = session.client("health", region_name="us-east-1")

        status_codes = ["open", "upcoming"]
        if include_closed:
            status_codes.append("closed")

        filter_params = {
            "services": ["EC2"],
            "eventStatusCodes": status_codes
        }

        paginator = health_client.get_paginator("describe_events")
        raw_events = []
        for page in paginator.paginate(filter=filter_params):
            for event in page.get("events", []):
                raw_events.append(event)

        if not raw_events:
            return account_id, profile_name, [], None

        for event in raw_events:
            event_arn = event.get("arn")
            event_code = event.get("eventTypeCode", "")
            event_status = event.get("statusCode", "unknown")
            start_time = format_datetime_short(event.get("startTime"))
            end_time = format_datetime_short(event.get("endTime"))
            event_region = event.get("region", "global")

            # 이벤트 설명 상세 조회
            description_text = ""
            try:
                details_res = health_client.describe_event_details(eventArns=[event_arn])
                successful_set = details_res.get("successfulSet", [])
                if successful_set:
                    event_desc_obj = successful_set[0].get("eventDescription", {})
                    description_text = event_desc_obj.get("latestDescription", "")
            except Exception as de:
                log_info_non_console(f"이벤트 상세 정보 조회 실패 ({event_arn}): {de}")

            # 정확한 EC2 인스턴스 재부팅 유지보수 일정 필터링
            is_target_code = event_code in TARGET_EVENT_CODES
            is_target_desc = TARGET_DESCRIPTION_KEYWORD in description_text.lower()

            if not (is_target_code or is_target_desc):
                continue

            # 영향받는 엔티티(인스턴스) 수집
            affected_entities = []
            try:
                ent_paginator = health_client.get_paginator("describe_affected_entities")
                for ent_page in ent_paginator.paginate(filter={"eventArns": [event_arn]}):
                    for entity in ent_page.get("entities", []):
                        affected_entities.append(entity)
            except Exception as ee:
                log_info_non_console(f"영향받는 엔티티 조회 실패 ({event_arn}): {ee}")

            if affected_entities:
                for entity in affected_entities:
                    entity_value = entity.get("entityValue", "-")  # 인스턴스 ID
                    entity_status = entity.get("statusCode", "UNKNOWN")  # IMPAIRED, RESOLVED 등
                    
                    parsed_region = parse_region_from_arn_or_event(event, entity)
                    inst_name, inst_state, final_region = get_instance_details(session, entity_value, parsed_region)

                    events_found.append({
                        "account_id": account_id,
                        "profile_name": profile_name,
                        "event_code": event_code,
                        "event_status": event_status,
                        "entity_status": entity_status,
                        "start_time": start_time,
                        "end_time": end_time,
                        "instance_id": entity_value,
                        "instance_name": inst_name,
                        "instance_state": inst_state,
                        "region": final_region,
                        "description": description_text
                    })
            else:
                events_found.append({
                    "account_id": account_id,
                    "profile_name": profile_name,
                    "event_code": event_code,
                    "event_status": event_status,
                    "entity_status": "-",
                    "start_time": start_time,
                    "end_time": end_time,
                    "instance_id": "-",
                    "instance_name": "-",
                    "instance_state": "-",
                    "region": event_region,
                    "description": description_text
                })

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "SubscriptionRequiredException":
            error_message = "AWS Business 또는 Enterprise Support 플랜이 필요합니다."
        elif error_code == "AccessDeniedException":
            error_message = "AWS Health API 접근 권한(health:DescribeEvents 등)이 부족합니다."
        else:
            error_message = f"AWS Health API 오류: {e.response.get('Error', {}).get('Message', str(e))}"
        log_info_non_console(f"Account {account_id} Health API ClientError: {e}")
    except Exception as e:
        error_message = f"오류 발생: {e}"
        log_info_non_console(f"Account {account_id} Health API 예외: {e}")

    return account_id, profile_name, events_found, error_message

def print_results(all_events, account_errors, verbose=False):
    """결과 데이터를 rich 표 및 안내 패널로 출력합니다."""
    console.print()

    if verbose and account_errors:
        for acct, prof, err in account_errors:
            console.print(f"[bold yellow]⚠️  [{prof} ({acct})][/bold yellow] {err}")
        console.print()

    if not all_events:
        panel_content = Text()
        panel_content.append("✅ 예정된 EC2 인스턴스 재부팅 일정이 없습니다.\n", style="bold green")
        panel_content.append("   (EC2 instance reboot maintenance scheduled)", style="dim")
        console.print(Panel(panel_content, title="AWS Health Dashboard", border_style="green", box=box.ROUNDED))
        console.print()
        return

    table = Table(
        title="🚨 EC2 Instance Reboot Maintenance Schedule",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True,
        expand=True
    )

    table.add_column("Account", style="cyan", min_width=15, ratio=2)
    table.add_column("Region", style="magenta", min_width=12, ratio=1)
    table.add_column("Instance ID", style="bold yellow", min_width=19, ratio=2)
    table.add_column("Instance Name", style="bold white", min_width=20, ratio=3)
    table.add_column("EC2 State", style="green", min_width=8, ratio=1)
    table.add_column("Entity Status", style="bold white", min_width=10, ratio=1)
    table.add_column("Event Status", style="dim", min_width=9, ratio=1)
    table.add_column("Scheduled Start", style="yellow", min_width=16, ratio=2)
    table.add_column("Scheduled End", style="dim", min_width=16, ratio=2)

    for item in all_events:
        event_status_display = item["event_status"]
        if item["event_status"].lower() in ["open", "upcoming"]:
            event_status_display = f"[yellow]{item['event_status']}[/yellow]"
        elif item["event_status"].lower() == "closed":
            event_status_display = f"[dim]{item['event_status']}[/dim]"

        entity_status_str = str(item["entity_status"]).upper()
        if entity_status_str == "RESOLVED":
            entity_status_display = "[bold green]RESOLVED[/bold green]"
        elif entity_status_str in ["IMPAIRED", "IMPACTED"]:
            entity_status_display = "[bold red]IMPAIRED[/bold red]"
        else:
            entity_status_display = entity_status_str

        state_str = str(item["instance_state"]).lower()
        if state_str == "running":
            state_display = f"[bold green]{item['instance_state']}[/bold green]"
        elif state_str in ["stopped", "stopping"]:
            state_display = f"[bold yellow]{item['instance_state']}[/bold yellow]"
        elif state_str == "terminated":
            state_display = f"[bold red]{item['instance_state']}[/bold red]"
        else:
            state_display = item["instance_state"]

        table.add_row(
            f"{item['profile_name']}\n({item['account_id']})",
            item["region"],
            item["instance_id"],
            item["instance_name"],
            state_display,
            entity_status_display,
            event_status_display,
            item["start_time"],
            item["end_time"]
        )

    console.print(table)
    console.print(f"\n총 [bold yellow]{len(all_events)}[/bold yellow]건의 유지보수 일정이 확인되었습니다.")
    console.print()

def main(args, config=None):
    """ic aws healthdashboard reboot 실행 엔트리 포인트"""
    all_accounts_flag = getattr(args, 'all_accounts', False)
    account_input = args.account if hasattr(args, 'account') and args.account else None

    # --all-accounts 플래그가 지정되었거나 계정이 지정되지 않은 경우, 로컬 AWS 프로파일 전체 수집
    if all_accounts_flag or not account_input:
        profiles_dict = get_profiles()
        valid_accounts = []
        if profiles_dict:
            for acct_id, prof_name in profiles_dict.items():
                # 'default' 제외하고 추가하거나 default도 활성화된 프로필이면 유지
                valid_accounts.append((acct_id, prof_name))
        else:
            valid_accounts = get_valid_accounts(None)
    else:
        valid_accounts = get_valid_accounts(account_input)

    if not valid_accounts:
        console.print("❌ 조회를 진행할 AWS 계정을 찾을 수 없습니다. (.env 또는 AWS 프로파일 설정을 확인하세요)")
        sys.exit(1)

    include_closed = getattr(args, 'all_status', False)
    all_events = []
    account_errors = []

    total_ops = len(valid_accounts)
    with ManualProgress("Checking AWS Health Dashboard for EC2 reboot schedules across all profiles...", total=total_ops) as progress:
        with ThreadPoolExecutor(max_workers=min(len(valid_accounts), 15)) as executor:
            futures = {
                executor.submit(fetch_reboot_events_for_account, acct, prof, include_closed): (acct, prof)
                for acct, prof in valid_accounts
            }

            for future in as_completed(futures):
                acct, prof = futures[future]
                try:
                    acct_id, prof_name, events, error_msg = future.result()
                    if error_msg:
                        account_errors.append((acct_id, prof_name, error_msg))
                    if events:
                        all_events.extend(events)
                    progress.update(f"Completed {prof_name} ({acct_id})", advance=1)
                except Exception as e:
                    account_errors.append((acct, prof, f"조회 중 예외 발생: {e}"))
                    progress.update(f"Failed {prof} ({acct})", advance=1)

    print_results(all_events, account_errors, verbose=getattr(args, 'verbose', False))

def add_arguments(parser):
    """Command line arguments definition"""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 또는 프로파일 지정 (구분자: ,)')
    parser.add_argument('-A', '--all-accounts', '--all-profiles', action='store_true', help='로컬 AWS 프로필에 등록된 모든 계정 전체 조회')
    parser.add_argument('--all-status', action='store_true', help='이미 종료된(closed) 과거 일정까지 포함하여 조회')
    parser.add_argument('-v', '--verbose', action='store_true', help='상세 에러 로그 및 정보 출력')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS Health Dashboard EC2 Reboot Schedule Check")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
