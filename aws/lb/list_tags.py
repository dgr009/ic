# aws/lb/list_tags.py

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from dotenv import load_dotenv
from common.log import log_info, log_error, log_exception, log_decorator
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table

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

# 새로운 설정 시스템에서 태그 키 가져오기
def get_tag_keys():
    """설정에서 태그 키를 가져옵니다."""
    if config and 'aws' in config and 'tags' in config['aws']:
        aws_tags = config['aws']['tags']
        required_tags = aws_tags.get('required', ['User', 'Team', 'Environment'])
        optional_tags = aws_tags.get('optional', ['Service', 'Application'])
    else:
        # Fallback to environment variables
        env_required = os.getenv("REQUIRED_TAGS", "User,Team,Environment")
        env_optional = os.getenv("OPTIONAL_TAGS", "Service,Application")
        required_tags = [t.strip() for t in env_required.split(",") if t.strip()]
        optional_tags = [t.strip() for t in env_optional.split(",") if t.strip()]
    
    return required_tags + optional_tags

TAG_KEYS = get_tag_keys()

@log_decorator
def fetch_lb_tags(account_id, profile_name, region):
    try:
        session = create_session(profile_name, region)
        if not session:
            log_error(f"Session creation failed for account {account_id} in region {region}")
            return []

        elbv2_client = session.client("elbv2")
        lbs = elbv2_client.describe_load_balancers().get("LoadBalancers", [])

        results = []
        for lb in lbs:
            lb_arn = lb["LoadBalancerArn"]
            lb_name = lb["LoadBalancerName"]

            tag_desc = elbv2_client.describe_tags(ResourceArns=[lb_arn]).get("TagDescriptions", [])
            if not tag_desc:
                # 태그 없음 → 필드 전부 "-"
                row = [account_id, region, lb_name] + ["-" for _ in TAG_KEYS]
                results.append(row)
                continue

            # 태그 딕셔너리화
            tags = {t["Key"]: t["Value"] for t in tag_desc[0]["Tags"]}

            # row 구성
            row_data = [account_id, region, lb_name]
            for tag_key in TAG_KEYS:
                row_data.append(tags.get(tag_key, "-"))

            results.append(row_data)
        return results

    except Exception as e:
        log_exception(e)
        log_error(f"Skipping {account_id} / {region} due to an error.")
        return []

@log_decorator
def list_lb_tags(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    # 테이블 생성
    table = Table(title="LB Tags Summary", show_header=True, header_style="bold magenta")

    # 고정 컬럼 (Account, Region, LBName)
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("LBName", style="cyan")

    # .env 공통 태그 컬럼
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
                    executor.submit(fetch_lb_tags, account_id, profile_name, region)
                )

        for future in as_completed(futures):
            try:
                rows = future.result()
                for row in rows:
                    table.add_row(*row)
            except Exception as e:
                log_exception(e)

    log_info("LB 태그 조회 결과:")
    console.print(table)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='조회할 AWS 계정 ID (구분자 ",")')
    parser.add_argument('-r', '--regions', help='조회할 리전 목록 (구분자 ",")')

def main(args):
    list_lb_tags(args)