"""
Tencent Profile 정보 표시

AWS profile info 에 대응. ~/.tencent/credentials 파일을 파싱하여
설정된 계정 목록과 credential 상태를 테이블로 출력합니다.

Usage:
    ic tencent profile info
    ic tencent profile info --credentials ~/.tencent/credentials
"""

import re
import configparser
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich import box


console = Console()


###############################################################################
# CLI 인자 정의
###############################################################################
def add_arguments(parser) -> None:
    parser.add_argument(
        "--credentials",
        help="credentials 파일 경로 (기본: ~/.tencent/credentials)"
    )


###############################################################################
# 파서
###############################################################################
class TencentCredentialsParser:
    """~/.tencent/credentials 파일을 파싱합니다."""

    DEFAULT_PATH = Path.home() / ".tencent" / "credentials"

    def __init__(self, creds_path: Optional[str] = None):
        self.path = Path(creds_path) if creds_path else self.DEFAULT_PATH

    def parse(self) -> Dict[str, Dict[str, str]]:
        """INI 형식 파일을 파싱하여 섹션 dict 반환."""
        if not self.path.exists():
            return {}

        config = configparser.ConfigParser()
        config.read(self.path)

        return {section: dict(config[section]) for section in config.sections()}

    def extract_account_id_from_role_arn(self, role_arn: str) -> str:
        """qcs::cam::uin/ACCOUNT_ID:role/... 에서 계정 ID 추출."""
        m = re.search(r"uin/(\d+)", role_arn)
        return m.group(1) if m else "-"

    def extract_role_name_from_arn(self, role_arn: str) -> str:
        """role ARN에서 역할 이름 추출."""
        if not role_arn:
            return "-"
        parts = role_arn.split("/")
        return parts[-1] if len(parts) > 1 else "-"


###############################################################################
# 프로필 정보 수집
###############################################################################
def collect_profile_info(parser: TencentCredentialsParser) -> List[Dict[str, str]]:
    from rich.progress import Progress, SpinnerColumn, TextColumn
    import time

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Parsing Tencent credentials file...", total=None)
        start = time.time()

        sections = parser.parse()

        elapsed = time.time() - start
        progress.update(task, description=f"Done in {elapsed:.2f}s")

    profiles = []
    for section_name, data in sections.items():
        has_direct_creds = bool(data.get("secret_id") and data.get("secret_key"))
        role_arn = data.get("role_arn", "")

        if has_direct_creds:
            profiles.append({
                "name":            section_name,
                "type":            "[bold green]Direct[/bold green]",
                "account_id":      data.get("account_id", "-"),
                "role_arn":        "-",
                "role_name":       "-",
                "source_account":  "-",
                "region":          data.get("region", "-"),
                "credential":      "[bold green]active[/bold green]",
            })
        elif role_arn:
            account_id = parser.extract_account_id_from_role_arn(role_arn) if role_arn else "-"
            role_name  = parser.extract_role_name_from_arn(role_arn) if role_arn else "-"
            source     = data.get("source_account", "main")
            profiles.append({
                "name":            section_name,
                "type":            "[cyan]AssumeRole[/cyan]",
                "account_id":      account_id,
                "role_arn":        role_arn,
                "role_name":       role_name,
                "source_account":  source,
                "region":          data.get("region", "-"),
                "credential":      "[bold green]via AssumeRole[/bold green]",
            })
        else:
            # role_arn도 secret도 없음
            profiles.append({
                "name":            section_name,
                "type":            "[dim]Unknown[/dim]",
                "account_id":      "-",
                "role_arn":        "-",
                "role_name":       "-",
                "source_account":  data.get("source_account", "-"),
                "region":          data.get("region", "-"),
                "credential":      "[bold red]missing[/bold red]",
            })

    return profiles


###############################################################################
# 렌더러
###############################################################################
def render_profiles(profiles: List[Dict[str, str]], creds_path: Path) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]Tencent Credentials[/bold cyan]  [dim]{creds_path}[/dim]"))
    console.print()

    if not profiles:
        console.print(f"[yellow]⚠️  프로필 없음: {creds_path}[/yellow]")
        console.print()
        console.print("[bold]파일을 생성해주세요:[/bold]")
        console.print(f"[dim]  mkdir -p {creds_path.parent}[/dim]")
        console.print(f"  [bold]# {creds_path}[/bold]")
        console.print("""  [dim]
  [main]
  secret_id  = AKIDxxxxxxxxxxxxxxxx
  secret_key  = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  region     = ap-seoul

  [prod]
  role_arn       = qcs::cam::uin/100000000001:role/CrossAccountRole
  source_account = main
  region         = ap-seoul

  [dev]
  role_arn       = qcs::cam::uin/100000000002:role/CrossAccountRole
  source_account = main
  region         = ap-seoul
  [/dim]""")
        return

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.add_column("Name",           style="bold cyan",    no_wrap=True)
    table.add_column("Type",           justify="center")
    table.add_column("Account ID",     style="green",        no_wrap=True)
    table.add_column("Role Name",      style="blue")
    table.add_column("Source Account", style="yellow")
    table.add_column("Region",         style="white")
    table.add_column("Credential",     justify="center")

    for p in profiles:
        table.add_row(
            p["name"],
            p["type"],
            p["account_id"],
            p["role_name"],
            p["source_account"],
            p["region"],
            p["credential"],
        )

    console.print(table)

    # 요약
    total      = len(profiles)
    main_count = sum(1 for p in profiles if "Direct" in p["type"])
    role_count = sum(1 for p in profiles if "AssumeRole" in p["type"])
    console.print(
        f"\n[dim]📊 Total: {total}  |  Direct credentials: {main_count}  |  AssumeRole: {role_count}[/dim]"
    )

    # 설정 미완성 프로필 경고
    unknown = [p["name"] for p in profiles if "Unknown" in p["type"]]
    if unknown:
        console.print(f"\n[yellow]⚠️  설정 미완성 프로필 (secret_id/role_arn 없음): {', '.join(unknown)}[/yellow]")


###############################################################################
# main
###############################################################################
def main(args, config=None) -> None:
    creds_arg = getattr(args, "credentials", None)
    parser = TencentCredentialsParser(creds_arg)

    profiles = collect_profile_info(parser)
    render_profiles(profiles, parser.path)
