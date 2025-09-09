import boto3
import configparser
import os
import re
import json
from botocore.exceptions import BotoCoreError, ClientError
from common.log import log_info, log_error, log_exception  # 로그 모듈 통합

# 새로운 설정 시스템 import
try:
    from ic.config.manager import ConfigManager
    config_manager = ConfigManager()
    config = config_manager.load_all_configs()  # secrets 포함한 전체 설정 로드
    USE_NEW_CONFIG = True
except ImportError:
    # 호환성을 위한 fallback
    from dotenv import load_dotenv
    load_dotenv()
    config = {}
    USE_NEW_CONFIG = False

def get_config_value(key, default_value, config_path=None):
    """설정에서 값을 가져오는 헬퍼 함수"""
    if USE_NEW_CONFIG and config:
        if config_path:
            # 중첩된 설정 경로 (예: 'aws.regions')
            value = config
            for path_part in config_path.split('.'):
                value = value.get(path_part, {})
            return value if value != {} else default_value
        else:
            return config.get(key, default_value)
    else:
        return os.getenv(key, default_value)

# 기본 태그 정의
DEFINED_TAGS = get_config_value("REQUIRED_TAGS", "Name")
DEFINED_REGIONS = get_config_value("REGIONS", "ap-northeast-2", "aws.regions")
if isinstance(DEFINED_REGIONS, str):
    DEFINED_REGIONS = DEFINED_REGIONS.split(",")

def get_env_accounts():
    """설정에서 계정 목록을 가져옵니다."""
    if USE_NEW_CONFIG and config and 'aws' in config:
        return config['aws'].get('accounts', [])
    else:
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
    # 새로운 설정 시스템에서 외부 AWS 설정 로드 시도
    if USE_NEW_CONFIG:
        try:
            from ic.config.external import ExternalConfigLoader
            external_loader = ExternalConfigLoader()
            aws_config = external_loader.load_aws_config()
            
            if aws_config and 'profiles' in aws_config:
                # 프로파일에서 계정 ID 추출하여 매핑
                profiles = {}
                for profile_name, profile_config in aws_config['profiles'].items():
                    role_arn = profile_config.get('role_arn')
                    if role_arn:
                        match = re.search(r'arn:aws:iam::(\d+):role', role_arn)
                        if match:
                            account_id = match.group(1)
                            profiles[account_id] = profile_name
                    else:
                        account_id = profile_config.get('account_id')
                        if account_id:
                            profiles[account_id] = profile_name
                
                # default 프로파일 추가
                if 'default' in aws_config['profiles']:
                    profiles['default'] = 'default'
                
                return profiles
        except Exception as e:
            log_error(f"Failed to load AWS config from new system: {e}")
    
    # Fallback to traditional AWS config file parsing
    aws_config = configparser.ConfigParser()
    aws_config.read(f"{os.path.expanduser('~')}/.aws/config")

    profiles = {}
    for section in aws_config.sections():
        if section.startswith('profile '):
            profile_name = section.split('profile ')[1]
            role_arn = aws_config[section].get('role_arn')
            if role_arn:
                match = re.search(r'arn:aws:iam::(\d+):role', role_arn)
                if match:
                    account_id = match.group(1)
                    profiles[account_id] = profile_name
            else:
                account_id = aws_config[section].get('account_id')
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