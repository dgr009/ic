# aws/nat/tag_check.py

import re
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_exception, log_decorator
from common.progress_decorator import ManualProgress
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table
from common.slack import send_slack_blocks_table_with_color

load_dotenv()
console = Console()

# 기본(하드코딩) 필수 태그 & 정규식
DEFAULT_REQUIRED_KEYS = ["User", "Team", "Environment"]
DEFAULT_RULES = {
    "User": r"^.+$",
    "Team": r"^\d+$",
    "Environment": r"^(PROD|STG|DEV|TEST|QA)$"
}

# .env에서 추가로 가져올 태그
ENV_REQUIRED_TAGS = os.getenv("REQUIRED_TAGS", "")
ENV_REQUIRED_LIST = [t.strip() for t in ENV_REQUIRED_TAGS.split(",") if t.strip()]

# .env에서 RULE_ 접두사 정규식 가져오기
ENV_RULES = {}
for key in ENV_REQUIRED_LIST:
    env_key = f"RULE_{key.upper()}"
    if env_key in os.environ:
        ENV_RULES[key] = os.environ[env_key]

# 최종 필수 태그 & RULES
REQUIRED_KEYS = sorted(set(DEFAULT_REQUIRED_KEYS + ENV_REQUIRED_LIST))
RULES = {**DEFAULT_RULES, **ENV_RULES}

TABLE_HEADER = ["Account", "Region", "NATGatewayId", "Validation Results"]

@log_decorator
def fetch_and_validate_nat_tags(account_id, profile_name, region):
    """
    NAT Gateway 태그를 불러와서 REQUIRED_KEYS & RULES 검증 후, 문제 있을 경우만 결과에 추가.
    """
    session = create_session(profile_name, region)
    if not session:
        log_error(f"Session creation failed for account {account_id} in region {region}")
        return []

    ec2_client = session.client("ec2")
    response = ec2_client.describe_nat_gateways()
    nat_gateways = response.get("NatGateways", [])

    invalid_rows = []
    for nat in nat_gateways:
        nat_id = nat.get("NatGatewayId")

        tags = {t["Key"]: t["Value"] for t in nat.get("Tags", [])}

        # 검증
        errors = []
        for key in REQUIRED_KEYS:
            val = tags.get(key)
            if not val:
                errors.append(f"필수 태그 '{key}' 누락")
            elif key in RULES and not re.match(RULES[key], val):
                errors.append(f"태그 '{key}' 규칙 불일치: {val}")

        if errors:
            invalid_rows.append([
                account_id,
                region,
                nat_id or "-",
                " / ".join(errors)
            ])

    return invalid_rows

@log_decorator
def check_all_nat_tags(args):
    """NAT Gateway 태그 유효성 검사 (병렬)"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    table = Table(title="NAT Gateway Tag Validation Results", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("NATGatewayId", style="cyan")
    table.add_column("Validation Results", style="red")

    table_data = []
    found_issues = False

    # Filter out accounts without valid profiles
    valid_accounts = []
    for account_id in accounts:
        profile_name = profiles.get(account_id)
        if profile_name:
            valid_accounts.append((account_id, profile_name))
        else:
            log_error(f"Account {account_id} not found in profiles")
    
    total_operations = len(valid_accounts) * len(regions)
    
    with ManualProgress("Validating NAT Gateway tags across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for account_id, profile_name in valid_accounts:
                for region in regions:
                    future = executor.submit(fetch_and_validate_nat_tags, account_id, profile_name, region)
                    futures.append(future)
                    future_to_info[future] = (account_id, region)

            completed = 0
            for future in as_completed(futures):
                account_id, region = future_to_info[future]
                try:
                    results = future.result()
                    if results:
                        found_issues = True
                        for row in results:
                            table.add_row(*row)
                            table_data.append(row)
                    completed += 1
                    issues_count = len(results) if results else 0
                    progress.update(f"Processed {account_id}/{region} - Found {issues_count} tag issues", advance=1)
                except Exception as e:
                    completed += 1
                    log_exception(e)
                    progress.update(f"Failed {account_id}/{region} - {str(e)[:50]}...", advance=1)

    if found_issues:
        log_info("NAT Gateway 태그 유효성 검사 결과 (이슈 있음):")
        console.print(table)
        send_slack_blocks_table_with_color("NAT Gateway 태그 유효성 검사 결과", TABLE_HEADER, table_data)
    else:
        log_info("모든 NAT 태그가 유효합니다.")
        table_data.append(["-", "-", "-", "모든 NAT 태그가 유효합니다."])
        send_slack_blocks_table_with_color("NAT Gateway 태그 유효성 검사 결과", TABLE_HEADER, table_data)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID (없으면 .env에서 모든 계정)')
    parser.add_argument('-r', '--regions', help='특정 리전 목록 (없으면 .env에서 모든 리전)')

def main(args):
    check_all_nat_tags(args)