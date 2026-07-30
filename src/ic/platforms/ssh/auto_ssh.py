#!/usr/bin/env python3
"""자동 SSH 접속을 위한 유틸리티 스크립트입니다."""

import os
import socket
import ipaddress
import netifaces
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import paramiko
from paramiko.config import SSHConfig
from tqdm import tqdm
try:
    from ic.config.manager import ConfigManager
    from ic.core.logging import ICLogger
except ImportError:
    try:
        from ic.config.manager import ConfigManager
        from ic.core.logging import ICLogger
    except ImportError:
        # Legacy fallback for development
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        from ic.config.manager import ConfigManager
        from ic.core.logging import ICLogger

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from pathlib import Path
import logging

# 설정 관리자 초기화
_config_manager = ConfigManager()
_config = _config_manager.load_all_configs()
_ssh_config = _config.get('ssh', {})

def get_config_var(key, default=""):
    """설정에서 값을 가져오고 값에 포함된 주석을 제거합니다."""
    value = _ssh_config.get(key.lower(), default)
    return str(value).split('#')[0].strip()

# 콘솔 및 로거 설정
console = Console()

# IC 로거 시스템 사용
_ic_logger = ICLogger(_config)
logger = _ic_logger.get_logger()
logging.getLogger('paramiko').setLevel(logging.ERROR)

# SSH 설정
DEFAULT_KEY_DIR = _ssh_config.get('key_dir', os.path.expanduser("~/aws-key"))
SSH_CONFIG_FILE = _ssh_config.get('config_file', os.path.expanduser("~/.ssh/config"))
SSH_MAX_WORKER = int(_ssh_config.get('workers', 70))
PORT_OPEN_TIMEOUT = float(_ssh_config.get('port_timeout', 0.5))
SSH_TIMEOUT = float(_ssh_config.get('timeout', 3))


from rich.prompt import Prompt, Confirm
from rich.prompt import IntPrompt

def select_ssh_user(default="ubuntu"):
    """SSH 접속 사용자 선택 또는 직접 입력"""
    user_choices = ["ubuntu", "root", "ec2-user", "centos", "appuser", "직접 입력"]
    console.print("[bold]SSH 사용자 선택:[/bold]")
    for idx, user in enumerate(user_choices, 1):
        console.print(f"[cyan]{idx}.[/cyan] {user}")
    selected = Prompt.ask("번호를 선택하세요", choices=[str(i) for i in range(1, len(user_choices)+1)], default="1")
    choice = user_choices[int(selected)-1]
    if choice == "직접 입력":
        return Prompt.ask("사용자명을 입력하세요", default=default)
    return choice

def select_key_file(default_key_dir):
    """키 파일을 자동으로 탐색하고 목록 중 선택하거나 직접 입력할 수 있음"""
    try:
        key_dir = Path(os.path.expanduser(default_key_dir))
        if not key_dir.exists():
            console.print(f"[red]경로가 존재하지 않음: {key_dir}[/red]")
            return None
        key_files = sorted([f for f in key_dir.glob("*.pem")])
        if not key_files:
            console.print(f"[yellow]{key_dir} 내 키 파일이 없습니다.[/yellow]")
            return Prompt.ask("직접 키 파일 경로를 입력하세요")

        console.print("[bold]SSH 키 파일 선택:[/bold]")
        for idx, f in enumerate(key_files, 1):
            console.print(f"[cyan]{idx}.[/cyan] {f.name}")
        console.print(f"[cyan]{len(key_files)+1}.[/cyan] 직접 입력")

        selected = Prompt.ask("번호를 선택하세요", choices=[str(i) for i in range(1, len(key_files)+2)], default="1")
        if int(selected) == len(key_files)+1:
            return Prompt.ask("직접 경로 입력")
        return str(key_files[int(selected)-1])
    except Exception as e:
        logger.error("키 파일 선택 중 오류: %s", e)
        return None

def prompt_port(default_port=22):
    """사용자에게 포트를 물어보거나 기본값 사용"""
    return IntPrompt.ask("SSH 포트를 입력하세요", default=default_port)

def scan_open_hosts(cidr):
    """포트가 열려 있는 IP 목록을 스캔하여 반환합니다."""
    ip_list = generate_ip_range(cidr)
    open_ips = []

    with ThreadPoolExecutor(max_workers=SSH_MAX_WORKER) as executor:
        futures = {executor.submit(is_port_open, ip): ip for ip in ip_list}
        for future in tqdm(futures, desc="🔍 열려있는 호스트 스캔 중"):
            ip = futures[future]
            try:
                if future.result():
                    open_ips.append(ip)
            except Exception as e:
                logger.warning("IP 처리 중 예외 (%s): %s", ip, e)

    return open_ips

def get_local_ip():
    """자신의 IP를 반환합니다."""
    try:
        gw_iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
        iface_info = netifaces.ifaddresses(gw_iface)[netifaces.AF_INET][0]
        return iface_info['addr']
    except Exception as e:
        logger.warning("로컬 IP 확인 실패: %s", e)
        return None

def get_existing_hosts():
    """기존에 등록된 호스트 IP를 SSH 설정에서 불러옵니다."""
    existing_ips = set()
    try:
        if os.path.exists(SSH_CONFIG_FILE):
            with open(SSH_CONFIG_FILE, "r") as f:
                for line in f:
                    if "Hostname" in line:
                        ip = line.strip().split()[-1]
                        existing_ips.add(ip)
    except IOError as e:
        logger.exception("SSH 설정 파일 읽기 실패: %s", str(e))
        console.print(f"[bold red]SSH 설정 파일 읽기 실패:[/bold red] {e}")
    return existing_ips


def is_port_open(ip, port=22):
    """지정된 IP와 포트가 열려 있는지 확인합니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(PORT_OPEN_TIMEOUT)
        try:
            result = sock.connect_ex((str(ip), port))
            return result == 0
        except Exception as e:
            logger.debug("포트 확인 중 예외 발생: %s", str(e))
            return False


def generate_ip_range(cidr):
    """CIDR 범위 내 IP 목록을 생성합니다."""
    try:
        network = ipaddress.IPv4Network(cidr)
        return [str(ip) for ip in network.hosts()]
    except ValueError as e:
        logger.error("유효하지 않은 CIDR: %s", cidr)
        console.print(f"[bold red]CIDR 에러:[/bold red] {e}")
        return []


def get_hostname_via_ssh(ip, key_path, user, port):
    """SSH를 통해 호스트명(hostname)을 가져옵니다."""
    try:
        ssh = paramiko.SSHClient()
        # 보안 정책 설정: 설정 파일에서 정책을 읽어오거나 환경 변수 확인
        import os
        try:
            from ic.config.manager import ConfigManager
        except ImportError:
            try:
                from ic.config.manager import ConfigManager
            except ImportError:
                # Legacy fallback for development
                import sys
                import os
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
                from ic.config.manager import ConfigManager
        _config_manager = ConfigManager()
        _config = _config_manager.load_all_configs()
        _ssh_config = _config.get('ssh', {})
        host_key_policy = _ssh_config.get('host_key_policy', 'auto').lower()
        
        if os.getenv('IC_TEST_MODE') or os.getenv('IC_DEV_MODE'):
            ssh.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507
        elif host_key_policy == 'reject':
            ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        elif host_key_policy == 'warning':
            ssh.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507
        elif host_key_policy == 'auto':
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
        else:
            # 기본값: 보안을 위해 경고 정책 사용
            ssh.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507
        ssh.connect(str(ip), username=user, key_filename=key_path, port=port, timeout=SSH_TIMEOUT)
        stdin, stdout, stderr = ssh.exec_command("hostname")
        hostname = stdout.read().decode().strip()
        ssh.close()
        return hostname
    except Exception as e:
        logger.warning("SSH 실패 (%s): %s", ip, str(e))
        return None

def update_ssh_config(ip, hostname, key_path, user, port):
    """SSH 설정 파일에 새로운 호스트 항목을 추가합니다."""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(SSH_CONFIG_FILE, "a") as f:
            f.write(f"\n# Added by auto_ssh.py on {current_time}\n")
            f.write(f"\nHost {hostname}\n")
            f.write(f"    Hostname {ip}\n")
            f.write(f"    User {user}\n")
            f.write(f"    Port {port}\n")
            f.write(f"    IdentityFile {key_path}\n")
        logger.info("SSH config 업데이트: %s (%s)", hostname, ip)
    except Exception as e:
        logger.error("SSH config 업데이트 실패: %s", str(e))


# def scan_and_add_hosts(cidr, key_path, user, port):
#     """CIDR 대역을 스캔하여 포트가 열려 있고 등록되지 않은 호스트를 추가합니다."""
#     existing_hosts = get_existing_hosts()
#     ip_list = generate_ip_range(cidr)
#     results = []

#     with ThreadPoolExecutor(max_workers=SSH_MAX_WORKER) as executor:
#         futures = {
#             executor.submit(is_port_open, ip): ip for ip in ip_list if ip not in existing_hosts
#         }
#         for future in tqdm(futures, desc="Scanning"):
#             ip = futures[future]
#             try:
#                 if future.result():
#                     hostname = get_hostname_via_ssh(ip, key_path)
#                     if hostname:
#                         update_ssh_config(ip, hostname, key_path)
#                         results.append({ "IP": ip, "Hostname": hostname })
#             except Exception as e:
#                 logger.error("호스트 처리 중 오류 (%s): %s", ip, str(e))

#     if results:
#         table = Table(title="등록된 SSH 호스트")
#         table.add_column("IP", style="cyan", no_wrap=True)
#         table.add_column("Hostname", style="green")
#         for entry in results:
#             table.add_row(entry["IP"], entry["Hostname"])
#         console.print(table)
#     else:
#         console.print("[yellow]새로 등록된 호스트가 없습니다.[/yellow]")

# SSH 접속 확인 함수
def check_ssh_connection(host):
    config_path = os.path.expanduser(SSH_CONFIG_FILE)
    ssh_config = SSHConfig()
    with open(config_path, "r") as f:
        ssh_config.parse(f)
    
    host_config = ssh_config.lookup(host)
    if not host_config:
        return host, False, None
    
    hostname = host_config.get('hostname')
    user = host_config.get('user')
    port = int(host_config.get('port', 22))
    identityfile = host_config.get('identityfile')
    
    client = paramiko.SSHClient()
    # 보안 정책 설정: 설정 파일에서 정책을 읽어오거나 환경 변수 확인
    try:
        from ic.config.manager import ConfigManager
    except ImportError:
        try:
            from ic.config.manager import ConfigManager
        except ImportError:
            # Legacy fallback for development
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            from ic.config.manager import ConfigManager
    _config_manager = ConfigManager()
    _config = _config_manager.load_all_configs()
    _ssh_config = _config.get('ssh', {})
    host_key_policy = _ssh_config.get('host_key_policy', 'auto').lower()
    
    if os.getenv('IC_TEST_MODE') or os.getenv('IC_DEV_MODE'):
        client.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507
    elif host_key_policy == 'reject':
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    elif host_key_policy == 'warning':
        client.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507
    elif host_key_policy == 'auto':
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
    else:
        # 기본값: 보안을 위해 경고 정책 사용
        client.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507
    try:
        client.connect(
            hostname=hostname,
            username=user,
            port=port,
            key_filename=identityfile[0] if identityfile else None,
            timeout=SSH_TIMEOUT
        )
        client.close()
        return (host, hostname, True, None)

    except paramiko.ssh_exception.AuthenticationException as e:
        # e를 소문자로 변환
        error_str = str(e).lower()
        if "keyboard-interactive" in error_str or "Verification code" in error_str:
            # 여기서 바로 사용자 입력을 받지 않고,
            # "검증코드 필요 -> 접속 실패"로 처리하거나, 별도 목록에 넣음
            # print(f"- {host} : Verification needed (keyboard-interactive), skipped.")
            return (host, hostname, False, str(e))
        else:
            # print(f"- {host} : Authentication failed ({e})")
            return (host, hostname, False, str(e))

    except Exception as e:
        # print(f"- {host} : Connection error ({e})")
        return (host, hostname, False, str(e))

def check_ssh_connections():
    """SSH config에 정의된 모든 호스트의 연결 상태를 확인합니다."""
    config_path = os.path.expanduser(SSH_CONFIG_FILE)
    hosts = []

    try:
        with open(config_path, "r") as f:
            for line in f:
                if line.strip().startswith("Host "):
                    host = line.strip().split()[1]
                    if host != "*":
                        hosts.append(host)
    except Exception as e:
        logger.exception("SSH 설정 파일 읽기 실패: %s", e)
        console.print(f"[bold red]SSH 설정 파일 읽기 실패:[/bold red] {e}")
        return

    failed_hosts = []
    with ThreadPoolExecutor(max_workers=SSH_MAX_WORKER) as executor:
        results = executor.map(check_ssh_connection, hosts)
        for host, hostname, success, error in results:
            if not success:
                failed_hosts.append((host, hostname, error))

    if failed_hosts:
        table = Table(title="SSH 연결 실패 호스트", show_lines=True)
        table.add_column("Host", style="red")
        table.add_column("IP", style="cyan")
        table.add_column("Error", style="yellow")
        for host, hostname, error in failed_hosts:
            table.add_row(host, hostname, error)
        console.print(table)
    else:
        console.print("[bold green]모든 호스트에 성공적으로 연결되었습니다.[/bold green]")

import netifaces

def select_cidr():
    """CIDR 자동 추정 후 사용자에게 사용할지 직접 물어봅니다."""
    console.rule("[bold cyan]🧭 CIDR 대역 선택 단계[/bold cyan]")
    auto_cidr = guess_local_cidr()
    if auto_cidr:
        console.print(f"[green]자동 추정된 CIDR:[/green] [bold]{auto_cidr}[/bold]")
        console.print("[yellow]CIDR 대역을 선택하세요:[/yellow]")
        console.print("[cyan]1.[/cyan] 이 CIDR 대역을 사용합니다.")
        console.print("[cyan]2.[/cyan] 직접 CIDR을 입력하겠습니다.")
        choice = Prompt.ask("선택", choices=["1", "2"], default="1")
        if choice == "1":
            return auto_cidr
    return Prompt.ask("CIDR를 입력하세요 (예: 192.168.0.0/24)")

def guess_local_cidr():
    """기본 네트워크 인터페이스의 CIDR을 추정합니다 (사설망 기준 넓은 대역)."""
    try:
        gw_iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
        iface_info = netifaces.ifaddresses(gw_iface)[netifaces.AF_INET][0]
        ip = iface_info['addr']
        ip_parts = ip.split(".")
        if ip.startswith("10."):
            cidr = f"{ip_parts[0]}.{ip_parts[1]}.0.0/16"
        elif ip.startswith("192.168."):
            cidr = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        elif ip.startswith("172.") and 16 <= int(ip_parts[1]) <= 31:
            cidr = f"{ip_parts[0]}.{ip_parts[1]}.0.0/16"
        else:
            cidr = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        logger.info("자동 추정된 CIDR: %s", cidr)
        return cidr
    except Exception as e:
        logger.warning("CIDR 자동 추정 실패: %s", e)
        return None

def main():
    parser = argparse.ArgumentParser(description="자동 SSH 호스트 스캐너")
    parser.add_argument("cidr", nargs="?", help="검색할 CIDR (예: 192.168.0.0/24)")
    parser.add_argument("--check", action="store_true", help="모든 SSH 호스트 연결 확인")
    args = parser.parse_args()

    if args.check:
        logger.info("모든 SSH 호스트 연결 상태 확인 시작")
        check_ssh_connections()
        return

    cidr = args.cidr or select_cidr()
    local_ip = get_local_ip()
    open_hosts = [ip for ip in scan_open_hosts(cidr) if ip != local_ip]

    if not open_hosts:
        console.print("[yellow]열려있는 호스트가 없습니다.[/yellow]")
        return

    results = []


    console.print("[red]Port Open IP LIST : [/red]")
    for ip in open_hosts:
        console.print(f"[green]{ip}[/green]")

    for ip in open_hosts:
        console.rule(f"[bold green]💻 호스트 설정: {ip}[/bold green]")
        console.print("[yellow]이 IP를 등록하시겠습니까?[/yellow]")
        console.print("[cyan]1.[/cyan] 등록")
        console.print("[cyan]0.[/cyan] 등록하지 않음")
        confirm = Prompt.ask("선택", choices=["0", "1"], default="0")
        if confirm == "0":
            continue
        hostname = Prompt.ask("이 호스트에 사용할 이름 (hostname)", default=f"host-{ip.replace('.', '-')}")
        user = select_ssh_user()
        port = prompt_port()
        key_path = select_key_file(DEFAULT_KEY_DIR)
        update_ssh_config(ip, hostname, key_path, user, port)
        results.append({ "IP": ip, "Hostname": hostname })

    if results:
        table = Table(title="최종 등록된 SSH 호스트")
        table.add_column("IP", style="cyan")
        table.add_column("Hostname", style="green")
        for r in results:
            table.add_row(r["IP"], r["Hostname"])
        console.print(table)


if __name__ == "__main__":
    main()

