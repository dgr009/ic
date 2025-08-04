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
    """Mocks/azure/vm/mock_data.json 에서 데이터를 로드합니다."""
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

def print_vm_table(vms):
    """VM 목록을 계층적 테이블로 출력합니다."""
    if not vms:
        console.print("[yellow]표시할 Azure VM 정보가 없습니다.[/yellow]")
        return
        
    vms.sort(key=lambda x: (x.get("subscription_name", ""), x.get("location", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    headers = ["Subscription", "Location", "Resource Group", "VM Name", "State", "Size", "Private IP", "Public IP"]
    
    table.add_column("Subscription", style="bold magenta")
    table.add_column("Location", style="bold cyan")
    table.add_column("Resource Group")
    table.add_column("VM Name")
    table.add_column("State", justify="center")
    table.add_column("Size")
    table.add_column("Private IP")
    table.add_column("Public IP")

    last_sub = None
    last_loc = None
    for i, vm in enumerate(vms):
        sub_changed = vm.get("subscription_name") != last_sub
        loc_changed = vm.get("location") != last_loc

        if i > 0:
            if sub_changed:
                table.add_row(Rule(style="dim"))
            elif loc_changed:
                table.add_row("", Rule(style="dim"))
        
        state = vm.get('power_state', 'N/A')
        color = "green" if "running" in state.lower() else "yellow"
        state_colored = f"[{color}]{state}[/{color}]"

        display_values = [
            vm.get("subscription_name", "") if sub_changed else "",
            vm.get("location", "") if sub_changed or loc_changed else "",
            vm.get("resource_group", "N/A"),
            vm.get("name", "N/A"),
            state_colored,
            vm.get("size", "N/A"),
            vm.get("private_ip", "-"),
            vm.get("public_ip", "-")
        ]
        
        table.add_row(*display_values)

        last_sub = vm.get("subscription_name")
        last_loc = vm.get("location")

    console.print(table)

def main(args):
    """메인 함수"""
    vms = load_mock_data()
    
    if args.name:
        vms = [vm for vm in vms if args.name.lower() in vm.get('name', '').lower()]

    if args.subscription:
        vms = [vm for vm in vms if args.subscription.lower() in vm.get('subscription_name', '').lower()]

    print_vm_table(vms)

def add_arguments(parser):
    """CLI 인자 추가"""
    parser.add_argument('-s', '--subscription', help='Azure Subscription 이름으로 필터링')
    parser.add_argument('-n', '--name', help='VM 이름으로 필터링 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure VM 정보 (Mock)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
