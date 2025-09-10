#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import oci
from rich.console import Console
from rich.table import Table
from rich import box
from datetime import datetime, timedelta
from common.progress_decorator import progress_bar, ManualProgress

def add_arguments(parser):
    parser.add_argument("--cost-start", default=None, help="비용 조회 시작 (YYYY-MM-DD)")
    parser.add_argument("--cost-end", default=None, help="비용 조회 종료 (YYYY-MM-DD)")

def get_date_range(start_str, end_str):
    now = datetime.utcnow()
    try:
        if start_str:
            y,m,d = map(int, start_str.split('-'))
            start_date = datetime(y,m,d)
        else:
            start_date = datetime(now.year, now.month, 1)
        if end_str:
            y,m,d = map(int, end_str.split('-'))
            end_date = datetime(y,m,d) + timedelta(days=1)
        else:
            end_date = datetime(now.year, now.month, now.day) + timedelta(days=1)
    except Exception:
        start_date = datetime(now.year, now.month, 1)
        end_date   = datetime(now.year, now.month, now.day) + timedelta(days=1)
    return start_date, end_date

@progress_bar("Fetching cost data from OCI Usage API")
def get_compartment_costs(usage_client, tenancy_ocid, start_time, end_time, console):
    with ManualProgress("Preparing cost analysis request", total=3) as progress:
        # Step 1: Prepare request details
        progress.update("Preparing API request parameters")
        details = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=tenancy_ocid,
            time_usage_started=start_time,
            time_usage_ended=end_time,
            granularity="DAILY",
            group_by=["compartmentName", "service"],
            query_type="COST",
            compartment_depth=6
        )
        progress.advance(1)
        
        # Step 2: Execute API call
        progress.update("Calling OCI Usage API")
        cost_data={}
        currency_cd = "USD"   
        try:
            resp = usage_client.request_summarized_usages(details)
            items = resp.data.items or []
            progress.advance(1)
            
            # Step 3: Process response data
            progress.update(f"Processing {len(items)} cost records")
            if items:
                currency_cd = items[0].currency or currency_cd
            for it in items:
                cname= it.compartment_name or "(root)"
                sname= it.service or "(UnknownService)"
                cval = float(it.computed_amount or 0.0)
                cost_data.setdefault(cname, {})
                cost_data[cname].setdefault(sname, 0.0)
                cost_data[cname][sname]+= cval
            progress.advance(1)
            
        except Exception as e:
            console.print(f"[yellow][WARN][/yellow] Cost API 실패: {e}")
    
    return cost_data, currency_cd

def print_cost_table(cost_rows, console, start_time, end_time, currency_cd):
    end_time_display = end_time - timedelta(seconds=1)
    console.print(f"\n[bold underline]Cost Info ({start_time.strftime('%Y-%m-%d %H:%M')}~{end_time_display.strftime('%Y-%m-%d %H:%M')})[/bold underline]")
    if not cost_rows:
        console.print("(No Cost Data)")
        return

    tbl = Table(show_lines=False, box=box.HEAVY_EDGE)
    tbl.add_column("Compartment", style="bold magenta")
    tbl.add_column("Service", style="bold cyan")
    tbl.add_column(f"Cost({currency_cd})", justify="right")
    tbl.add_column(f"Total({currency_cd})", justify="right")
    
    account_total=0
    for ckey in sorted(cost_rows.keys(), key=lambda x:x.lower()):
        services = cost_rows[ckey]
        ctotal = sum(services.values())
        if ctotal==0:
            continue
        account_total+=ctotal
        first=True
        for svc, val in sorted(services.items(), key=lambda x:x[1], reverse=True):
            if first:
                tbl.add_row(
                    ckey,
                    svc,
                    f"{val:,.0f}",
                    f"[yellow]{ctotal:,.0f}[/yellow]"
                )
                first=False
            else:
                if val>0:
                    tbl.add_row("", svc, f"{val:,.0f}")
        tbl.add_section()
    tbl.add_row("[green]총 합계[/green]","","",f"[green]{account_total:,.0f}[/green]")
    tbl.add_section()
    console.print(tbl)


@progress_bar("Analyzing OCI cost usage")
def main(args):
    console = Console()
    
    with ManualProgress("Initializing OCI cost analysis", total=4) as progress:
        # Step 1: Load OCI configuration
        progress.update("Loading OCI configuration")
        try:
            config = oci.config.from_file("~/.oci/config", "DEFAULT")
            usage_client = oci.usage_api.UsageapiClient(config)
        except Exception as e:
            console.print(f"[red]OCI 설정 파일 로드 실패: {e}[/red]")
            sys.exit(1)
        progress.advance(1)

        # Step 2: Parse date range
        progress.update("Parsing date range parameters")
        start_date, end_date = get_date_range(args.cost_start, args.cost_end)
        progress.advance(1)
        
        # Step 3: Fetch cost data (this will show its own progress)
        progress.update("Fetching cost data from OCI")
        cost_data, currency_cd = get_compartment_costs(usage_client, config["tenancy"], start_date, end_date, console)
        progress.advance(1)
        
        # Step 4: Display results
        progress.update("Generating cost report")
        if cost_data:
            print_cost_table(cost_data, console, start_date, end_date, currency_cd)
        else:
            console.print("(No Cost Data)")
        progress.advance(1) 