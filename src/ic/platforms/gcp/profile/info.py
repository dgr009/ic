"""
GCP Profile (Configurations) 정보 표시

AWS profile info, Tencent profile info에 대응.
~/.config/gcloud/configurations/ 디렉토리의 gcloud 프로필(configuration) 파일들을 파싱하여
설정된 계정 목록, 활성 프로젝트, 리전, 존 정보를 테이블로 출력합니다.

Usage:
    ic gcp profile info
    ic gcp profile info --mock
    ic gcp profile info --active-only
    ic gcp profile info --output json
"""

import os
import json
import configparser
from pathlib import Path
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from ic.core.interfaces.command import BaseCommand
from ic.core.interfaces.result import CommandResult

console = Console()


class GcpProfileParser:
    """~/.config/gcloud/ 설정 파일들을 파싱합니다."""

    DEFAULT_GCLOUD_DIR = Path.home() / ".config" / "gcloud"

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
            self.gcloud_dir = self.config_dir.parent
        else:
            self.gcloud_dir = self.DEFAULT_GCLOUD_DIR
            self.config_dir = self.gcloud_dir / "configurations"

    def get_active_config_name(self) -> str:
        """현재 활성화된 configuration 이름을 반환합니다."""
        env_active = os.getenv("CLOUDSDK_ACTIVE_CONFIG_NAME")
        if env_active:
            return env_active.strip()

        active_file = self.gcloud_dir / "active_config"
        if active_file.exists():
            try:
                return active_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return "default"

    def get_adc_info(self) -> Dict[str, Any]:
        """Application Default Credentials 정보를 확인합니다."""
        adc_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not adc_path:
            adc_path = str(self.gcloud_dir / "application_default_credentials.json")

        path_obj = Path(adc_path)
        if not path_obj.exists():
            return {"exists": False, "path": adc_path}

        try:
            with open(path_obj, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "exists": True,
                "path": adc_path,
                "type": data.get("type", "unknown"),
                "account": data.get("client_email") or data.get("account", "-"),
                "quota_project_id": data.get("quota_project_id", "-"),
            }
        except Exception as e:
            return {"exists": True, "path": adc_path, "error": str(e)}

    def parse_configurations(self) -> List[Dict[str, Any]]:
        """모든 configuration 파일을 파싱하여 프로필 목록을 반환합니다."""
        if not self.config_dir.exists():
            return []

        active_name = self.get_active_config_name()
        profiles = []

        for config_file in sorted(self.config_dir.glob("config_*")):
            if not config_file.is_file():
                continue

            config_name = config_file.name[len("config_"):]
            is_active = (config_name == active_name)

            cp = configparser.ConfigParser()
            try:
                cp.read(config_file, encoding="utf-8")
            except Exception:
                continue

            account = "-"
            project = "-"
            if cp.has_section("core"):
                account = cp.get("core", "account", fallback="-")
                project = cp.get("core", "project", fallback="-")

            region = "-"
            zone = "-"
            if cp.has_section("compute"):
                region = cp.get("compute", "region", fallback="-")
                zone = cp.get("compute", "zone", fallback="-")

            profiles.append({
                "name": config_name,
                "is_active": is_active,
                "status": "Active" if is_active else "Inactive",
                "account": account,
                "project": project,
                "region": region,
                "zone": zone,
                "file_path": str(config_file),
            })

        # 활성 프로필이 맨 위로 오도록 정렬
        profiles.sort(key=lambda x: (not x["is_active"], x["name"]))
        return profiles


def format_table_output(profiles: List[Dict[str, Any]], verbose: bool = False) -> None:
    """GCP 프로필 목록을 Rich 테이블로 출력합니다."""
    if not profiles:
        console.print("[yellow]📋 등록된 GCP 프로필(configuration)이 없습니다.[/yellow]")
        console.print("💡 [dim]gcloud init 또는 gcloud config configurations create <name> 명령으로 프로필을 생성할 수 있습니다.[/dim]")
        return

    table = Table(title="🌐 GCP Profiles (Configurations)", title_style="bold blue")
    table.add_column("Active", justify="center", style="bold", no_wrap=True)
    table.add_column("Configuration", style="cyan", no_wrap=True)
    table.add_column("Account", style="green")
    table.add_column("Project ID", style="bold yellow")
    table.add_column("Region", style="white")
    table.add_column("Zone", style="dim white")
    table.add_column("Status", justify="center")

    for p in profiles:
        is_active = p.get("is_active", False)
        active_mark = "[bold green]●[/bold green]" if is_active else "[dim]○[/dim]"
        status_mark = "[bold green]Active[/bold green]" if is_active else "[dim]Inactive[/dim]"
        cfg_name = f"[bold]{p.get('name', '-')}[/bold]" if is_active else p.get("name", "-")

        table.add_row(
            active_mark,
            cfg_name,
            p.get("account", "-"),
            p.get("project", "-"),
            p.get("region", "-"),
            p.get("zone", "-"),
            status_mark,
        )

    console.print(table)

    # 활성 프로필 요약
    active_profile = next((p for p in profiles if p.get("is_active")), None)
    active_name = active_profile["name"] if active_profile else "None"
    active_proj = active_profile["project"] if active_profile else "-"
    active_acc = active_profile["account"] if active_profile else "-"

    adc_parser = GcpProfileParser()
    adc = adc_parser.get_adc_info()
    adc_status = "[green]Available[/green]" if adc.get("exists") else "[dim]Not Found[/dim]"

    console.print(f"\n📊 [bold]Active Configuration:[/bold] [cyan]{active_name}[/cyan] (Project: [bold yellow]{active_proj}[/bold yellow], Account: [green]{active_acc}[/green])")
    console.print(f"🔑 [bold]ADC Credentials:[/bold] {adc_status}")
    if adc.get("exists") and adc.get("quota_project_id") and adc.get("quota_project_id") != "-":
        console.print(f"💡 [dim]ADC Quota Project: {adc.get('quota_project_id')}[/dim]")


def format_tree_output(profiles: List[Dict[str, Any]]) -> None:
    """GCP 프로필 목록을 트리 구조로 출력합니다."""
    if not profiles:
        console.print("[yellow]📋 등록된 GCP 프로필이 없습니다.[/yellow]")
        return

    tree = Tree("🌐 [bold blue]GCP Configurations[/bold blue]")
    for p in profiles:
        is_active = p.get("is_active", False)
        prefix = "● [bold green]" if is_active else "○ [dim]"
        suffix = "[/bold green] (Active)" if is_active else "[/dim]"
        cfg_node = tree.add(f"{prefix}{p.get('name')}{suffix}")
        cfg_node.add(f"👤 Account: {p.get('account', '-')}")
        cfg_node.add(f"📁 Project: {p.get('project', '-')}")
        cfg_node.add(f"📍 Location: {p.get('region', '-')} / {p.get('zone', '-')}")
    console.print(tree)


class GcpProfileInfoCommand(BaseCommand):
    """GCP 프로필 정보 조회 커맨드"""

    @classmethod
    def add_arguments(cls, parser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Mock 데이터를 사용하여 오프라인으로 실행",
        )
        parser.add_argument(
            "--config-dir",
            help="gcloud configuration 디렉토리 경로 (기본: ~/.config/gcloud/configurations)",
        )
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="현재 활성화된 프로필만 출력",
        )

    def execute(self, args, config=None) -> CommandResult:
        use_mock = getattr(args, "mock", False)
        if use_mock:
            mock_file = Path(__file__).parent / "mock_data.json"
            if mock_file.exists():
                with open(mock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return CommandResult(
                    data=data,
                    table_renderer=format_table_output,
                    tree_renderer=format_tree_output,
                    success=True,
                    metadata={"total_count": len(data), "mock": True},
                )
            return CommandResult(
                data=[],
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                success=True,
                metadata={"mock": True},
            )

        parser = GcpProfileParser(config_dir=getattr(args, "config_dir", None))
        profiles = parser.parse_configurations()
        adc_info = parser.get_adc_info()

        if getattr(args, "active_only", False):
            profiles = [p for p in profiles if p.get("is_active")]

        return CommandResult(
            data=profiles,
            table_renderer=format_table_output,
            tree_renderer=format_tree_output,
            success=True,
            metadata={
                "total_count": len(profiles),
                "active_config": parser.get_active_config_name(),
                "adc_info": adc_info,
            },
        )


# Legacy CLI 지원을 위한 전역 함수
def add_arguments(parser):
    cmd = GcpProfileInfoCommand()
    cmd.add_arguments(parser)


def main(args, config=None):
    cmd = GcpProfileInfoCommand()
    return cmd.run(args, config)
