import re
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.log import log_info, log_error, log_decorator
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table
from common.slack import send_slack_blocks_table_with_color

load_dotenv()

# Rich 콘솔 객체 초기화
console = Console()

DEFAULT_REQUIRED_KEYS = [
    "Name", "User", "Team", "Service", "Role", "Environment"
]

DEFAULT_RULES = {
    "User": r"^.+$",
    "Team": r"^\d+$",
    "Name": r"^[a-zA-Z0-9_\-+() ]+$",
    "Role": r"^[a-zA-Z0-9_\-+, ]+$",
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

TABLE_HEADER = ["Account", "Region", "InstanceID", "Validation Results"]



@log_decorator
def fetch_and_validate_tags(account_id, profile_name, region, resource_id=None):
    """특정 리전의 EC2 인스턴스에 대한 태그를 가져오고 유효성 검사."""
    session = create_session(profile_name, region)
    if not session:
        log_error(f"Session creation failed for account {account_id} in region {region}")
        return []

    ec2 = session.resource('ec2')
    resources = [ec2.Instance(resource_id)] if resource_id else ec2.instances.all()

    results = []

    for resource in resources:
        tags = {tag['Key']: tag['Value'] for tag in resource.tags or {}}
        errors = validate_tag_rules(tags)

        if errors:  # 오류가 있는 경우에만 테이블에 추가
            results.append([
                account_id,
                region,
                resource.id,
                " / ".join(errors),
            ])

    return results

@log_decorator
def validate_tag_rules(tags):
    errors = []
    # **필수 태그 존재 및 값 검사**
    for key in REQUIRED_KEYS:
        value = tags.get(key)
        if not value:
            errors.append(f"필수 태그 '{key}'가 누락 or 비어있음")
        elif key in RULES and not re.match(RULES[key], value):
            errors.append(f"태그 '{key}' 값 '{value}' → 규칙 불일치")
    return errors

@log_decorator
def check_all_ec2_tags(args):
    """모든 계정과 리전의 EC2 태그를 병렬로 검사."""
    accounts = [args.account] if args.account else get_env_accounts()
    regions = DEFINED_REGIONS
    profiles = get_profiles()

    # 테이블 초기화
    table = Table(title="EC2 Tag Validation Results", show_header=True, header_style="bold magenta", expand=True)
    table.add_column(TABLE_HEADER[0], style="green")
    table.add_column(TABLE_HEADER[1], style="blue")
    table.add_column(TABLE_HEADER[2], style="cyan")
    table.add_column(TABLE_HEADER[3], style="red")

    futures = []

    # 병렬 처리 시
    with ThreadPoolExecutor() as executor:
        for account_id in accounts:
            profile_name = profiles.get(account_id)
            if not profile_name:
                log_error(f"Account {account_id} not found in profiles")
                continue
            for region in regions:
                futures.append(
                    executor.submit(fetch_and_validate_tags, account_id, profile_name, region, args.resource)
                )

        # 결과 수집 및 테이블 작성
        validation_results = False  # 유효성 오류가 있는지 추적
        table_data = [] # 슬랙 전송을 위한 데이터 저장

        for future in as_completed(futures):
            try:
                results = future.result()
                if results:  # 유효성 오류가 있는 경우만 테이블에 추가
                    validation_results = True
                    for row in results:
                        table.add_row(*row)
                        table_data.append(row)
            except Exception as e:
                log_error(f"Error processing tags: {e}")

    # 결과 출력
    if validation_results:
        log_info("EC2 태그 유효성 검사 결과:")
        console.print(table)  # 유효성 오류가 있는 경우 테이블 출력       
        send_slack_blocks_table_with_color("EC2 태그 유효성 검사 결과", TABLE_HEADER, table_data)
    else:
        log_info("모든 태그가 유효합니다.")  # 모든 인스턴스가 유효한 경우 메시지 출력
        table_data.append(["all","all","all","모든태그가 유효합니다."])
        send_slack_blocks_table_with_color("EC2 태그 유효성 검사 결과", TABLE_HEADER, table_data)
        # send_slack_message("EC2 태그 검사 완료 > 모든 태그가 유효합니다")

def add_arguments(parser):
    """tag_check 명령어에 필요한 인수 추가."""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID (없으면 .env에서 모든 계정 사용)')
    parser.add_argument('-r', '--resource', help='특정 리소스 ID (없으면 모든 리소스 검사)')

def main(args):
    """tag_check 진입점."""
    check_all_ec2_tags(args)