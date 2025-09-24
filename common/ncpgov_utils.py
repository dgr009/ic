"""
NCP Gov (Naver Cloud Platform Government) Utilities

This module provides utilities for NCP Government Cloud integration including
enhanced security features, compliance validation, and sensitive data masking.
"""

import os
import yaml
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from rich.console import Console

import logging
from .ncp_security_utils import ncp_data_masker, ncp_security_monitor, ncp_compliance_validator

logger = logging.getLogger(__name__)
console = Console()


class NCPGovConfigError(Exception):
    """NCP Gov 설정 관련 오류"""
    pass


def get_ncpgov_config_path() -> Path:
    """NCP Gov 설정 파일 경로 반환 (hierarchical lookup)"""
    # Import here to avoid circular imports
    try:
        from src.ic.config.path_manager import ConfigPathManager
        path_manager = ConfigPathManager()
        config_path = path_manager.get_ncpgov_config_path()
        if config_path:
            return config_path
    except ImportError:
        logger.debug("ConfigPathManager not available, using legacy path")
    
    # Fallback to legacy path
    return Path.home() / '.ncpgov' / 'config'


def create_ncpgov_config_directory() -> Path:
    """NCP Gov 설정 디렉터리 생성"""
    config_dir = Path.home() / '.ncpgov'
    config_dir.mkdir(mode=0o700, exist_ok=True)
    logger.debug(f"NCP Gov 설정 디렉터리 생성: {config_dir}")
    return config_dir


def load_ncpgov_config(profile: str = 'default') -> Dict[str, Any]:
    """
    NCP Gov 설정 파일 로드 (hierarchical config lookup using ConfigManager)
    
    Args:
        profile: 사용할 프로파일 이름
        
    Returns:
        설정 딕셔너리
    """
    try:
        # Try to use ConfigManager for hierarchical lookup
        from src.ic.config.manager import ConfigManager
        config_manager = ConfigManager()
        
        # Monitor configuration access for government cloud
        config_path = get_ncpgov_config_path()
        if config_path:
            ncp_security_monitor.monitor_config_access(str(config_path), 'read')
        
        try:
            profile_config = config_manager.load_platform_config('ncpgov', profile)
            logger.debug(f"NCP Gov 설정 로드 완료: 프로파일 '{profile}' (ConfigManager)")
            
            # Validate government compliance
            compliance_results = ncp_compliance_validator.validate_ncp_gov_compliance(profile_config)
            if not compliance_results['compliant']:
                logger.warning(f"NCP Gov 규정 준수 문제: {compliance_results['failed_requirements']}")
                ncp_security_monitor.log_security_event(
                    'compliance_violation',
                    {'profile': profile, 'violations': compliance_results['failed_requirements']},
                    'WARNING'
                )
            
            # Validate configuration security
            from .ncp_security_utils import validate_ncp_config_security
            if config_path:
                security_results = validate_ncp_config_security(str(config_path))
                if not security_results['secure']:
                    logger.warning(f"NCP Gov 설정 파일 보안 문제: {security_results['issues']}")
            
            return profile_config
            
        except (FileNotFoundError, ValueError) as e:
            # Convert to NCPGovConfigError for consistency
            raise NCPGovConfigError(str(e))
            
    except ImportError:
        # Fallback to legacy method if ConfigManager is not available
        logger.debug("ConfigManager not available, using legacy config loading")
        
        config_path = get_ncpgov_config_path()
        
        # Monitor configuration access for government cloud
        ncp_security_monitor.monitor_config_access(str(config_path), 'read')
        
        if not config_path or not config_path.exists():
            # Provide helpful error message with configuration guidance
            error_msg = f"NCP Gov 설정 파일이 없습니다."
            if config_path:
                error_msg += f" 경로: {config_path}"
            error_msg += "\n\n설정 파일을 생성하려면 다음 명령을 실행하세요:"
            error_msg += "\n  ic config init --template ncpgov"
            error_msg += "\n\n또는 수동으로 다음 위치 중 하나에 설정 파일을 생성하세요:"
            error_msg += f"\n  • {Path.home() / '.ncpgov' / 'config.yaml'}"
            error_msg += f"\n  • {Path.home() / '.ic' / 'config' / 'ncpgov.yaml'}"
            raise NCPGovConfigError(error_msg)
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                raise NCPGovConfigError("NCP Gov 설정 파일이 비어있습니다.")
            
            if profile not in config_data:
                available_profiles = list(config_data.keys())
                raise NCPGovConfigError(f"프로파일 '{profile}'을 찾을 수 없습니다. 사용 가능한 프로파일: {available_profiles}")
            
            profile_config = config_data[profile]
            logger.debug(f"NCP Gov 설정 로드 완료: 프로파일 '{profile}' from {config_path} (legacy)")
            
            # Validate government compliance
            compliance_results = ncp_compliance_validator.validate_ncp_gov_compliance(profile_config)
            if not compliance_results['compliant']:
                logger.warning(f"NCP Gov 규정 준수 문제: {compliance_results['failed_requirements']}")
                ncp_security_monitor.log_security_event(
                    'compliance_violation',
                    {'profile': profile, 'violations': compliance_results['failed_requirements']},
                    'WARNING'
                )
            
            # Validate configuration security
            from .ncp_security_utils import validate_ncp_config_security
            security_results = validate_ncp_config_security(str(config_path))
            if not security_results['secure']:
                logger.warning(f"NCP Gov 설정 파일 보안 문제: {security_results['issues']}")
            
            return profile_config
            
        except yaml.YAMLError as e:
            raise NCPGovConfigError(f"NCP Gov 설정 파일 파싱 오류: {e}")
        except Exception as e:
            raise NCPGovConfigError(f"NCP Gov 설정 로드 실패: {e}")


def validate_ncpgov_config(config_path: str = None) -> bool:
    """
    NCP Gov 설정 파일 유효성 검사
    
    Args:
        config_path: 설정 파일 경로 (None이면 기본 경로 사용)
        
    Returns:
        유효성 검사 결과
    """
    if config_path is None:
        config_path = get_ncpgov_config_path()
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        logger.error(f"NCP Gov 설정 파일이 없습니다: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            logger.error("NCP Gov 설정 파일이 비어있습니다.")
            return False
        
        # 각 프로파일 검증
        for profile_name, profile_config in config_data.items():
            required_keys = ['access_key', 'secret_key', 'apigw_key']
            
            for key in required_keys:
                if key not in profile_config or not profile_config[key]:
                    logger.error(f"프로파일 '{profile_name}'에서 필수 설정이 누락되었습니다: {key}")
                    return False
            
            # 정부 클라우드 보안 설정 확인
            security_settings = {
                'encryption_enabled': True,
                'audit_logging_enabled': True,
                'access_control_enabled': True
            }
            
            for setting, default_value in security_settings.items():
                if setting not in profile_config:
                    logger.warning(f"프로파일 '{profile_name}'에 보안 설정 '{setting}'이 없습니다. 기본값 {default_value} 사용")
        
        logger.info("NCP Gov 설정 파일 유효성 검사 통과")
        return True
        
    except Exception as e:
        logger.error(f"NCP Gov 설정 파일 검증 실패: {e}")
        return False


def mask_sensitive_data(data: Any, mask_patterns: List[str] = None) -> Any:
    """
    민감한 정보 마스킹 (정부 클라우드 규정 준수)
    
    Args:
        data: 마스킹할 데이터
        mask_patterns: 추가 마스킹 패턴
        
    Returns:
        마스킹된 데이터
    """
    if mask_patterns is None:
        mask_patterns = []
    
    # 기본 민감한 키워드
    default_sensitive_keys = [
        'password', 'secret', 'key', 'token', 'credential', 'auth',
        'private', 'confidential', 'ssn', 'social', 'card', 'account'
    ]
    
    sensitive_keys = default_sensitive_keys + mask_patterns
    
    def _mask_value(value: Any) -> Any:
        if isinstance(value, str):
            # 이메일 마스킹
            if '@' in value and '.' in value:
                parts = value.split('@')
                if len(parts) == 2:
                    username = parts[0]
                    domain = parts[1]
                    masked_username = username[:2] + '*' * (len(username) - 2) if len(username) > 2 else '***'
                    return f"{masked_username}@{domain}"
            
            # 전화번호 마스킹 (한국 형식)
            phone_pattern = r'(\d{2,3})-?(\d{3,4})-?(\d{4})'
            if re.match(phone_pattern, value):
                return re.sub(phone_pattern, r'\1-***-\3', value)
            
            # 일반 문자열 마스킹
            if len(value) > 4:
                return value[:2] + '*' * (len(value) - 4) + value[-2:]
            else:
                return '***'
        
        return value
    
    def _process_data(obj: Any) -> Any:
        if isinstance(obj, dict):
            masked_obj = {}
            for key, value in obj.items():
                key_lower = key.lower()
                
                # 민감한 키 확인
                if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                    masked_obj[key] = "***MASKED***"
                elif isinstance(value, (dict, list)):
                    masked_obj[key] = _process_data(value)
                else:
                    masked_obj[key] = value
            
            return masked_obj
        
        elif isinstance(obj, list):
            return [_process_data(item) for item in obj]
        
        else:
            return obj
    
    return _process_data(data)


def validate_gov_compliance(config: Dict[str, Any]) -> Dict[str, bool]:
    """
    정부 클라우드 규정 준수 검증
    
    Args:
        config: 설정 딕셔너리
        
    Returns:
        규정 준수 상태
    """
    compliance_checks = {
        'encryption_enabled': config.get('encryption_enabled', False),
        'audit_logging_enabled': config.get('audit_logging_enabled', False),
        'access_control_enabled': config.get('access_control_enabled', False),
        'apigw_key_present': bool(config.get('apigw_key')),
        'secure_region': config.get('region', '').upper() == 'KR'  # 정부 클라우드는 한국 리전만
    }
    
    # 전체 규정 준수 여부
    compliance_checks['overall_compliance'] = all(compliance_checks.values())
    
    # 규정 준수 로깅
    if compliance_checks['overall_compliance']:
        logger.info("정부 클라우드 규정 준수 검증 통과")
    else:
        failed_checks = [check for check, passed in compliance_checks.items() if not passed and check != 'overall_compliance']
        logger.warning(f"정부 클라우드 규정 준수 검증 실패: {failed_checks}")
    
    return compliance_checks


def handle_ncpgov_api_error(func):
    """NCP Gov API 오류 처리 데코레이터 (보안 강화)"""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Monitor successful government API call
            ncp_security_monitor.monitor_api_call(
                service=f"ncpgov_{getattr(func, '__module__', 'unknown')}",
                action=func.__name__,
                params=kwargs,
                response=result
            )
            return result
        except Exception as e:
            # 민감한 정보가 포함될 수 있는 오류 메시지 마스킹
            error_message = str(e)
            masked_message = ncp_data_masker.mask_log_message(error_message)
            
            logger.error(f"NCP Gov API 호출 실패: {masked_message}")
            console.print(f"[red]NCP Gov API 오류: {masked_message}[/red]")
            
            # Monitor failed government API call with high severity
            ncp_security_monitor.monitor_api_call(
                service=f"ncpgov_{getattr(func, '__module__', 'unknown')}",
                action=func.__name__,
                params=kwargs,
                error=e
            )
            ncp_security_monitor.log_security_event(
                'gov_api_failure',
                {'function': func.__name__, 'error_type': type(e).__name__},
                'ERROR'
            )
            return None
    return wrapper


def create_ncpgov_config_example() -> str:
    """NCP Gov 설정 예제 파일 내용 생성"""
    return """# NCP Gov (Naver Cloud Platform Government) Configuration
# 이 파일을 ~/.ncpgov/config로 복사하고 실제 값으로 수정하세요.
# 정부 클라우드는 보안이 강화된 환경입니다.

default:
  access_key: "your-ncpgov-access-key"
  secret_key: "your-ncpgov-secret-key"
  apigw_key: "your-ncpgov-apigw-key"
  region: "KR"  # 정부 클라우드는 KR 리전만 지원
  platform: "VPC"  # VPC 권장
  
  # 정부 클라우드 보안 설정
  encryption_enabled: true
  audit_logging_enabled: true
  access_control_enabled: true

production:
  access_key: "prod-ncpgov-access-key"
  secret_key: "prod-ncpgov-secret-key"
  apigw_key: "prod-ncpgov-apigw-key"
  region: "KR"
  platform: "VPC"
  encryption_enabled: true
  audit_logging_enabled: true
  access_control_enabled: true
"""


def log_audit_event(event_type: str, details: Dict[str, Any]):
    """
    감사 이벤트 로깅 (정부 클라우드 규정 준수)
    
    Args:
        event_type: 이벤트 타입
        details: 이벤트 상세 정보
    """
    # 민감한 정보 마스킹
    masked_details = mask_sensitive_data(details)
    
    audit_log = {
        'timestamp': logger.handlers[0].formatter.formatTime(logger.makeRecord(
            logger.name, logger.level, __file__, 0, '', (), None
        )) if logger.handlers else None,
        'event_type': event_type,
        'details': masked_details,
        'compliance': 'gov_cloud'
    }
    
    logger.info(f"[AUDIT] {event_type}: {json.dumps(audit_log, ensure_ascii=False)}")


def validate_api_response_security(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    API 응답 보안 검증 및 마스킹
    
    Args:
        response_data: API 응답 데이터
        
    Returns:
        보안 검증된 응답 데이터
    """
    # 민감한 정보 마스킹
    masked_data = mask_sensitive_data(response_data)
    
    # 감사 로그 기록
    log_audit_event('api_response_processed', {
        'response_size': len(str(response_data)),
        'masked_fields': _count_masked_fields(response_data, masked_data)
    })
    
    return masked_data


def _count_masked_fields(original: Any, masked: Any) -> int:
    """마스킹된 필드 수 계산"""
    count = 0
    
    if isinstance(original, dict) and isinstance(masked, dict):
        for key, value in masked.items():
            if value == "***MASKED***":
                count += 1
            elif isinstance(value, (dict, list)):
                count += _count_masked_fields(original.get(key), value)
    elif isinstance(original, list) and isinstance(masked, list):
        for orig_item, masked_item in zip(original, masked):
            count += _count_masked_fields(orig_item, masked_item)
    
    return count


def check_file_permissions(file_path: Path) -> bool:
    """
    파일 권한 검사 (정부 클라우드 보안 요구사항)
    
    Args:
        file_path: 검사할 파일 경로
        
    Returns:
        권한이 적절한지 여부
    """
    if not file_path.exists():
        return False
    
    # 파일 권한 확인 (600: 소유자만 읽기/쓰기)
    file_mode = file_path.stat().st_mode & 0o777
    expected_mode = 0o600
    
    if file_mode != expected_mode:
        logger.warning(f"파일 권한이 부적절합니다: {file_path} (현재: {oct(file_mode)}, 권장: {oct(expected_mode)})")
        return False
    
    return True


def secure_file_creation(file_path: Path, content: str):
    """
    보안 파일 생성 (정부 클라우드 규정 준수)
    
    Args:
        file_path: 생성할 파일 경로
        content: 파일 내용
    """
    # 디렉터리 생성 (700 권한)
    file_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    
    # 파일 생성 (600 권한)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 권한 설정 확인
    file_path.chmod(0o600)
    
    # 감사 로그 기록
    log_audit_event('secure_file_created', {
        'file_path': str(file_path),
        'permissions': '600'
    })
    
    logger.info(f"보안 파일 생성 완료: {file_path}")


def make_apigw_signature(method: str, uri: str, access_key: str, secret_key: str, timestamp: str) -> str:
    """
    NCP Gov API Gateway 서명 생성
    
    Args:
        method: HTTP 메서드
        uri: API URI
        access_key: 액세스 키
        secret_key: 시크릿 키
        timestamp: 타임스탬프
        
    Returns:
        생성된 서명
    """
    import hmac
    import hashlib
    import base64
    
    # 서명 문자열 생성
    message = f"{method} {uri}\n{timestamp}\n{access_key}"
    
    # HMAC-SHA256 서명 생성
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    # Base64 인코딩
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    # 감사 로그 기록 (민감한 정보 제외)
    log_audit_event('apigw_signature_generated', {
        'method': method,
        'uri': uri,
        'timestamp': timestamp
    })
    
    return signature_b64


def get_gov_security_headers() -> Dict[str, str]:
    """정부 클라우드 보안 헤더 반환"""
    return {
        'x-ncp-gov-compliance': 'enabled',
        'x-ncp-gov-security-level': 'high',
        'x-ncp-gov-audit-required': 'true'
    }