#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import oci
from rich.console import Console
from rich.table import Table
from rich import box
import datetime
from common.progress_decorator import progress_bar, ManualProgress

def add_arguments(parser):
    parser.add_argument("--cost-start", default=None, help="크레딧 조회 시작일 (YYYY-MM-DD), 기본: 2025-05-22")
    parser.add_argument("--cost-end", default=None, help="크레딧 조회 종료일 (YYYY-MM-DD), 기본: 오늘")
    parser.add_argument("--credit-initial", type=float, default=None, help="초기 크레딧 금액")

@progress_bar("Fetching credit usage data from OCI")
def get_credit_usage(usage_client, tenancy_ocid, start_date, end_date, initial_credit, console):
    from oci.usage_api.models import RequestSummarizedUsagesDetails
    
    with ManualProgress("Processing credit usage analysis", total=4) as progress:
        # Step 1: Prepare request parameters
        progress.update("Preparing credit usage request")
        adj_end_time = end_date + datetime.timedelta(days=1)

        details = RequestSummarizedUsagesDetails(
            tenant_id=tenancy_ocid,
            time_usage_started=start_date,
            time_usage_ended=adj_end_time,
            granularity="MONTHLY",
            query_type="COST",
            group_by=[],
            compartment_depth=6,
        )
        progress.advance(1)

        # Step 2: Fetch usage data from API
        progress.update("Calling OCI Usage API for credit data")
        monthly_cost: dict[str, float] = {}
        currency_cd = "KRW"

        try:
            resp = usage_client.request_summarized_usages(details)
            items = resp.data.items or []
            progress.advance(1)
            
            # Step 3: Process monthly cost data
            progress.update(f"Processing {len(items)} monthly cost records")
            if items:
                currency_cd = items[0].currency if items[0].currency and items[0].currency.strip() else "KRW"
            for it in items:
                cost_val = float(it.computed_amount or 0.0)
                mk = it.time_usage_started.strftime("%Y-%m")
                monthly_cost.setdefault(mk, 0.0)
                monthly_cost[mk] += cost_val
            progress.advance(1)
            
        except Exception as e:
            console.print(f"[yellow][WARN][/yellow] 크레딧 조회 실패: {e}")
            return {}, currency_cd

        # Step 4: Calculate credit consumption over time
        progress.update("Calculating credit consumption timeline")
        credit_data: dict[str, tuple[float, float]] = {}
        remain = initial_credit

        curr = datetime.datetime(start_date.year, start_date.month, 1)
        end_month = datetime.datetime(end_date.year, end_date.month, 1)
        month_count = 0
        while curr <= end_month:
            mk = curr.strftime("%Y-%m")
            used = monthly_cost.get(mk, 0.0)
            remain -= used
            if remain < 0:
                remain = 0
            credit_data[mk] = (used, remain)
            month_count += 1

            if curr.month == 12:
                curr = datetime.datetime(curr.year + 1, 1, 1)
            else:
                curr = datetime.datetime(curr.year, curr.month + 1, 1)
        
        progress.update(f"Processed {month_count} months of credit data")
        progress.advance(1)

    return credit_data, currency_cd

def print_credit_table(credit_data, console, initial_credit, currency_cd):
    year_to_print = list(credit_data.keys())[0].split('-')[0] if credit_data else "N/A"
    console.print(f"[bold underline]\nCredit Usage for {year_to_print}[/bold underline]")
    if not credit_data:
        console.print("(No credit data)")
        return
    
    tbl= Table(show_lines=False, box=box.SIMPLE_HEAVY)
    tbl.add_column("Month", style="bold cyan")
    tbl.add_column(f"Monthly Cost({currency_cd})", justify="right")
    tbl.add_column(f"Remaining({currency_cd})", justify="right")
    tbl.add_section()
    tbl.add_row("[magenta bold]Initial[/magenta bold]", "-", f"{initial_credit:,.0f}")
    tbl.add_section()

    final_use=0.0
    for mk in sorted(credit_data.keys()):
        costv, rm= credit_data[mk]
        final_use+= costv
        tbl.add_row(mk, f"{costv:,.0f}", f"{rm:,.0f}")
    
    final_remain = list(credit_data.values())[-1][1] if credit_data else initial_credit
    tbl.add_section()
    tbl.add_row("[bold]Summary[/bold]", f"[blue bold]{final_use:,.0f}[/blue bold]", f"[green bold]{final_remain:,.0f}[/green bold]")
    console.print(tbl)

@progress_bar("Analyzing OCI credit usage")
def main(args):
    console = Console()
    
    with ManualProgress("Initializing OCI credit analysis", total=5) as progress:
        # Step 1: Load OCI configuration
        progress.update("Loading OCI configuration")
        try:
            config = oci.config.from_file("~/.oci/config", "DEFAULT")
            usage_client = oci.usage_api.UsageapiClient(config)
        except Exception as e:
            console.print(f"[red]OCI 설정 파일 로드 실패: {e}[/red]")
            sys.exit(1)
        progress.advance(1)

        # Step 2: Parse date parameters
        progress.update("Parsing date and credit parameters")
        now = datetime.datetime.utcnow()
        try:
            start_date = datetime.datetime.strptime(args.cost_start, "%Y-%m-%d") if args.cost_start else datetime.datetime(2025, 5, 22)
            end_date = datetime.datetime.strptime(args.cost_end, "%Y-%m-%d") if args.cost_end else datetime.datetime(now.year, now.month, now.day)
        except ValueError:
            console.print("[red]날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식으로 입력해주세요.[/red]")
            sys.exit(1)
        progress.advance(1)
        
        # Step 3: Set initial credit amount
        progress.update("Setting initial credit parameters")
        initial_credit = args.credit_initial if args.credit_initial is not None else 208698600.0
        progress.advance(1)

        # Step 4: Fetch credit usage data (this will show its own progress)
        progress.update("Fetching credit usage data")
        cd, currency_cd = get_credit_usage(usage_client, config["tenancy"], start_date, end_date, initial_credit, console)
        progress.advance(1)
        
        # Step 5: Display results
        progress.update("Generating credit usage report")
        if cd:
            print_credit_table(cd, console, initial_credit, currency_cd)
        else:
            console.print("(No Credit Data)")
        progress.advance(1) 