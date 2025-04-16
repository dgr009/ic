# aws/s3/tag_check.py

import os
import re
import botocore
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_exception, log_decorator
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table
from common.slack import send_slack_blocks_table_with_color

# (주의) cli.py에서 load_dotenv()를 이미 한다면, 중복 호출일 수 있음
load_dotenv()
console = Console()

# 기본(하드코딩) + .env 결합
DEFAULT_REQUIRED_KEYS = ["User", "Team", "Environment"]  # 필요하다면 추가
DEFAULT_RULES = {
    "User": r"^.+$",
    "Team": r"^\d+$",
    "Environment": r"^(PROD|STG|DEV|TEST|QA)$"
}

env_required = os.getenv("REQUIRED_TAGS", "")
env_required_list = [t.strip() for t in env_required.split(",") if t.strip()]

ENV_RULES = {}
for k in env_required_list:
    env_key = f"RULE_{k.upper()}"
    if env_key in os.environ:
        ENV_RULES[k] = os.environ[env_key]

# 최종 필수 태그 & RULES
REQUIRED_KEYS = sorted(set(DEFAULT_REQUIRED_KEYS + env_required_list))
RULES = {**DEFAULT_RULES, **ENV_RULES}

TABLE_HEADER = ["Account", "Region", "BucketName", "Validation Results"]

@log_decorator
def fetch_and_validate_s3_tags(account_id, profile_name, region):
    """
    S3 버킷 태그 조회 후, REQUIRED_KEYS & RULES 검증.
    """
    session = create_session(profile_name, region)
    if not session:
        log_error(f"Session creation failed for account {account_id} in region {region}")
        return []

    s3_client = session.client("s3", region_name=region)
    buckets_resp = s3_client.list_buckets()
    buckets = buckets_resp.get("Buckets", [])

    invalid_rows = []
    for b in buckets:
        bucket_name = b["Name"]
        actual_region = "Unknown"  # 기본값

        # 실제 리전 조회
        try:
            location_resp = s3_client.get_bucket_location(Bucket=bucket_name)
            actual_region = location_resp.get("LocationConstraint", "us-east-1")
            if not actual_region:
                actual_region = "us-east-1"
        except Exception as e:
            log_exception(e)

        # 태그 가져오기
        try:
            tagging_resp = s3_client.get_bucket_tagging(Bucket=bucket_name)
            tags = tagging_resp.get("TagSet", [])
        except botocore.exceptions.ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchTagSet":
                # 태그 전혀 없는 경우 => 필수 태그 전부 누락 처리
                missing = ", ".join(REQUIRED_KEYS)
                invalid_rows.append([
                    account_id,
                    actual_region,
                    bucket_name,
                    f"모든 태그 누락: {missing}"
                ])
                continue
            elif error_code == "IllegalLocationConstraintException":
                # region mismatch -> 스킵
                continue
            else:
                log_exception(e)
                log_error(f"Skipping {bucket_name} in account {account_id} / region {region}")
                continue

        # 태그 dict
        tag_dict = {t["Key"]: t["Value"] for t in tags}

        # 필수 태그 검사
        errors = []
        for key in REQUIRED_KEYS:
            val = tag_dict.get(key)
            if key == "Name" :
                continue
            if not val:
                errors.append(f"필수 태그 '{key}' 누락")
            else:
                rule_pattern = RULES.get(key)
                if rule_pattern and not re.match(rule_pattern, val):
                    errors.append(f"'{key}' 규칙 불일치: {val}")

        if errors:
            invalid_rows.append([
                account_id,
                actual_region,
                bucket_name,
                " / ".join(errors)
            ])

    return invalid_rows

@log_decorator
def check_all_s3_tags(args):
    """S3 태그 유효성 검사"""
    # 계정/리전 설정
    accounts = args.account.split(",") if args.account else get_env_accounts()
    # S3는 global endpoint가 많으니, 굳이 regions를 안 돌려도 되지만 필요하면 해도 됨.
    # 여기선 '서울' 등 특정 region만 쓰고 싶으면 아래처럼 커스텀해도 됨.
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    table = Table(title="S3 Tag Validation Results", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("BucketName", style="cyan")
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

            # 예: region = "ap-northeast-2"로 고정 (S3 global) or loop for all DEFINED_REGIONS
            # 여기서는 list_tags와 맞춰서 region 하나만 하는 식의 예시:
            futures.append(
                executor.submit(fetch_and_validate_s3_tags, account_id, profile_name, "ap-northeast-2")
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
        log_info("S3 태그 유효성 검사 결과 (이슈 있음):")
        console.print(table)
        send_slack_blocks_table_with_color("S3 태그 유효성 검사 결과", TABLE_HEADER, table_data)
    else:
        log_info("모든 S3 버킷 태그가 유효합니다.")
        table_data.append(["-", "-", "-", "모든 S3 버킷 태그가 유효합니다."])
        send_slack_blocks_table_with_color("S3 태그 유효성 검사 결과", TABLE_HEADER, table_data)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 (없으면 .env에서 모든 계정)')
    parser.add_argument('-r', '--regions', help='특정 리전 (없으면 .env에서 모든 리전)')

def main(args):
    check_all_s3_tags(args)