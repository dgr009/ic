import logging
import os
from datetime import datetime
from functools import wraps
from rich.console import Console
from rich.traceback import install
from rich.table import Table, box

# Try to import the new logging system, fallback to old system if not available
try:
    from ic.core.logging import get_logger
    NEW_LOGGING_AVAILABLE = True
except ImportError:
    NEW_LOGGING_AVAILABLE = False

console = Console()
install(show_locals=True)

# Initialize logger based on availability
if NEW_LOGGING_AVAILABLE:
    # Use new ICLogger system
    ic_logger = get_logger()
    logger = ic_logger.get_logger()
else:
    # Fallback to old logging system
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, "../logs")
    os.makedirs(log_dir, exist_ok=True)

    # 너무 자세한 파일명:라인번호를 매번 찍지 않도록 로그 포맷 간소화
    LOG_FORMAT = "%(asctime)s [%(levelname)s] - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.FileHandler(f"{log_dir}/ic_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("ic")

    # 필요 시, boto3나 paramiko의 로그레벨을 별도 조정 가능
    # logging.getLogger("boto3").setLevel(logging.WARNING)
    # logging.getLogger("botocore").setLevel(logging.WARNING)

    # 혹시 중복 핸들러가 붙으면 정리
    if len(logger.handlers) > 1:
        logger.handlers = [logger.handlers[-1]]
    
    ic_logger = None

def log_info_non_console(message: str):
    """INFO 레벨 로그 출력 + 콘솔 미표시"""
    if NEW_LOGGING_AVAILABLE and ic_logger:
        ic_logger.log_info_file_only(message)
    else:
        logger.info(message)

def log_info(message: str):
    """INFO 레벨 로그 출력 + 콘솔 표시"""
    if NEW_LOGGING_AVAILABLE and ic_logger:
        # New system: INFO goes to file only, but we can show on console for backward compatibility
        ic_logger.log_info_file_only(message)
        console.print(f"[bold cyan]INFO:[/bold cyan] {message}")
    else:
        logger.info(message)
        # 콘솔에만 심플하게 표시
        if logger.level <= logging.INFO:
            console.print(f"[bold cyan]INFO:[/bold cyan] {message}")

def log_error(message: str):
    """ERROR 레벨 로그 출력 + 콘솔 표시"""
    if NEW_LOGGING_AVAILABLE and ic_logger:
        ic_logger.log_error(message)
    else:
        logger.error(message)
        console.print(f"[bold red]ERROR:[/bold red] {message}")

def log_exception(e: Exception):
    """
    예외 로깅:
      - logger.exception() 사용 → 실제 오류 위치가 표준 Traceback으로 표시됨
      - 콘솔에는 짧은 메시지만 출력 (원하면 traceback도 함께 볼 수 있음)
    """
    if NEW_LOGGING_AVAILABLE and ic_logger:
        # Log the exception with traceback to file
        ic_logger.get_logger().exception(e)
        # Show error on console
        ic_logger.log_error(f"Exception: {e}")
    else:
        # logger.exception()은 자동으로 traceback을 로그에 남겨주고,
        # 실제 발생 소스파일/라인 정보를 출력합니다.
        logger.exception(e)
        # 콘솔에는 짧은 메시지만 띄울 수도 있고, 필요시 traceback도 rich로 출력 가능
        console.print(f"[bold red]Exception:[/bold red] {e}")

def log_decorator(func):
    """함수 진입/예외 등을 간단히 로깅하는 데코레이터 예시."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 여기서 바로 log_exception을 호출하면 traceback이 사용자 코드 위치부터 표시됨
            log_exception(e)
            raise e
    return wrapper


def print_table(title, columns, data):
    """테이블 형식의 로그 출력."""
    table = Table(title=title, show_header=True, header_style="bold blue")
    for column in columns:
        table.add_column(column)

    for row in data:
        table.add_row(*[str(item) for item in row])

    console.print(table)

def log_env_table(env_used: dict):
    if not env_used:
        return

    table = Table(title="Env 나열", box=box.SIMPLE_HEAD, show_header=False, title_justify="left")
    # show_header=False이면 컬럼 헤더를 안 띄움
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    for k, v in sorted(env_used.items()):
        table.add_row(k, v)

    console.print(table)

def log_env_short(env_used: dict):
    if not env_used:
        return

    # key, value에 다른 색상 적용
    # 여러 개면 ", "로 구분
    items_str = []
    for k, v in sorted(env_used.items()):
        items_str.append(f"[cyan]{k}[/cyan]=[green]{v}[/green]")
    # 한 줄로 조인
    joined = ", ".join(items_str)

    # 출력
    console.print(f"[bold white]Env 나열:[/bold white] {joined}")

def log_args_short(args):
    """인자를 짧게 요약해서 로깅"""
    if NEW_LOGGING_AVAILABLE and ic_logger:
        # Use new logging system's log_args method
        ic_logger.log_args(args)
    else:
        # Fallback to old system
        args_dict = {k: v for k, v in vars(args).items() if not k.startswith('_') and k != 'func'}
        
        # None 값을 "None(*)" 으로 변경
        pretty_args = {k: (v if v is not None else "default") for k, v in args_dict.items()}
        
        args_str = ", ".join(f"{k}={v}" for k, v in pretty_args.items())
        log_info(f"Args 나열: {args_str}")

def cleanup_old_logs():
    """Clean up old log files beyond retention limit."""
    if NEW_LOGGING_AVAILABLE and ic_logger:
        ic_logger.cleanup_old_logs()
    else:
        # Fallback cleanup for old system
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(script_dir, "../logs")
            
            if not os.path.exists(log_dir):
                return
            
            import glob
            from pathlib import Path
            
            # Find all IC log files
            log_files = glob.glob(os.path.join(log_dir, "ic_*.log*"))
            
            # Sort by modification time (oldest first)
            log_files.sort(key=lambda f: os.path.getmtime(f))
            
            # Keep only the last 30 files
            max_files = 30
            if len(log_files) > max_files:
                files_to_remove = log_files[:-max_files]
                for log_file in files_to_remove:
                    try:
                        os.remove(log_file)
                        logger.debug(f"Removed old log file: {log_file}")
                    except OSError as e:
                        logger.warning(f"Failed to remove log file {log_file}: {e}")
                        
        except Exception as e:
            logger.warning(f"Failed to cleanup old logs: {e}")

def get_log_file_path():
    """Get current log file path."""
    if NEW_LOGGING_AVAILABLE and ic_logger:
        return ic_logger.get_log_file_path()
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(script_dir, "../logs")
        return os.path.join(log_dir, f"ic_{datetime.now().strftime('%Y%m%d')}.log")

def init_logging_with_config(config):
    """Initialize logging system with configuration."""
    global ic_logger, logger
    
    if NEW_LOGGING_AVAILABLE:
        from ic.core.logging import init_logger
        ic_logger = init_logger(config)
        logger = ic_logger.get_logger()
        return ic_logger
    else:
        # Configuration not supported in old system
        return None

# 로그아웃은 사용하지 않으므로 제거
# def log_logout(message):