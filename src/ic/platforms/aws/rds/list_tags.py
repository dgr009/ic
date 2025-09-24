# aws/rds/list_tags.py

import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_exception, log_decorator
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()

# .env에서 공통 태그 키 불러오기
env_required = os.getenv("REQUIRED_TAGS", "User,Team,Environment")
env_optional = os.getenv("OPTIONAL_TAGS", "Service,Application")

required_tags = [t.strip() for t in env_required.split(",") if t.strip()]
optional_tags = [t.strip() for t in env_optional.split(",") if t.strip()]
TAG_KEYS = required_tags + optional_tags

@log_decorator
def fetch_rds_tags(account_id, profile_name, region):
    """
    RDS 인스턴스 태그 조회:
    DBInstances => 각 DBInstanceArn => list_tags_for_resource(ResourceName=arn)
    row 형식: [account_id, region, db_identifier, <tag1>, <tag2>, ...]
    """
    try:
        session = create_session(profile_name, region)
        if not session:
            log_error(f"Session creation failed for account {account_id} in region {region}")
            return []

        rds_client = session.client("rds", region_name=region)
        dbs = rds_client.describe_db_instances().get("DBInstances", [])

        results = []
        for db in dbs:
            db_arn = db["DBInstanceArn"]
            db_id = db["DBInstanceIdentifier"]

            # RDS 태그 조회
            tag_list = rds_client.list_tags_for_resource(ResourceName=db_arn).get("TagList", [])

            tags = {t["Key"]: t["Value"] for t in tag_list}

            # [Account, Region, DBIdentifier] + env에서 가져온 TAG_KEYS
            row_data = [account_id, region, db_id]
            for tag_key in TAG_KEYS:
                row_data.append(tags.get(tag_key, "-"))

            results.append(row_data)

        return results

    except Exception as e:
        log_exception(e)
        log_error(f"Skipping {account_id} / {region} due to error.")
        return []

@log_decorator
def list_rds_tags(args):
    """RDS 인스턴스 태그 조회, 계정/리전별 병렬 처리"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    table = Table(title="RDS Tags Summary", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("DBIdentifier", style="cyan")

    # .env 태그 컬럼 구성
    for tag_key in TAG_KEYS:
        table.add_column(tag_key)

    futures = []
    with ThreadPoolExecutor() as executor:
        for account_id in accounts:
            profile_name = profiles.get(account_id)
            if not profile_name:
                log_info(f"Account {account_id} not found in profiles")
                continue

            for region in regions:
                futures.append(
                    executor.submit(fetch_rds_tags, account_id, profile_name, region)
                )

        for future in as_completed(futures):
            try:
                rows = future.result()
                for row in rows:
                    table.add_row(*row)
            except Exception as e:
                log_exception(e)

    log_info("RDS 태그 조회 결과:")
    console.print(table)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='조회할 AWS 계정 (없으면 .env에서 모든 계정)')
    parser.add_argument('-r', '--regions', help='조회할 리전 (없으면 .env에서 모든 리전)')

def main(args):
    list_rds_tags(args)