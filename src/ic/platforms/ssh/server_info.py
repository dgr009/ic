#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import getpass
import concurrent.futures
import paramiko
# Paramiko 내부 디버그 로그를 별도 파일로 남겨 문제 파악을 쉽게 함
# paramiko.util.log_to_file("ssh_paramiko_debug.log")

from ic.config.manager import ConfigManager
from ic.core.logging import ICLogger
from rich.table import Table
from rich.console import Console
from common.progress_decorator import concurrent_progress, ManualProgress

console = Console()
# -----------------------------------------------------------------------------
# 설정 관리자 초기화
# -----------------------------------------------------------------------------
_config_manager = ConfigManager()
_config = _config_manager.load_all_configs()
_ssh_config = _config.get('ssh', {})

# IC 로거 시스템 사용
_ic_logger = ICLogger(_config)
logger = _ic_logger.get_logger()

SSH_CONFIG_FILE = _ssh_config.get('config_file', "~/.ssh/config")
SSH_TIMEOUT = int(_ssh_config.get('timeout', 5))
MAX_WORKER = int(_ssh_config.get('workers', 20))

# Skip prefixes 설정 (secrets에서 가져오기)
skip_prefixes = _ssh_config.get('skip_prefixes', ['git'])
if isinstance(skip_prefixes, str):
    SSH_SKIP_PREFIXES = [p.strip().lower() for p in skip_prefixes.split(",") if p.strip()]
else:
    SSH_SKIP_PREFIXES = [p.strip().lower() for p in skip_prefixes if p.strip()]

# -----------------------------------------------------------------------------
# 유틸 함수
# -----------------------------------------------------------------------------
def color_percentage(value: str) -> str:
    if value in ["N/A", "-", None]:
        return value or "N/A"
    try:
        stripped = value.strip('%')
        percentage = float(stripped)
        if percentage >= 85:
            return f"[red]{value}[/red]"
        elif percentage >= 60:
            return f"[yellow]{value}[/yellow]"
        else:
            return f"[green]{value}[/green]"
    except ValueError:
        return value

def parse_memory_value(value: str) -> float:
    if value.endswith('Gi'):
        return float(value[:-2])
    elif value.endswith('Mi'):
        return float(value[:-2]) / 1024
    elif value.endswith('Ki'):
        return float(value[:-2]) / 1024 / 1024
    elif value.endswith('G'):
        return float(value[:-1])
    elif value.endswith('M'):
        return float(value[:-1]) / 1024
    elif value.endswith('K'):
        return float(value[:-1]) / 1024 / 1024
    else:
        return float(value)

# -----------------------------------------------------------------------------
# SSH 처리 클래스
# -----------------------------------------------------------------------------
class ServerInfoRetriever:
    def __init__(self, hostname: str, username: str, private_key_path: str, port: int) -> None:
        self.hostname = hostname
        self.username = username
        self.private_key_path = private_key_path
        self.port = port
        self.ssh = self._establish_ssh_connection()

    def _establish_ssh_connection(self):  # -> paramiko.SSHClient | None
        """SSH 연결을 시도하고 실패 시 상세 로그를 남깁니다."""
        try:
            private_key = paramiko.RSAKey(filename=self.private_key_path)
        except Exception:
            # log_exception(key_exc)
            logger.error(
                f"[KEY-ERROR] {self.hostname}:{self.port} - 키 로드 실패 ({self.private_key_path})"
            )
            return None

        try:
            ssh = paramiko.SSHClient()
            # 보안 강화: 알려진 호스트만 허용하되, 개발/테스트 환경에서는 경고와 함께 허용
            import os
            if os.getenv('IC_TEST_MODE') or os.getenv('IC_DEV_MODE'):
                ssh.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507
            else:
                ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
            ssh.connect(
                self.hostname,
                username=self.username,
                pkey=private_key,
                port=self.port,
                timeout=SSH_TIMEOUT,
            )
            # log_info(f"SSH 연결 성공: {self.hostname}")
            return ssh
        except paramiko.SSHException as e:
            # log_exception(e)
            # log_error(f"SSH connection failed for {self.hostname}: {e}")
            return None
        except Exception as e:
            # log_exception(e)
            # log_error(f"Failed to establish SSH connection for {self.hostname}: {e}")
            return None

    def _execute_ssh_command(self, command: str) -> str:
        if not self.ssh:
            return None
        try:
            _, stdout, _ = self.ssh.exec_command(command, get_pty=False)
            raw_output = stdout.read().decode('utf-8', errors='replace')

            banner_start_chars = ("_", "|", "'", "^", "-")
            filtered_lines = []
            for line in raw_output.split('\n'):
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                if stripped_line[0] in banner_start_chars:
                    continue
                filtered_lines.append(stripped_line)

            filtered_output = "\n".join(filtered_lines)
            # log_error(f"[{self.hostname}] Command: {command}\nFiltered output:\n{filtered_output}")
            return filtered_output
        except Exception as e:
            # 상세 로그 남김 (호스트, 커맨드, 예외)
            # log_exception(e)
            logger.error(
                f"[CMD-FAIL] {self.hostname}:{self.port} - '{command}' 실행 실패: {e}"
            )
            return None
        

    def get_device_info(self): # -> tuple or None:
        if self.ssh is None:
            return None

        # 디스크 Usage
        df_root_output = self._execute_ssh_command('df -h /')        
        df_app_output = self._execute_ssh_command('df -h /app')
        df_data_output = self._execute_ssh_command('df -h /data')
        
        # CPU
        cpu_num_output = self._execute_ssh_command('nproc')
        cpu_output = self._execute_ssh_command('top -bn1 | grep "Cpu(s)"')

        # 메모리
        memory_output = self._execute_ssh_command('free -h')

        # 기본 인터페이스 & IP
        default_interface = self._execute_ssh_command("sudo ip route | grep default | awk '{print $5}' | head -n 1")
        ip_output = None
        if default_interface:
            ip_output = self._execute_ssh_command(f"sudo ip addr show {default_interface} | grep 'inet ' | awk '{{print $2}}' | cut -d'/' -f1")


        # 결과 검증
        if None in [
            df_root_output, df_app_output, df_data_output,
            cpu_num_output, cpu_output, memory_output, ip_output
        ]:
            # log_error(f"정보 수집 실패: {self.hostname}")
            return None

        return (
            df_root_output,
            df_app_output,
            df_data_output,
            cpu_num_output,
            cpu_output,
            memory_output,
            ip_output
        )

    def close_connection(self) -> None:
        """
        SSH 연결 해제
        """
        if self.ssh:
            self.ssh.close()
            # log_info(f"SSH 연결 종료: {self.hostname}")

# -----------------------------------------------------------------------------
# SSH Config 파싱
# -----------------------------------------------------------------------------
def parse_ssh_config() -> list:
    config_path = os.path.expanduser(SSH_CONFIG_FILE)
    ssh_config = paramiko.SSHConfig()

    servers = []
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            ssh_config.parse(f)
    except FileNotFoundError:
        logger.exception(f".ssh/config 파일을 찾을 수 없음: {config_path}")
        console.print(f"[bold red]에러:[/bold red] .ssh/config 파일을 찾을 수 없습니다: {config_path}")
        return servers

    for host_info in ssh_config.get_hostnames():
        if '*' in host_info:
            continue

        # 호스트 접두사 필터링
        lower_host = host_info.lower()
        if any(lower_host.startswith(pref) for pref in SSH_SKIP_PREFIXES):
            # log_info(f"[SKIP] 접두사 제외 규칙에 의해 무시: {host_info}")
            continue

        config = ssh_config.lookup(host_info)

        identity_files = config.get("identityfile", [])
        if identity_files:
            private_key = identity_files[0]
        else:
            # 기본 키 경로 설정
            default_key_dir = _ssh_config.get('key_dir', '~/.ssh')
            default_key_dir = os.path.expanduser(default_key_dir)
            private_key = os.path.join(default_key_dir, 'id_rsa')

        user = config.get("user", getpass.getuser())
        port = config.get("port", 22)

        servers.append({
            "servername": host_info,
            "hostname": config.get("hostname"),
            "username": user,
            "port": int(port),
            "private_key_path": private_key
        })

    total_hosts = len(list(ssh_config.get_hostnames())) - 1  # '*' 제외
    excluded_hosts = total_hosts - len(servers)
    console.print(f"[cyan]ssh_config 파싱 완료:[/cyan] [green]{len(servers)}개 호스트,[/green] [red]제외 {excluded_hosts}개)[/red]")
    console.print(f"[cyan]Skip prefixes:[/cyan] {SSH_SKIP_PREFIXES}")
    return servers

# -----------------------------------------------------------------------------
# 서버 정보 수집 함수
# -----------------------------------------------------------------------------
def fetch_server_info(cfg: dict):
    """
    단일 서버 정보 수집 → (servername, hostname, ip_output, df_root, df_app, df_data, cpu_num, cpu_out, mem_out)
    """
    try:
        retriever = ServerInfoRetriever(
            cfg["hostname"],
            cfg["username"],
            cfg["private_key_path"],
            cfg["port"]
        )
        # log_info(f"[{cfg['servername']}] 장치 정보 수집 시작")
        device_info = retriever.get_device_info()
        # log_info(f"[{cfg['servername']}] 장치 정보 수집 완료")
        retriever.close_connection()

        if device_info is None:
            # log_error(
            #     f"[FETCH-FAIL] {cfg['servername']} ({cfg['hostname']}) - 장치 정보 수집 실패"
            # )
            return (
                cfg["servername"],
                cfg["hostname"],
                "Connection Fail",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
            )
        else:
            df_root, df_app, df_data, cpu_num, cpu_out, mem_out, ip_out = device_info
            return (
                cfg['servername'],
                cfg['hostname'],
                ip_out,
                df_root,
                df_app,
                df_data,
                cpu_num,
                cpu_out,
                mem_out
            )
    except Exception as e:
        # Handle any unexpected errors during server info collection
        logger.error(f"[FETCH-ERROR] {cfg['servername']} ({cfg['hostname']}) - Unexpected error: {e}")
        return (
            cfg["servername"],
            cfg["hostname"],
            "Connection Fail",
            "N/A",
            "N/A",
            "N/A",
            "N/A",
            "N/A",
            "N/A",
        )


@concurrent_progress("Collecting SSH server information", max_workers=MAX_WORKER)
def collect_all_server_info(server_configs: list) -> list:
    """
    Collect information from all servers using concurrent execution with progress tracking.
    
    Args:
        server_configs: List of server configuration dictionaries
        
    Returns:
        List of server information tuples
    """
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKER) as executor:
        # Submit all tasks
        future_to_server = {
            executor.submit(fetch_server_info, config): config 
            for config in server_configs
        }
        
        # Process completed tasks
        for future in concurrent.futures.as_completed(future_to_server):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                cfg = future_to_server[future]
                logger.exception(e)
                console.print(f"[bold red]에러:[/bold red] {cfg['servername']} 처리 중 오류: {e}")
                # Add failed result to maintain consistency
                results.append((
                    cfg["servername"],
                    cfg["hostname"],
                    "Connection Fail",
                    "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"
                ))
    
    return results

# -----------------------------------------------------------------------------
# 결과 파싱
# -----------------------------------------------------------------------------
def parse_df_output(df_output: str) -> tuple:
    """
    df -h 명령 결과 문자열에서 총 용량, 사용 퍼센트만 파싱.

    Args:
        df_output (str): df -h 결과 문자열

    Returns:
        tuple: (total_capacity, usage_percentage)
    """
    total_capacity = '-'
    usage_percentage = '-'
    if not df_output:
        return total_capacity, usage_percentage

    lines = df_output.split('\n')
    for line in lines:
        if '/' in line:
            df_columns = re.split(r'\s+', line)
            if len(df_columns) >= 5:
                total_capacity = df_columns[1]
                usage_percentage = df_columns[4]
                break
    return total_capacity, usage_percentage


def parse_cpu_usage(cpu_output: str) -> str:
    """
    top -bn1 | grep "Cpu(s)" 결과에서 idle 값을 추출해 CPU 사용률(=100-idle)을 구함

    Args:
        cpu_output (str): "Cpu(s):  2.5 us,  1.0 sy, 96.5 id, ..." 형태의 문자열

    Returns:
        str: "15.0%" 형태의 CPU 사용률
    """
    if not cpu_output:
        return "N/A"
    cpu_output = cpu_output.replace(',', ' ')
    cpu_columns = re.split(r'\s+', cpu_output)
    try:
        idle_cpu = float(cpu_columns[7])
        usage = 100.0 - idle_cpu
        return f"{usage:.1f}%"
    except:
        return "N/A"


def parse_memory_info(memory_output: str) -> tuple:
    """
    free -h 결과에서 총 메모리, 메모리 사용 퍼센트 등을 파싱

    Args:
        memory_output (str): free -h 명령 결과 문자열

    Returns:
        tuple: (total_memory_str, memory_percentage_str)
    """
    if not memory_output:
        return ("N/A", "N/A")

    lines = memory_output.split('\n')
    try:
        # 보통 lines[1]이 Mem: ... 형태
        memory_columns = re.split(r'\s+', lines[1])
        total_memory_str = memory_columns[1]
        used_memory_str = memory_columns[2]

        total_memory = parse_memory_value(total_memory_str)
        used_memory = parse_memory_value(used_memory_str)

        if total_memory > 0:
            memory_percentage = (used_memory / total_memory) * 100
        else:
            memory_percentage = 0.0
        return (total_memory_str, f"{memory_percentage:.2f}%")
    except:
        return ("N/A", "N/A")

# -----------------------------------------------------------------------------
# 결과 출력
# -----------------------------------------------------------------------------
def display_server_info(results: list, headers: list) -> None:
    """
    서버 정보 결과를 rich.Table로 출력한다.

    Args:
        results (list): fetch_server_info를 통해 수집된 튜플들의 리스트
        headers (list): 컬럼 헤더
    """
    # 예시: [22, 15, 15, 7, 6, 8, 7, 9, 7, 4, 9, 8, 7]
    column_widths = [22, 15, 15, 7, 6, 8, 7, 9, 7, 4, 9, 8, 7]

    table = Table(title="서버 정보 결과", show_lines=False)
    for idx, header in enumerate(headers):
        table.add_column(header, width=column_widths[idx], no_wrap=True)

    sorted_result = sorted(results, key=lambda x: x[0])
    failed_servers = []

    for data in sorted_result:
        (servername, hostname, ip_output,
         df_root_output, df_app_output, df_data_output,
         cpu_num_output, cpu_output, memory_output) = data

        if ip_output == "Connection Fail":
            # 연결 실패
            root_total_capacity = root_percentage = "N/A"
            app_total_capacity = app_percentage = "N/A"
            data_total_capacity = data_percentage = "N/A"
            cpu_num = "N/A"
            cpu_usage = "N/A"
            total_memory_str = "N/A"
            memory_percentage = "N/A"
            ip_colored = f"[red]{ip_output}[/red]"
            failed_servers.append(data)
        else:
            # 디스크
            root_total_capacity, root_percentage = parse_df_output(df_root_output)
            app_total_capacity, app_percentage = parse_df_output(df_app_output)
            data_total_capacity, data_percentage = parse_df_output(df_data_output)

            # CPU
            cpu_num = cpu_num_output
            cpu_usage = parse_cpu_usage(cpu_output)

            # 메모리
            total_memory_str, memory_percentage = parse_memory_info(memory_output)

            # IP 색상
            ip_colored = f"[blue]{ip_output}[/blue]"

        # 색상 적용
        root_percentage_colored = color_percentage(root_percentage)
        app_percentage_colored = color_percentage(app_percentage)
        data_percentage_colored = color_percentage(data_percentage)
        cpu_usage_colored = color_percentage(cpu_usage)
        memory_percentage_colored = color_percentage(memory_percentage)

        table.add_row(
            servername,
            hostname,
            ip_colored,
            root_total_capacity,
            root_percentage_colored,
            app_total_capacity,
            app_percentage_colored,
            data_total_capacity,
            data_percentage_colored,
            str(cpu_num),
            cpu_usage_colored,
            total_memory_str,
            memory_percentage_colored
        )

    if failed_servers:
        console.print("\n[red]문제가 있는 서버 목록:[/red]")
        for fs in failed_servers:
            console.print(f"- {fs[0]} ({fs[1]})")

    console.print(table)

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
def main(args) -> None:
    import time
    
    # log_info("server_info 스크립트 시작")
    server_configs = parse_ssh_config()
    if not server_configs:
        logger.error("서버 설정이 비어있어 종료합니다.")
        return

    # "Memory"로 헤더 변경
    headers = [
        "Server Name",
        "Access IP",
        "Internal IP",
        "/ Tot",
        "/ %",
        "/app Tot",
        "/app %",
        "/data Tot",
        "/data %",
        "vCPU",
        "CPU %",
        "Memory",
        "Mem %"
    ]

    total_servers = len(server_configs)
    start_time = time.time()
    
    # Use the new progress decorator system for concurrent server information collection
    console.print(f"[cyan]Starting collection from {total_servers} servers...[/cyan]")
    
    try:
        results = collect_all_server_info(server_configs)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Count successful vs failed connections
        failed_count = sum(1 for result in results if result[2] == "Connection Fail")
        success_count = total_servers - failed_count
        
        console.print(f"[green]✓ Collection completed in {processing_time:.2f}s[/green]")
        console.print(f"[cyan]Results:[/cyan] [green]{success_count} successful[/green], [red]{failed_count} failed[/red]")
        
    except Exception as e:
        logger.exception(f"Error during server information collection: {e}")
        console.print(f"[bold red]에러:[/bold red] 서버 정보 수집 중 예기치 못한 오류가 발생했습니다: {e}")
        return

    display_server_info(results, headers)
    # log_info("server_info 스크립트 완료")

# if __name__ == "__main__":
#     try:
#         main()
#     except Exception as e:
#         logger.exception(f"에러 발생: {e}")
#         console.print(f"[bold red]에러:[/bold red] 스크립트 실행 중 예기치 못한 오류가 발생했습니다: {e}")
#         exit(1)