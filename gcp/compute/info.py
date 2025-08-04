#!/usr/bin/env python3
import argparse
import json
import os
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

console = Console()

def load_mock_data():
    """Mocks/gcp/compute/mock_data.json 에서 데이터를 로드합니다."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    mock_file = os.path.join(dir_path, 'mock_data.json')

    try:
        with open(mock_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[bold red]에러: Mock 데이터 파일을 찾을 수 없습니다: {mock_file}[/bold red]")
        return []
    except json.JSONDecodeError:
        console.print(f"[bold red]에러: Mock 데이터 파일의 형식이 올바르지 않습니다: {mock_file}[/bold red]")
        return []

def print_instance_table(instances):
    """GCP 인스턴스 목록을 계층적 테이블로 출력합니다."""
    if not instances:
        console.print("[yellow]표시할 GCP Compute Engine 정보가 없습니다.[/yellow]")
        return

    instances.sort(key=lambda x: (x.get("project_name", ""), x.get("zone", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    headers = ["Project", "Zone", "Instance Name", "Status", "Machine Type", "Internal IP", "External IP"]
    keys = ["project_name", "zone", "name", "status", "machineType", "internalIp", "externalIp"]

    table.add_column("Project", style="bold magenta")
    table.add_column("Zone", style="bold cyan")
    table.add_column("Instance Name")
    table.add_column("Status", justify="center")
    table.add_column("Machine Type")
    table.add_column("Internal IP")
    table.add_column("External IP")

    last_project = None
    last_zone = None
    for i, inst in enumerate(instances):
        project_changed = inst.get("project_name") != last_project
        zone_changed = inst.get("zone") != last_zone

        if i > 0:
            if project_changed:
                table.add_row(Rule(style="dim"))
            elif zone_changed:
                table.add_row("", Rule(style="dim"))

        status = inst.get('status', 'N/A')
        color = "green" if status == "RUNNING" else "red"
        status_colored = f"[{color}]{status}[/{color}]"
        
        display_values = [
            inst.get("project_name", "") if project_changed else "",
            inst.get("zone", "") if project_changed or zone_changed else "",
            inst.get("name", "N/A"),
            status_colored,
            inst.get("machineType", "N/A"),
            inst.get("internalIp", "-"),
            inst.get("externalIp", "-")
        ]
        
        table.add_row(*display_values)

        last_project = inst.get("project_name")
        last_zone = inst.get("zone")
    
    console.print(table)

def main(args):
    """메인 함수"""
    instances = load_mock_data()
    
    if args.name:
        instances = [inst for inst in instances if args.name.lower() in inst.get('name', '').lower()]
    
    if args.project:
        instances = [inst for inst in instances if args.project.lower() in inst.get('project_name', '').lower()]

    print_instance_table(instances)

def add_arguments(parser):
    """CLI 인자 추가"""
    parser.add_argument('-p', '--project', help='GCP 프로젝트 이름으로 필터링')
    parser.add_argument('-n', '--name', help='인스턴스 이름으로 필터링 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Compute Engine 정보 (Mock)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
