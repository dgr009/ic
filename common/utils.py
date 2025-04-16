import boto3
import configparser
import os
import re
import json
from dotenv import load_dotenv
from botocore.exceptions import BotoCoreError, ClientError
from common.log import log_info, log_error, log_exception  # 로그 모듈 통합

load_dotenv()

# 기본 태그 정의
DEFINED_TAGS = os.getenv("REQUIRED_TAGS", "Name")
DEFINED_REGIONS = os.getenv("REGIONS", "ap-northeast-2").split(",")

def get_env_accounts():
    """ .env에서 계정 목록을 가져옵니다. """
    accounts = os.getenv("AWS_ACCOUNTS", "")
    return accounts.split(",") if accounts else []

def ensure_directory_exists(directory):
    """지정된 경로에 디렉터리가 없으면 생성합니다."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        log_info(f"Created directory: {directory}")

def save_json(data, file_path):
    """데이터를 JSON 파일로 저장합니다."""
    try:
        ensure_directory_exists(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        log_info(f"Data saved to JSON: {file_path}")
    except Exception as e:
        log_exception(e)
        log_error(f"Error saving JSON to {file_path}")

def load_json(file_path):
    """JSON 파일을 로드합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log_info(f"Loaded JSON from {file_path}")
        return data
    except FileNotFoundError as e:
        log_error(f"JSON file not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        log_error(f"JSON decoding error in {file_path}: {e}")
        return None

def get_profiles():
    """AWS 프로파일과 계정 ID를 매핑하여 로드합니다."""
    config = configparser.ConfigParser()
    config.read(f"{os.path.expanduser('~')}/.aws/config")

    profiles = {}
    for section in config.sections():
        if section.startswith('profile '):
            profile_name = section.split('profile ')[1]
            role_arn = config[section].get('role_arn')
            if role_arn:
                match = re.search(r'arn:aws:iam::(\d+):role', role_arn)
                if match:
                    account_id = match.group(1)
                    profiles[account_id] = profile_name
            else:
                account_id = config[section].get('account_id')
                if account_id:
                    profiles[account_id] = profile_name

    profiles['default'] = 'default'
    return profiles

def create_session(profile_name, region_name):
    """AWS 세션을 생성합니다."""
    try:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        # log_info(f"Session created for profile '{profile_name}' in region '{region_name}'")
        return session
    except (BotoCoreError, ClientError) as e:
        log_exception(e)
        log_error(f"Failed to create session for profile '{profile_name}' in region '{region_name}'")
        return None

def get_boto3_client(service, session):
    """AWS 서비스 클라이언트를 생성합니다."""
    try:
        client = session.client(service)
        log_info(f"Created boto3 client for service '{service}'")
        return client
    except Exception as e:
        log_exception(e)
        log_error(f"Failed to create client for service '{service}'")
        return None

def handle_boto3_exceptions(func):
    """Boto3 관련 예외 처리를 위한 데코레이터."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (BotoCoreError, ClientError) as e:
            log_exception(e)
            log_error(f"AWS API 호출 중 오류 발생: {e}")
            return None
    return wrapper

@handle_boto3_exceptions
def list_instances(session):
    """모든 EC2 인스턴스를 나열합니다."""
    ec2 = session.resource('ec2')
    instances = ec2.instances.all()
    instance_ids = [instance.id for instance in instances]
    log_info(f"Found {len(instance_ids)} instances")
    return instance_ids

@handle_boto3_exceptions
def describe_instance_tags(instance_id, session):
    """특정 인스턴스의 태그 정보를 반환합니다."""
    ec2 = session.resource('ec2')
    instance = ec2.Instance(instance_id)
    if instance.tags:
        tag_dict = {tag['Key']: tag['Value'] for tag in instance.tags}
        # log_info(f"Fetched tags for instance {instance_id}")
        return tag_dict
    log_info(f"No tags found for instance {instance_id}")
    return {}

def display_table(data, headers):
    """PrettyTable을 사용해 데이터를 테이블 형식으로 출력합니다."""
    table = PrettyTable()
    table.field_names = headers

    for row in data:
        table.add_row(row)

    log_info("Displaying table:")
    print(table)