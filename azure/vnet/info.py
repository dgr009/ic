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
    """Mocks/azure/vnet/mock_data.json 에서 데이터를 로드합니다."""
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

def print_vnet_table(vnets):
    """VNet 정보를 계층적 테이블로 출력합니다."""
    if not vnets:
        console.print("[yellow]표시할 Azure VNet 정보가 없습니다.[/yellow]")
        return
        
    vnets.sort(key=lambda x: (x.get("subscription_name", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Subscription", style="bold magenta")
    table.add_column("VNet Name", style="bold green")
    table.add_column("Resource Group")
    table.add_column("Location")
    table.add_column("Address Space")
    table.add_column("Subnet Name", style="cyan")
    table.add_column("Subnet Prefix")
    table.add_column("NSG / Route Table")

    last_sub = None
    last_vnet = None
    for i, vnet in enumerate(vnets):
        sub_changed = vnet.get("subscription_name") != last_sub
        vnet_changed = vnet.get("name") != last_vnet

        if i > 0:
            if sub_changed:
                table.add_row(Rule(style="dim"))
            elif vnet_changed:
                table.add_row("", Rule(style="dim"))
        
        address_spaces = ", ".join(vnet.get('address_space', []))
        
        for j, subnet in enumerate(vnet.get('subnets', [])):
            nsg_info = subnet.get('nsg', '-')
            rt_info = subnet.get('route_table', '-')
            
            display_values = [
                vnet.get("subscription_name", "") if (sub_changed and j==0) else "",
                vnet.get("name", "N/A") if (vnet_changed and j==0) else "",
                vnet.get("resource_group", "N/A") if j == 0 else "",
                vnet.get("location", "N/A") if j == 0 else "",
                address_spaces if j == 0 else "",
                subnet.get('name', 'N/A'),
                subnet.get('address_prefix', 'N/A'),
                f"{nsg_info} / {rt_info}"
            ]
            table.add_row(*display_values)

        last_sub = vnet.get("subscription_name")
        last_vnet = vnet.get("name")
    
    console.print(table)

def main(args):
    """메인 함수"""
    vnets = load_mock_data()
    
    if args.name:
        vnets = [vnet for vnet in vnets if args.name.lower() in vnet.get('name', '').lower()]

    if args.subscription:
        vnets = [vnet for vnet in vnets if args.subscription.lower() in vnet.get('subscription_name', '').lower()]

    print_vnet_table(vnets)

def add_arguments(parser):
    """CLI 인자 추가"""
    parser.add_argument('-s', '--subscription', help='Azure Subscription 이름으로 필터링')
    parser.add_argument('-n', '--name', help='VNet 이름으로 필터링 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure VNet 정보 (Mock)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
