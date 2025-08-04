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
    """Mocks/gcp/vpc/mock_data.json 에서 데이터를 로드합니다."""
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

def print_vpc_table(vpcs):
    """GCP VPC 정보를 계층적 테이블로 출력합니다."""
    if not vpcs:
        console.print("[yellow]표시할 GCP VPC 정보가 없습니다.[/yellow]")
        return

    vpcs.sort(key=lambda x: (x.get("project_name", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("VPC Name", style="bold green")
    table.add_column("Resource Type")
    table.add_column("Name / Destination")
    table.add_column("Details / Next Hop")

    last_project = None
    last_vpc = None
    for i, vpc in enumerate(vpcs):
        project_changed = vpc.get("project_name") != last_project
        vpc_changed = vpc.get("name") != last_vpc

        if i > 0:
            if project_changed:
                table.add_row(Rule(style="dim"))
            elif vpc_changed:
                table.add_row("", Rule(style="dim"))
        
        # VPC 정보 행
        table.add_row(
            vpc.get("project_name", "") if project_changed else "",
            vpc.get("name", "N/A"),
            "", "", ""
        )
        
        # Subnetworks
        for subnet in vpc.get("subnetworks", []):
            table.add_row(
                "", "",
                "[cyan]Subnetwork[/cyan]",
                subnet.get("name"),
                f"Region: {subnet.get('region')}, CIDR: {subnet.get('ipCidrRange')}"
            )
            
        # Routes
        if vpc.get("routes"):
            table.add_row("", "", Rule(style="dotted"))
        for route in vpc.get("routes", []):
            dest_padded = route.get('destRange', '').ljust(18)
            table.add_row(
                "", "",
                "[yellow]Route[/yellow]",
                f"{dest_padded} -> {route.get('nextHop')}",
                f"Name: {route.get('name')}"
            )

        last_project = vpc.get("project_name")
        last_vpc = vpc.get("name")
    
    console.print(table)

def main(args):
    """메인 함수"""
    vpcs = load_mock_data()
    
    if args.name:
        vpcs = [vpc for vpc in vpcs if args.name.lower() in vpc.get('name', '').lower()]

    if args.project:
        vpcs = [vpc for vpc in vpcs if args.project.lower() in vpc.get('project_name', '').lower()]

    print_vpc_table(vpcs)

def add_arguments(parser):
    """CLI 인자 추가"""
    parser.add_argument('-p', '--project', help='GCP 프로젝트 이름으로 필터링')
    parser.add_argument('-n', '--name', help='VPC 이름으로 필터링 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP VPC 정보 (Mock)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
