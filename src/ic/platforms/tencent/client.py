#!/usr/bin/env python3
"""
Tencent Cloud Client Factory

AWS boto3.Session / get_profiles() 에 대응하는 Tencent 클라이언트 팩토리.

다중 계정을 지원하며, 메인 계정의 SecretId/SecretKey 로 STS AssumeRole 을 통해
서브 계정의 임시 자격증명을 발급합니다.

# Config YAML 예시 (EXAMPLE):
#   tencent:
#     main_account:
#       secret_id: "EXAMPLE_AKIDxxxxxxxxxxxxxxxx"
#       secret_key: "EXAMPLE_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
#     accounts:
#       - id: "100000000001"
#         name: "prod"
#         role_arn: "qcs::cam::uin/100000000001:role/CrossAccountRole"
#       - id: "100000000002"
#         name: "dev"
#         role_arn: "qcs::cam::uin/100000000002:role/CrossAccountRole"
#     regions:
#       - ap-seoul
#       - ap-tokyo

환경변수 예시 (단일 계정):
  TENCENT_SECRET_ID=AKIDxxx
  TENCENT_SECRET_KEY=xxx
  TENCENT_REGIONS=ap-seoul,ap-tokyo
"""

import os
import re
import configparser
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

try:
    from common.log import log_info_non_console
except ImportError:
    def log_info_non_console(msg):
        pass

# Tencent SDK import (optional - graceful failure if not installed)
try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    TENCENT_SDK_AVAILABLE = True
except ImportError:
    TENCENT_SDK_AVAILABLE = False

# 기본 리전 목록
TENCENT_DEFAULT_REGIONS = ["ap-seoul", "ap-tokyo"]

# ~/.tencent/credentials 기본 경로
TENCENT_CREDENTIALS_PATH = Path.home() / ".tencent" / "credentials"

# 임시 자격증명 캐시 (role_arn -> (cred, expire_time))
_credential_cache: Dict[str, Tuple[Any, float]] = {}

def _parse_tencent_credentials_file(creds_path: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    """
    ~/.tencent/credentials 파일을 파싱합니다.

    파일 형식 (INI, AWS config와 동일):

        [main]
        secret_id  = AKIDxxxxxxxxxx
        secret_key = xxxxxxxxxx

        [prod]
        role_arn       = qcs::cam::uin/100000000001:role/CrossAccountRole
        source_account = main          # main 섹션의 credentials 사용
        region         = ap-seoul

        [dev]
        role_arn       = qcs::cam::uin/100000000002:role/CrossAccountRole
        source_account = main
        region         = ap-seoul
    """
    path = creds_path or TENCENT_CREDENTIALS_PATH
    if not path.exists():
        return {}

    config = configparser.ConfigParser()
    config.read(path)

    sections: Dict[str, Dict[str, str]] = {}
    for section in config.sections():
        sections[section] = dict(config[section])
    return sections


def get_tencent_credentials_file_path() -> Path:
    """현재 사용 중인 credentials 파일 경로를 반환합니다."""
    return TENCENT_CREDENTIALS_PATH



def _get_config() -> Dict[str, Any]:
    """IC 설정에서 Tencent 설정을 로드합니다."""
    try:
        from ic.config.manager import ConfigManager
        mgr = ConfigManager()
        config = mgr.load_all_configs()
        return config.get("tencent", {})
    except Exception:
        return {}


def get_tencent_regions(regions_arg: Optional[str] = None) -> List[str]:
    """
    사용할 Tencent 리전 목록을 반환합니다.
    
    우선순위: CLI 인수 > config yaml > 환경변수 > 기본값
    """
    if regions_arg:
        return [r.strip() for r in regions_arg.split(",") if r.strip()]

    config = _get_config()
    config_regions = config.get("regions", [])
    if config_regions:
        if isinstance(config_regions, str):
            return [r.strip() for r in config_regions.split(",") if r.strip()]
        return list(config_regions)

    env_regions = os.getenv("TENCENT_REGIONS", "")
    if env_regions:
        return [r.strip() for r in env_regions.split(",") if r.strip()]

    return TENCENT_DEFAULT_REGIONS


def get_main_credential() -> Optional[Any]:
    """
    메인 계정의 자격증명 객체를 반환합니다.

    우선순위: ~/.tencent/credentials [main] > ic config yaml > 환경변수
    """
    if not TENCENT_SDK_AVAILABLE:
        return None

    # 1순위: ~/.tencent/credentials 파일의 [main] 섹션 또는 secret_id/key가 있는 첫 번째 섹션
    sections = _parse_tencent_credentials_file()
    if sections:
        main_section = sections.get("main", {})
        secret_id = main_section.get("secret_id", "")
        secret_key = main_section.get("secret_key", "")
        if secret_id and secret_key:
            return credential.Credential(secret_id, secret_key)
        
        # [main]이 없다면 secret_id, secret_key가 존재하는 첫 번째 섹션 찾기
        for sec_name, sec_data in sections.items():
            sid = sec_data.get("secret_id", "")
            skey = sec_data.get("secret_key", "")
            if sid and skey:
                return credential.Credential(sid, skey)

    # 2순위: ic config yaml
    config = _get_config()
    main_account = config.get("main_account", {})
    secret_id  = main_account.get("secret_id", "")
    secret_key = main_account.get("secret_key", "")
    if secret_id and secret_key:
        return credential.Credential(secret_id, secret_key)

    # 3순위: 환경변수
    secret_id  = os.getenv("TENCENT_SECRET_ID", "")
    secret_key = os.getenv("TENCENT_SECRET_KEY", "")
    if secret_id and secret_key:
        return credential.Credential(secret_id, secret_key)

    return None


def normalize_role_arn(role_arn: str) -> str:
    """Tencent Role ARN 규격을 보정합니다. (role/ -> roleName/)"""
    if not role_arn:
        return role_arn
    # qcs::cam::uin/12345:role/RoleName -> qcs::cam::uin/12345:roleName/RoleName
    if ":role/" in role_arn and ":roleName/" not in role_arn:
        return role_arn.replace(":role/", ":roleName/")
    return role_arn


def _assume_role(main_cred: Any, role_arn: str, account_name: str) -> Optional[Any]:
    """
    STS AssumeRole 로 서브 계정의 임시 자격증명을 발급합니다.
    
    결과는 캐시됩니다 (만료 5분 전까지 재사용).
    """
    normalized_arn = normalize_role_arn(role_arn)
    cache_key = normalized_arn

    # 캐시 확인 (만료 5분 전에 갱신)
    if cache_key in _credential_cache:
        cached_cred, expire_time = _credential_cache[cache_key]
        if time.time() < expire_time - 300:
            log_info_non_console(f"[Tencent] Using cached credentials for {account_name}")
            return cached_cred

    try:
        from tencentcloud.sts.v20180813 import sts_client, models as sts_models

        http_profile = HttpProfile()
        http_profile.endpoint = "sts.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        client = sts_client.StsClient(main_cred, "ap-seoul", client_profile)

        req = sts_models.AssumeRoleRequest()
        req.RoleArn = normalized_arn
        req.RoleSessionName = f"ic-cli-{account_name}"
        req.DurationSeconds = 3600  # 1시간

        resp = client.AssumeRole(req)

        if not resp.Credentials:
            msg = f"[Tencent] AssumeRole returned empty Credentials for {account_name}"
            log_info_non_console(msg)
            try:
                from rich.console import Console
                Console().print(f"[bold red]❌ AssumeRole 실패 ({account_name}): 임시 자격증명이 비어있습니다.[/bold red]")
            except Exception:
                pass
            return None

        tmp_cred = credential.Credential(
            resp.Credentials.TmpSecretId,
            resp.Credentials.TmpSecretKey,
            resp.Credentials.Token
        )

        # 캐시 저장 (만료 시간 기록)
        expire_time = time.time() + 3600
        _credential_cache[cache_key] = (tmp_cred, expire_time)

        log_info_non_console(f"[Tencent] AssumeRole success for {account_name} ({normalized_arn})")
        return tmp_cred

    except TencentCloudSDKException as e:
        msg = f"[Tencent] AssumeRole failed for {account_name} ({normalized_arn}): {e.code} - {e.message}"
        log_info_non_console(msg)
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ AssumeRole 실패 ({account_name}): [{e.code}] {e.message}[/bold red]")
        except Exception:
            pass
        return None
    except Exception as e:
        msg = f"[Tencent] AssumeRole unexpected error for {account_name}: {e}"
        log_info_non_console(msg)
        try:
            from rich.console import Console
            Console().print(f"[bold red]❌ AssumeRole 예외 발생 ({account_name}): {e}[/bold red]")
        except Exception:
            pass
        return None


def get_accounts(account_filter: Optional[str] = None) -> List[Dict[str, str]]:
    """
    설정된 Tencent 계정 목록을 반환합니다.

    우선순위: ~/.tencent/credentials > ic config yaml > 환경변수

    Args:
        account_filter: 콤마(,)로 구분된 계정 이름 또는 ID 필터.
                        None 이면 전체 계정 반환.

    Returns:
        [{"id": "...", "name": "...", "role_arn": "...", "region": "..."}, ...]
    """
    # 1순위: ~/.tencent/credentials 파일
    sections = _parse_tencent_credentials_file()
    if sections:
        accounts = []
        for name, data in sections.items():
            has_direct_creds = bool(data.get("secret_id") and data.get("secret_key"))
            role_arn = data.get("role_arn", "")

            m = re.search(r"uin/(\d+)", role_arn) if role_arn else None
            account_id = data.get("account_id") or (m.group(1) if m else name)

            if has_direct_creds or role_arn:
                accounts.append({
                    "id":               account_id,
                    "name":             name,
                    "role_arn":         role_arn,
                    "region":           data.get("region", ""),
                    "source_account":   data.get("source_account", ""),
                    "has_direct_creds": str(has_direct_creds),
                })

        all_accounts = accounts
    else:
        # 2순위: ic config yaml
        config = _get_config()
        yaml_accounts = config.get("accounts", [])
        if yaml_accounts:
            all_accounts = yaml_accounts
        else:
            # 3순위: 환경변수 폴백 (단일 계정)
            secret_id = os.getenv("TENCENT_SECRET_ID", "")
            if secret_id:
                account_id = os.getenv("TENCENT_ACCOUNT_ID", "main")
                all_accounts = [{"id": account_id, "name": account_id, "role_arn": ""}]
            else:
                all_accounts = []

    if not account_filter:
        return all_accounts

    # 이름 또는 ID 기반 필터
    filter_set = {f.strip().lower() for f in account_filter.split(",") if f.strip()}
    filtered = [
        a for a in all_accounts
        if a.get("name", "").lower() in filter_set
        or str(a.get("id", "")).lower() in filter_set
    ]
    return filtered


def _get_direct_credential_for_section(section_name: str) -> Optional[Any]:
    """credentials 파일 섹션에서 직접 secret_id/key 자격증명을 가져옵니다."""
    if not TENCENT_SDK_AVAILABLE:
        return None
    sections = _parse_tencent_credentials_file()
    if sections and section_name in sections:
        data = sections[section_name]
        secret_id  = data.get("secret_id", "")
        secret_key = data.get("secret_key", "")
        if secret_id and secret_key:
            return credential.Credential(secret_id, secret_key)
    return None


def get_credential_for_account(account: Dict[str, str]) -> Optional[Any]:
    """
    특정 계정의 자격증명을 반환합니다.

    - role_arn 이 정의된 경우:
        1. source_account 가 지정되어 있으면 그 source_account 의 자격증명으로 AssumeRole
        2. source_account 가 없으면 이 섹션의 direct credential (또는 main_credential)로 AssumeRole
    - role_arn 이 없는 경우:
        1. 이 섹션의 direct credential 사용 (또는 main_credential 로 폴백)
    """
    if not TENCENT_SDK_AVAILABLE:
        return None

    role_arn     = account.get("role_arn", "")
    account_name = account.get("name", account.get("id", "unknown"))

    if role_arn:
        source_name = account.get("source_account", "")
        if source_name and source_name != account_name:
            source_cred = _get_credential_by_section_name(source_name)
        else:
            source_cred = _get_direct_credential_for_section(account_name) or get_main_credential()

        if not source_cred:
            log_info_non_console(f"[Tencent] No source credential for AssumeRole: {account_name}")
            return None
        return _assume_role(source_cred, role_arn, account_name)
    else:
        return _get_direct_credential_for_section(account_name) or get_main_credential()


def _get_credential_by_section_name(section_name: str) -> Optional[Any]:
    """
    credentials 파일의 특정 섹션에서 소스 자격증명을 가져옵니다.
    다른 계정이 source_account 로 참조할 때는 direct credential 을 우선 사용합니다.
    """
    if not TENCENT_SDK_AVAILABLE:
        return None

    sections = _parse_tencent_credentials_file()
    if not sections or section_name not in sections:
        return get_main_credential()

    data = sections[section_name]
    secret_id  = data.get("secret_id", "")
    secret_key = data.get("secret_key", "")

    # 1. 소스로 사용될 때는 direct credential (secret_id/key)을 최우선으로 리턴
    if secret_id and secret_key:
        return credential.Credential(secret_id, secret_key)

    # 2. direct credential 이 없으면 이 섹션의 role_arn 으로 AssumeRole
    role_arn    = data.get("role_arn", "")
    parent_name = data.get("source_account", "")

    if role_arn:
        if parent_name and parent_name != section_name:
            parent_cred = _get_credential_by_section_name(parent_name)
            if parent_cred:
                return _assume_role(parent_cred, role_arn, section_name)
        
        source_cred = get_main_credential()
        if source_cred:
            return _assume_role(source_cred, role_arn, section_name)

    return get_main_credential()


def make_client_profile(endpoint: Optional[str] = None) -> Any:
    """Tencent SDK ClientProfile 을 생성합니다."""
    http_profile = HttpProfile()
    if endpoint:
        http_profile.endpoint = endpoint
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    return client_profile


def check_sdk_available() -> bool:
    """Tencent SDK 설치 여부를 확인합니다."""
    return TENCENT_SDK_AVAILABLE
