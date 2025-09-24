import os
from concurrent.futures import ThreadPoolExecutor, as_completed
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
def fetch_instance_tags(account_id, profile_name, region):
    """특정 계정과 리전의 EC2 인스턴스 태그를 가져옵니다."""
    try:
        session = create_session(profile_name, region)
        if not session:
            log_error(f"Session creation failed for account {account_id} in region {region}")
            return []

        ec2 = session.resource('ec2')
        instances = ec2.instances.all()
        results = []

        for instance in instances:
            tags = {tag['Key']: tag['Value'] for tag in (instance.tags or [])}

            # [Account, Region, InstanceID] + env에서 불러온 TAG_KEYS 순서대로
            row_data = [account_id, region, instance.id]
            for tag_key in TAG_KEYS:
                row_data.append(tags.get(tag_key, "-"))

            results.append(row_data)

        return results

    except Exception as e:
        log_exception(e)
        log_error(f"Skipping {account_id} / {region} due to an error.")
        return []

@log_decorator
def list_ec2_tags(args):
    """모든 계정과 리전의 EC2 인스턴스 태그를 병렬로 조회합니다."""
    # 계정/리전 목록 설정
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    # 테이블 생성
    table = Table(title="EC2 Tags Summary", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("InstanceID", style="cyan")

    # .env에서 가져온 태그 키를 기준으로 동적으로 컬럼 추가
    for tag_key in TAG_KEYS:
        table.add_column(tag_key)

    # 병렬 처리
    futures = []
    with ThreadPoolExecutor() as executor:
        for account_id in accounts:
            profile_name = profiles.get(account_id)
            if not profile_name:
                log_info(f"Account {account_id} not found in profiles")
                continue
            for region in regions:
                futures.append(
                    executor.submit(fetch_instance_tags, account_id, profile_name, region)
                )

        for future in as_completed(futures):
            try:
                results = future.result()
                for row in results:
                    table.add_row(*row)
            except Exception as e:
                log_exception(e)

    # 테이블 출력
    log_info("EC2 태그 조회 결과:")
    console.print(table)

def add_arguments(parser):
    """list_tags 명령에 필요한 인수 추가."""
    parser.add_argument('-a', '--account', help='태그를 조회할 AWS 계정 ID 목록(,) (없으면 .env에서 로드)')
    parser.add_argument('-r', '--regions', help='태그를 조회할 리전 목록(,) (없으면 .env에서 로드)')

def main(args):
    """list_tags의 진입점."""
    list_ec2_tags(args)