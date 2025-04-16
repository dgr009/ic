# aws/s3/list_tags.py

import os
import botocore
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_exception, log_decorator
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()

env_required = os.getenv("REQUIRED_TAGS", "User,Team,Environment")
env_optional = os.getenv("OPTIONAL_TAGS", "Service,Application")
required_tags = [t.strip() for t in env_required.split(",") if t.strip()]
optional_tags = [t.strip() for t in env_optional.split(",") if t.strip()]
TAG_KEYS = required_tags + optional_tags

@log_decorator
def fetch_s3_tags(account_id, profile_name, region):
    try:
        session = create_session(profile_name, region)
        if not session:
            log_error(f"Session creation failed for account {account_id} in region {region}")
            return []

        s3_client = session.client("s3", region_name=region)
        buckets_resp = s3_client.list_buckets()
        buckets = buckets_resp.get("Buckets", [])

        results = []
        for b in buckets:
            bucket_name = b["Name"]
            actual_region = "Unknown"

            # 실제 리전 가져오기
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
                    # 태그가 없는 경우
                    tags = []
                elif error_code == "IllegalLocationConstraintException":
                    continue
                else:
                    log_exception(e)
                    log_error(f"Skipping {bucket_name} in account {account_id} / region {region} due to error.")
                    continue

            tag_dict = {t["Key"]: t["Value"] for t in tags}

            # row_data 구성 (N/A 표기)
            row_data = [account_id, actual_region, bucket_name]
            for tag_key in TAG_KEYS:
                row_data.append(tag_dict.get(tag_key, "-"))

            results.append(row_data)

        return results

    except Exception as e:
        log_exception(e)
        log_error(f"Skipping account {account_id} / region {region} due to an error.")
        return []

@log_decorator
def list_s3_tags(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    table = Table(title="S3 Bucket Tags Summary", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("BucketName", style="cyan")
    for tag_key in TAG_KEYS:
        table.add_column(tag_key)

    futures = []
    with ThreadPoolExecutor() as executor:
        for account_id in accounts:
            profile_name = profiles.get(account_id)
            if not profile_name:
                log_info(f"Account {account_id} not found in profiles")
                continue
            # for region in regions:
            # s3 global - region 하나에서 조회 (서울)
            futures.append(executor.submit(fetch_s3_tags, account_id, profile_name, "ap-northeast-2"))

        for future in as_completed(futures):
            try:
                rows = future.result()
                for row in rows:
                    table.add_row(*row)
            except Exception as e:
                log_exception(e)

    log_info("S3 버킷 태그 조회 결과:")
    console.print(table)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='...')
    parser.add_argument('-r', '--regions', help='...')

def main(args):
    list_s3_tags(args)