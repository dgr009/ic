# aws/lb/tag_check.py

import re
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_exception, log_decorator
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table
from common.slack import send_slack_blocks_table_with_color

load_dotenv()
console = Console()

# LB에도 EC2와 동일한 태그를 요구한다고 가정 (원하면 따로 해도 됨)
# 필요하면 .env + 하드코딩 혼합
DEFAULT_REQUIRED_KEYS = ["User", "Team", "Environment"]  
DEFAULT_RULES = {
    "User": r"^.+$",
    "Team": r"^\d+$",
    "Environment": r"^(PROD|STG|DEV|TEST|QA)$"
}

# [추가] .env에서 태그/정규식 불러오기
ENV_REQUIRED_TAGS = os.getenv("REQUIRED_TAGS", "")
ENV_REQUIRED_LIST = [t.strip() for t in ENV_REQUIRED_TAGS.split(",") if t.strip()]

# RULE_ 접두사의 환경변수를 읽어와서 dict로 만드는 로직 예시
ENV_RULES = {}
for key in ENV_REQUIRED_LIST:
    env_key = f"RULE_{key.upper()}"  # 예: RULE_USER
    if env_key in os.environ:
        ENV_RULES[key] = os.environ[env_key]

# 최종적으로 합쳐서 사용 (중복 제거)
REQUIRED_KEYS = sorted(set(DEFAULT_REQUIRED_KEYS + ENV_REQUIRED_LIST))
RULES = {**DEFAULT_RULES, **ENV_RULES}

TABLE_HEADER = ["Account", "Region", "LBName", "Validation Results"]

@log_decorator
def fetch_and_validate_lb_tags(account_id, profile_name, region):
    """
    LB 태그를 불러와서 REQUIRED_KEYS & RULES 검증 후, 문제 있을 경우만 결과에 추가.
    """
    session = create_session(profile_name, region)
    if not session:
        log_error(f"Session creation failed for account {account_id} in region {region}")
        return []

    elbv2_client = session.client("elbv2")
    lbs = elbv2_client.describe_load_balancers().get("LoadBalancers", [])

    invalid_rows = []
    for lb in lbs:
        lb_arn = lb["LoadBalancerArn"]
        lb_name = lb["LoadBalancerName"]

        tag_desc = elbv2_client.describe_tags(ResourceArns=[lb_arn]).get("TagDescriptions", [])
        if not tag_desc:
            # 태그 전혀 없으면 필수 태그 전부 누락!
            missing = ", ".join(REQUIRED_KEYS)
            invalid_rows.append([account_id, region, lb_name, f"모든 태그 누락: {missing}"])
            continue

        tags = {t["Key"]: t["Value"] for t in tag_desc[0]["Tags"]}

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
                lb_name,
                " / ".join(errors)
            ])

    return invalid_rows


@log_decorator
def check_all_lb_tags(args):
    """LB 태그 유효성 검사 (병렬)"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    table = Table(title="LB Tag Validation Results", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("LBName", style="cyan")
    table.add_column("Validation Results", style="red")

    table_data = []
    found_issues = False

    futures = []
    with ThreadPoolExecutor() as executor:
        for account_id in accounts:
            profile_name = profiles.get(account_id)
            if not profile_name:
                log_error(f"Account {account_id} not found in profiles")
                continue

            for region in regions:
                futures.append(
                    executor.submit(fetch_and_validate_lb_tags, account_id, profile_name, region)
                )

        for f in as_completed(futures):
            try:
                results = f.result()
                if results:
                    found_issues = True
                    for row in results:
                        table.add_row(*row)
                        table_data.append(row)
            except Exception as e:
                log_exception(e)

    if found_issues:
        log_info("LB 태그 유효성 검사 결과 (이슈 있음):")
        console.print(table)
        send_slack_blocks_table_with_color("LB 태그 유효성 검사 결과", TABLE_HEADER, table_data)
    else:
        log_info("모든 LB 태그가 유효합니다.")
        table_data.append(["-", "-", "-", "모든 LB 태그가 유효합니다."])
        send_slack_blocks_table_with_color("LB 태그 유효성 검사 결과", TABLE_HEADER, table_data)


def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID (없으면 .env에서 모든 계정)')
    parser.add_argument('-r', '--regions', help='특정 리전 목록 (없으면 .env에서 모든 리전)')

def main(args):
    check_all_lb_tags(args)