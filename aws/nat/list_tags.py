# aws/nat/list_tags.py

import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_exception, log_decorator
from common.progress_decorator import ManualProgress
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table

load_dotenv()

console = Console()

# .env에서 공통 태그 키를 읽기 (EC2 / LB와 동일)
env_required = os.getenv("REQUIRED_TAGS", "User,Team,Environment")
env_optional = os.getenv("OPTIONAL_TAGS", "Service,Application")

required_tags = [t.strip() for t in env_required.split(",") if t.strip()]
optional_tags = [t.strip() for t in env_optional.split(",") if t.strip()]
TAG_KEYS = required_tags + optional_tags

@log_decorator
def fetch_nat_tags(account_id, profile_name, region):
    """
    NAT Gateway 태그 정보를 조회하고, (Account, Region, NatGatewayId, <tag1>, <tag2>...) 형태로 반환.
    """
    try:
        session = create_session(profile_name, region)
        if not session:
            log_error(f"Session creation failed for account {account_id} in region {region}")
            return []

        ec2_client = session.client("ec2", region_name=region)
        response = ec2_client.describe_nat_gateways()
        nat_gateways = response.get("NatGateways", [])

        results = []
        for nat in nat_gateways:
            nat_id = nat.get("NatGatewayId", "-")
            tags = {t["Key"]: t["Value"] for t in nat.get("Tags", [])}

            # [Account, Region, NAT Gateway ID] + 태그 키별로 값 or "-"
            row_data = [account_id, region, nat_id]
            for tag_key in TAG_KEYS:
                row_data.append(tags.get(tag_key, "-"))

            results.append(row_data)
        return results

    except Exception as e:
        log_exception(e)
        log_error(f"Skipping {account_id} / {region} due to an error.")
        return []

@log_decorator
def list_nat_tags(args):
    """NAT Gateway 태그를 병렬로 조회하여 콘솔 테이블로 출력."""
    # 계정/리전 목록
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    # 테이블 구성
    table = Table(title="NAT Gateway Tags Summary", show_header=True, header_style="bold magenta")

    # 고정 컬럼
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("NatGatewayId", style="cyan")

    # .env에서 읽은 TAG_KEYS 기반 동적 컬럼
    for tag_key in TAG_KEYS:
        table.add_column(tag_key)

    # Filter out accounts without valid profiles
    valid_accounts = []
    for account_id in accounts:
        profile_name = profiles.get(account_id)
        if profile_name:
            valid_accounts.append((account_id, profile_name))
        else:
            log_info(f"Account {account_id} not found in profiles")
    
    total_operations = len(valid_accounts) * len(regions)
    
    with ManualProgress("Collecting NAT Gateway tags across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for account_id, profile_name in valid_accounts:
                for region in regions:
                    future = executor.submit(fetch_nat_tags, account_id, profile_name, region)
                    futures.append(future)
                    future_to_info[future] = (account_id, region)

            completed = 0
            for future in as_completed(futures):
                account_id, region = future_to_info[future]
                try:
                    rows = future.result()
                    nat_count = len(rows)
                    for row in rows:
                        table.add_row(*row)
                    completed += 1
                    progress.update(f"Processed {account_id}/{region} - Found {nat_count} NAT Gateways", advance=1)
                except Exception as e:
                    completed += 1
                    log_exception(e)
                    progress.update(f"Failed {account_id}/{region} - {str(e)[:50]}...", advance=1)

    log_info("NAT Gateway 태그 조회 결과:")
    console.print(table)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='조회할 AWS 계정 ID 목록 (구분자 ",") (없으면 .env에서 로드)')
    parser.add_argument('-r', '--regions', help='조회할 리전 목록 (구분자 ",") (없으면 .env에서 로드)')

def main(args):
    list_nat_tags(args)