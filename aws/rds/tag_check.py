# aws/rds/tag_check.py

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_exception, log_decorator
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table
from common.slack import send_slack_blocks_table_with_color

# 새로운 설정 시스템 import
try:
    from ic.config.manager import ConfigManager
    config_manager = ConfigManager()
    config = config_manager.get_config()
except ImportError:
    # 호환성을 위한 fallback
    from dotenv import load_dotenv
    load_dotenv()
    config = {}

console = Console()

def get_tag_validation_config():
    """설정에서 태그 검증 규칙을 가져옵니다."""
    if config and 'aws' in config and 'tags' in config['aws']:
        aws_tags = config['aws']['tags']
        required_keys = aws_tags.get('required', ['User', 'Team', 'Environment'])
        rules = aws_tags.get('rules', {
            'User': r'^.+$',
            'Team': r'^\d+$',
            'Environment': r'^(PROD|STG|DEV|TEST|QA)$'
        })
    else:
        # Fallback to environment variables
        DEFAULT_REQUIRED_KEYS = ["User", "Team", "Environment"]
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
        
        required_keys = sorted(set(DEFAULT_REQUIRED_KEYS + env_required_list))
        rules = {**DEFAULT_RULES, **ENV_RULES}
    
    return required_keys, rules

REQUIRED_KEYS, RULES = get_tag_validation_config()

TABLE_HEADER = ["Account", "Region", "DBIdentifier", "Validation Results"]

@log_decorator
def fetch_and_validate_rds_tags(account_id, profile_name, region):
    """
    RDS 인스턴스 태그 조회 후, REQUIRED_KEYS & RULES에 맞춰 유효성 검사
    """
    session = create_session(profile_name, region)
    if not session:
        log_error(f"Session creation failed for account {account_id} in region {region}")
        return []

    rds_client = session.client("rds", region_name=region)
    dbs = rds_client.describe_db_instances().get("DBInstances", [])

    invalid_rows = []
    for db in dbs:
        db_arn = db["DBInstanceArn"]
        db_id = db["DBInstanceIdentifier"]

        tag_list = rds_client.list_tags_for_resource(ResourceName=db_arn).get("TagList", [])
        tags = {t["Key"]: t["Value"] for t in tag_list}

        errors = []
        for key in REQUIRED_KEYS:
            val = tags.get(key)
            if not val:
                errors.append(f"필수 태그 '{key}' 누락")
            else:
                # 정규식
                rule_pattern = RULES.get(key)
                if rule_pattern and not re.match(rule_pattern, val):
                    errors.append(f"'{key}' 규칙 불일치: {val}")

        if errors:
            invalid_rows.append([
                account_id,
                region,
                db_id,
                " / ".join(errors)
            ])

    return invalid_rows

@log_decorator
def check_all_rds_tags(args):
    """RDS 태그 유효성 검사 (병렬)"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    table = Table(title="RDS Tag Validation Results", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("DBIdentifier", style="cyan")
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
                    executor.submit(fetch_and_validate_rds_tags, account_id, profile_name, region)
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
        log_info("RDS 태그 유효성 검사 결과 (이슈 있음):")
        console.print(table)
        send_slack_blocks_table_with_color("RDS 태그 유효성 검사 결과", TABLE_HEADER, table_data)
    else:
        log_info("모든 RDS 태그가 유효합니다.")
        table_data.append(["-", "-", "-", "모든 RDS 태그가 유효합니다."])
        send_slack_blocks_table_with_color("RDS 태그 유효성 검사 결과", TABLE_HEADER, table_data)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 (없으면 .env에서 모든 계정)')
    parser.add_argument('-r', '--regions', help='특정 리전 (없으면 .env에서 모든 리전)')

def main(args):
    check_all_rds_tags(args)