"""
NCP (Naver Cloud Platform) Utilities

This module provides common utilities for NCP integration including configuration management,
API error handling, output formatting, and performance optimizations following OCI patterns.
"""

import os
import yaml
import json
import time
import functools
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box

import logging
from .ncp_security_utils import ncp_data_masker, ncp_security_monitor

logger = logging.getLogger(__name__)
console = Console()


class NCPConfigError(Exception):
    """NCP 설정 관련 오류"""
    pass


def get_ncp_config_path() -> Path:
    """NCP 설정 파일 경로 반환 (hierarchical lookup)"""
    # Import here to avoid circular imports
    try:
        from src.ic.config.path_manager import ConfigPathManager
        path_manager = ConfigPathManager()
        config_path = path_manager.get_ncp_config_path()
        if config_path:
            return config_path
    except ImportError:
        logger.debug("ConfigPathManager not available, using legacy path")
    
    # Fallback to legacy path
    return Path.home() / '.ncp' / 'config'


def create_ncp_config_directory() -> Path:
    """NCP 설정 디렉터리 생성"""
    config_dir = Path.home() / '.ncp'
    config_dir.mkdir(mode=0o700, exist_ok=True)
    logger.debug(f"NCP 설정 디렉터리 생성: {config_dir}")
    return config_dir


def load_ncp_config(profile: str = 'default') -> Dict[str, Any]:
    """
    NCP 설정 파일 로드 (hierarchical config lookup using ConfigManager)
    
    Args:
        profile: 사용할 프로파일 이름
        
    Returns:
        설정 딕셔너리
    """
    try:
        # Try to use ConfigManager for hierarchical lookup
        from src.ic.config.manager import ConfigManager
        config_manager = ConfigManager()
        
        # Monitor configuration access
        config_path = get_ncp_config_path()
        if config_path:
            ncp_security_monitor.monitor_config_access(str(config_path), 'read')
        
        try:
            profile_config = config_manager.load_platform_config('ncp', profile)
            logger.debug(f"NCP 설정 로드 완료: 프로파일 '{profile}' (ConfigManager)")
            
            # Validate configuration security
            from .ncp_security_utils import validate_ncp_config_security
            if config_path:
                security_results = validate_ncp_config_security(str(config_path))
                if not security_results['secure']:
                    logger.warning(f"NCP 설정 파일 보안 문제: {security_results['issues']}")
            
            return profile_config
            
        except (FileNotFoundError, ValueError) as e:
            # Convert to NCPConfigError for consistency
            raise NCPConfigError(str(e))
            
    except ImportError:
        # Fallback to legacy method if ConfigManager is not available
        logger.debug("ConfigManager not available, using legacy config loading")
        
        config_path = get_ncp_config_path()
        
        # Monitor configuration access
        ncp_security_monitor.monitor_config_access(str(config_path), 'read')
        
        if not config_path or not config_path.exists():
            # Provide helpful error message with configuration guidance
            error_msg = f"NCP 설정 파일이 없습니다."
            if config_path:
                error_msg += f" 경로: {config_path}"
            error_msg += "\n\n설정 파일을 생성하려면 다음 명령을 실행하세요:"
            error_msg += "\n  ic config init --template ncp"
            error_msg += "\n\n또는 수동으로 다음 위치 중 하나에 설정 파일을 생성하세요:"
            error_msg += f"\n  • {Path.home() / '.ncp' / 'config.yaml'}"
            error_msg += f"\n  • {Path.home() / '.ic' / 'config' / 'ncp.yaml'}"
            raise NCPConfigError(error_msg)
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                raise NCPConfigError("NCP 설정 파일이 비어있습니다.")
            
            if profile not in config_data:
                available_profiles = list(config_data.keys())
                raise NCPConfigError(f"프로파일 '{profile}'을 찾을 수 없습니다. 사용 가능한 프로파일: {available_profiles}")
            
            profile_config = config_data[profile]
            logger.debug(f"NCP 설정 로드 완료: 프로파일 '{profile}' from {config_path} (legacy)")
            
            # Validate configuration security
            from .ncp_security_utils import validate_ncp_config_security
            security_results = validate_ncp_config_security(str(config_path))
            if not security_results['secure']:
                logger.warning(f"NCP 설정 파일 보안 문제: {security_results['issues']}")
            
            return profile_config
            
        except yaml.YAMLError as e:
            raise NCPConfigError(f"NCP 설정 파일 파싱 오류: {e}")
        except Exception as e:
            raise NCPConfigError(f"NCP 설정 로드 실패: {e}")


def validate_ncp_config(config_path: str = None) -> bool:
    """
    NCP 설정 파일 유효성 검사
    
    Args:
        config_path: 설정 파일 경로 (None이면 기본 경로 사용)
        
    Returns:
        유효성 검사 결과
    """
    if config_path is None:
        config_path = get_ncp_config_path()
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        logger.error(f"NCP 설정 파일이 없습니다: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            logger.error("NCP 설정 파일이 비어있습니다.")
            return False
        
        # 각 프로파일 검증
        for profile_name, profile_config in config_data.items():
            required_keys = ['access_key', 'secret_key']
            
            for key in required_keys:
                if key not in profile_config or not profile_config[key]:
                    logger.error(f"프로파일 '{profile_name}'에서 필수 설정이 누락되었습니다: {key}")
                    return False
            
            # 선택적 설정 기본값 확인
            if 'region' not in profile_config:
                logger.warning(f"프로파일 '{profile_name}'에 region이 설정되지 않았습니다. 기본값 'KR' 사용")
            
            if 'platform' not in profile_config:
                logger.warning(f"프로파일 '{profile_name}'에 platform이 설정되지 않았습니다. 기본값 'VPC' 사용")
        
        logger.info("NCP 설정 파일 유효성 검사 통과")
        return True
        
    except Exception as e:
        logger.error(f"NCP 설정 파일 검증 실패: {e}")
        return False


def handle_ncp_api_error(func):
    """NCP API 오류 처리 데코레이터 (보안 강화)"""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Monitor successful API call
            ncp_security_monitor.monitor_api_call(
                service=getattr(func, '__module__', 'unknown'),
                action=func.__name__,
                params=kwargs,
                response=result
            )
            return result
        except Exception as e:
            # Mask sensitive information in error messages
            masked_error = ncp_data_masker.mask_log_message(str(e))
            logger.error(f"NCP API 호출 실패: {masked_error}")
            console.print(f"[red]NCP API 오류: {masked_error}[/red]")
            
            # Monitor failed API call
            ncp_security_monitor.monitor_api_call(
                service=getattr(func, '__module__', 'unknown'),
                action=func.__name__,
                params=kwargs,
                error=e
            )
            return None
    return wrapper


def format_bytes(bytes_value: int) -> str:
    """
    바이트를 읽기 쉬운 형식으로 변환
    
    Args:
        bytes_value: 바이트 값
        
    Returns:
        포맷된 문자열 (예: "1.5 GB")
    """
    if bytes_value == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size = float(bytes_value)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def apply_status_color(status: str) -> str:
    """
    상태에 따른 색상 적용
    
    Args:
        status: 상태 문자열
        
    Returns:
        색상이 적용된 문자열
    """
    status_lower = status.lower()
    
    if status_lower in ['running', 'active', 'available', 'ok']:
        return f"[green]{status}[/green]"
    elif status_lower in ['stopped', 'terminated', 'deleted']:
        return f"[red]{status}[/red]"
    elif status_lower in ['pending', 'starting', 'stopping', 'creating']:
        return f"[yellow]{status}[/yellow]"
    elif status_lower in ['error', 'failed', 'unavailable']:
        return f"[red bold]{status}[/red bold]"
    else:
        return status


class OutputFormatter:
    """NCP 서비스 출력 포맷터 (OCI 스타일)"""
    
    @staticmethod
    def print_table(data: List[Dict], headers: List[str], title: str, empty_message: str = "(No Resources)"):
        """
        OCI 스타일 테이블 출력
        
        Args:
            data: 출력할 데이터 목록
            headers: 테이블 헤더
            title: 테이블 제목
            empty_message: 데이터가 없을 때 표시할 메시지
        """
        if not data:
            console.print(empty_message)
            return
        
        console.print(f"[bold underline]{title}[/bold underline]")
        table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                      header_style="bold", expand=False)
        table.show_edge = False
        
        # OCI 스타일 컬럼 설정
        for header in headers:
            style_opts = {}
            if header in ["Region", "Zone"]: 
                style_opts = {"style": "bold cyan"}
            elif header == "Status": 
                style_opts = {"justify": "center"}
            elif header in ["CPU", "Memory", "Storage"]: 
                style_opts = {"justify": "right"}
            elif header in ["Name", "Instance Name"]: 
                style_opts = {"overflow": "fold"}
            
            table.add_column(header, **style_opts)
        
        # 데이터 행 추가 (OCI 스타일 그룹핑)
        last_region = None
        for i, row in enumerate(data):
            region_changed = row.get("region") != last_region
            
            if i > 0 and region_changed:
                table.add_row(*["-" for _ in headers])
            
            # 행 데이터 구성
            row_values = []
            for header in headers:
                key = header.lower().replace(" ", "_")
                value = row.get(key, "-")
                
                if header == "Status":
                    value = apply_status_color(str(value))
                elif header in ["Size", "Storage"] and isinstance(value, int):
                    value = format_bytes(value)
                
                row_values.append(str(value))
            
            table.add_row(*row_values)
            last_region = row.get("region")
        
        console.print(table)
    
    @staticmethod
    def print_json(data: Any, indent: int = 2):
        """
        JSON 형식으로 출력
        
        Args:
            data: 출력할 데이터
            indent: 들여쓰기 레벨
        """
        try:
            json_str = json.dumps(data, indent=indent, ensure_ascii=False)
            console.print(json_str)
        except Exception as e:
            logger.error(f"JSON 출력 실패: {e}")
            console.print(f"[red]JSON 출력 오류: {e}[/red]")


def filter_resources_by_name(resources: List[Dict], name_filter: str, name_key: str = 'name') -> List[Dict]:
    """
    이름으로 리소스 필터링
    
    Args:
        resources: 리소스 목록
        name_filter: 필터링할 이름 (부분 일치)
        name_key: 이름 필드 키
        
    Returns:
        필터링된 리소스 목록
    """
    if not name_filter:
        return resources
    
    filtered = []
    for resource in resources:
        resource_name = resource.get(name_key, '')
        if name_filter.lower() in resource_name.lower():
            filtered.append(resource)
    
    logger.debug(f"이름 필터 '{name_filter}' 적용: {len(resources)} -> {len(filtered)} 리소스")
    return filtered


def create_ncp_config_example() -> str:
    """NCP 설정 예제 파일 내용 생성"""
    return """# NCP (Naver Cloud Platform) Configuration
# 이 파일을 ~/.ncp/config로 복사하고 실제 값으로 수정하세요.

default:
  access_key: "your-ncp-access-key"
  secret_key: "your-ncp-secret-key"
  region: "KR"  # KR, US, JP
  platform: "VPC"  # VPC or Classic

production:
  access_key: "prod-ncp-access-key"
  secret_key: "prod-ncp-secret-key"
  region: "KR"
  platform: "VPC"

development:
  access_key: "dev-ncp-access-key"
  secret_key: "dev-ncp-secret-key"
  region: "KR"
  platform: "Classic"
"""


def get_platform_display_name(platform: str) -> str:
    """플랫폼 표시 이름 반환"""
    platform_names = {
        'VPC': 'VPC Platform',
        'CLASSIC': 'Classic Platform'
    }
    return platform_names.get(platform.upper(), platform)


def validate_platform_support(platform: str, service: str) -> bool:
    """
    플랫폼별 서비스 지원 여부 확인
    
    Args:
        platform: 플랫폼 (VPC, Classic)
        service: 서비스 이름
        
    Returns:
        지원 여부
    """
    # VPC 전용 서비스
    vpc_only_services = ['vpc']
    
    if service.lower() in vpc_only_services and platform.upper() != 'VPC':
        return False
    
    return True


# Performance Monitoring and Optimization Utilities

def performance_monitor(func: Callable) -> Callable:
    """
    성능 모니터링 데코레이터
    
    API 호출 시간을 측정하고 5초 이상 걸리는 경우 로그에 기록합니다.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            
            # 5초 이상 걸리는 경우 성능 로그 기록
            if elapsed_time > 5.0:
                logger.warning(f"성능 주의: {func.__name__} 실행 시간 {elapsed_time:.2f}초")
            else:
                logger.debug(f"성능: {func.__name__} 실행 시간 {elapsed_time:.2f}초")
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"오류 발생: {func.__name__} 실행 시간 {elapsed_time:.2f}초, 오류: {e}")
            raise
    
    return wrapper


def timeout_handler(timeout_seconds: int = 30):
    """
    타임아웃 처리 데코레이터
    
    Args:
        timeout_seconds: 타임아웃 시간 (초)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_signal_handler(signum, frame):
                raise TimeoutError(f"함수 {func.__name__}이 {timeout_seconds}초 내에 완료되지 않았습니다.")
            
            # 타임아웃 설정 (Unix 시스템에서만 작동)
            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
                signal.alarm(timeout_seconds)
                
                result = func(*args, **kwargs)
                
                signal.alarm(0)  # 타임아웃 해제
                signal.signal(signal.SIGALRM, old_handler)
                
                return result
                
            except AttributeError:
                # Windows에서는 signal.SIGALRM이 지원되지 않음
                logger.debug("타임아웃 처리가 이 플랫폼에서 지원되지 않습니다.")
                return func(*args, **kwargs)
            except TimeoutError as e:
                logger.error(f"타임아웃 오류: {e}")
                console.print(f"[red]작업 타임아웃: {e}[/red]")
                raise
            finally:
                try:
                    signal.alarm(0)  # 타임아웃 해제
                except:
                    pass
        
        return wrapper
    return decorator


def paginate_api_results(api_func: Callable, page_size: int = 100, max_pages: int = None) -> List[Any]:
    """
    API 결과 페이지네이션 처리
    
    Args:
        api_func: API 호출 함수
        page_size: 페이지당 항목 수
        max_pages: 최대 페이지 수 (None이면 모든 페이지)
        
    Returns:
        모든 페이지의 결과를 합친 리스트
    """
    all_results = []
    page_no = 1
    
    while True:
        try:
            # 페이지네이션 파라미터와 함께 API 호출
            page_results = api_func(page_no=page_no, page_size=page_size)
            
            if not page_results:
                break
            
            all_results.extend(page_results)
            
            # 페이지 크기보다 적은 결과가 반환되면 마지막 페이지
            if len(page_results) < page_size:
                break
            
            # 최대 페이지 수 확인
            if max_pages and page_no >= max_pages:
                logger.warning(f"최대 페이지 수 {max_pages}에 도달했습니다.")
                break
            
            page_no += 1
            
        except Exception as e:
            logger.error(f"페이지네이션 처리 중 오류 (페이지 {page_no}): {e}")
            break
    
    logger.debug(f"페이지네이션 완료: 총 {len(all_results)}개 항목, {page_no-1}페이지")
    return all_results


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff_factor: float = 2.0):
    """
    실패 시 재시도 데코레이터
    
    Args:
        max_retries: 최대 재시도 횟수
        delay: 초기 지연 시간 (초)
        backoff_factor: 지연 시간 증가 계수
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"최대 재시도 횟수 {max_retries} 도달: {func.__name__}")
                        break
                    
                    logger.warning(f"재시도 {attempt + 1}/{max_retries}: {func.__name__} - {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
            # 모든 재시도 실패
            raise last_exception
        
        return wrapper
    return decorator


def measure_api_performance(api_calls: List[Callable]) -> Dict[str, float]:
    """
    여러 API 호출의 성능을 측정합니다.
    
    Args:
        api_calls: 측정할 API 호출 함수 목록
        
    Returns:
        각 API 호출의 실행 시간 딕셔너리
    """
    performance_stats = {}
    
    for api_call in api_calls:
        start_time = time.time()
        
        try:
            api_call()
            elapsed_time = time.time() - start_time
            performance_stats[api_call.__name__] = elapsed_time
            
            logger.debug(f"API 성능: {api_call.__name__} - {elapsed_time:.2f}초")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            performance_stats[api_call.__name__] = elapsed_time
            logger.error(f"API 오류: {api_call.__name__} - {elapsed_time:.2f}초, 오류: {e}")
    
    return performance_stats


def optimize_batch_requests(items: List[Any], batch_size: int = 50, 
                          processor_func: Callable = None) -> List[Any]:
    """
    대량 요청을 배치로 나누어 처리합니다.
    
    Args:
        items: 처리할 항목 목록
        batch_size: 배치 크기
        processor_func: 배치 처리 함수
        
    Returns:
        처리된 결과 목록
    """
    if not processor_func:
        return items
    
    results = []
    total_batches = (len(items) + batch_size - 1) // batch_size
    
    logger.debug(f"배치 처리 시작: {len(items)}개 항목을 {total_batches}개 배치로 분할")
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_number = (i // batch_size) + 1
        
        try:
            logger.debug(f"배치 {batch_number}/{total_batches} 처리 중 ({len(batch)}개 항목)")
            batch_results = processor_func(batch)
            results.extend(batch_results)
            
        except Exception as e:
            logger.error(f"배치 {batch_number} 처리 실패: {e}")
            continue
    
    logger.debug(f"배치 처리 완료: {len(results)}개 결과")
    return results


class PerformanceTracker:
    """성능 추적 클래스"""
    
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
    
    def start_timer(self, operation_name: str):
        """타이머 시작"""
        self.start_times[operation_name] = time.time()
    
    def end_timer(self, operation_name: str):
        """타이머 종료 및 메트릭 기록"""
        if operation_name in self.start_times:
            elapsed = time.time() - self.start_times[operation_name]
            self.metrics[operation_name] = elapsed
            del self.start_times[operation_name]
            
            logger.debug(f"성능 메트릭: {operation_name} - {elapsed:.2f}초")
            return elapsed
        return None
    
    def get_metrics(self) -> Dict[str, float]:
        """수집된 메트릭 반환"""
        return self.metrics.copy()
    
    def print_summary(self):
        """성능 요약 출력"""
        if not self.metrics:
            console.print("[yellow]수집된 성능 메트릭이 없습니다.[/yellow]")
            return
        
        console.print("\n[bold underline]Performance Summary[/bold underline]")
        
        table = Table(show_header=True, header_style="bold")
        table.add_column("Operation", style="cyan")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Status", justify="center")
        
        for operation, duration in sorted(self.metrics.items(), key=lambda x: x[1], reverse=True):
            status = "⚠️ Slow" if duration > 5.0 else "✅ Fast"
            duration_str = f"{duration:.2f}s"
            
            table.add_row(operation, duration_str, status)
        
        console.print(table)


# 전역 성능 추적기 인스턴스
performance_tracker = PerformanceTracker()


def configure_ncp_logging(verbose: bool = False):
    """
    NCP 모듈의 로깅을 OCI 스타일로 설정합니다.
    
    Args:
        verbose: 상세 로그 출력 여부
    """
    # NCP 관련 로거들의 레벨 설정
    ncp_loggers = [
        'ncp_module',
        'ncpgov_module', 
        'common.ncp_utils',
        'common.ncpgov_utils'
    ]
    
    # 기본적으로 WARNING 레벨로 설정 (OCI 모듈과 동일)
    log_level = logging.DEBUG if verbose else logging.WARNING
    
    for logger_name in ncp_loggers:
        ncp_logger = logging.getLogger(logger_name)
        ncp_logger.setLevel(log_level)
        
        # 콘솔 핸들러가 없으면 추가
        if not ncp_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(log_level)
            
            # 간단한 포맷터 (OCI 스타일)
            if verbose:
                formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
            else:
                formatter = logging.Formatter('%(levelname)s: %(message)s')
            
            handler.setFormatter(formatter)
            ncp_logger.addHandler(handler)
    
    logger.debug(f"NCP 로깅 설정 완료: {'verbose' if verbose else 'minimal'} 모드")


def suppress_ncp_console_logs():
    """
    NCP 모듈의 콘솔 로그 출력을 최소화합니다 (OCI 모듈과 동일한 동작).
    """
    # requests 라이브러리 로그 레벨 조정
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # NCP 클라이언트 로그 레벨 조정
    logging.getLogger('ncp_module.client').setLevel(logging.ERROR)
    logging.getLogger('ncpgov_module.client').setLevel(logging.ERROR)
    
    logger.debug("NCP 콘솔 로그 출력 최소화 완료")


def get_platform_endpoints(platform: str) -> Dict[str, str]:
    """
    플랫폼별 API 엔드포인트 반환
    
    Args:
        platform: 플랫폼 (Classic, VPC)
        
    Returns:
        엔드포인트 딕셔너리
    """
    if platform.upper() == "CLASSIC":
        return {
            "server": "https://ncloud.apigw.ntruss.com/server/v2",
            "vpc": None,  # Classic에서는 VPC 미지원
            "loadbalancer": "https://ncloud.apigw.ntruss.com/loadbalancer/v2",
            "objectstorage": "https://ncloud.apigw.ntruss.com/objectstorage/v2",
            "clouddb": "https://ncloud.apigw.ntruss.com/clouddb/v2"
        }
    elif platform.upper() == "VPC":
        return {
            "vserver": "https://ncloud.apigw.ntruss.com/vserver/v2",
            "vpc": "https://ncloud.apigw.ntruss.com/vpc/v2",
            "vloadbalancer": "https://ncloud.apigw.ntruss.com/vloadbalancer/v2",
            "objectstorage": "https://ncloud.apigw.ntruss.com/objectstorage/v2",
            "clouddb": "https://ncloud.apigw.ntruss.com/clouddb/v2"
        }
    else:
        raise ValueError(f"지원하지 않는 플랫폼: {platform}")


# 모듈 로드 시 자동으로 로그 출력 최소화
suppress_ncp_console_logs()