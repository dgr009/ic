#!/usr/bin/env python3
import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

from common.log import log_info_non_console
from common.progress_decorator import ManualProgress
from common.utils import get_env_accounts, get_profiles

load_dotenv()
console = Console()

def get_bucket_metrics(cloudwatch_client, bucket_name):
    """CloudWatch에서 버킷의 크기, 객체 수, 스토리지 티어 정보를 가져옵니다."""
    size_gb = 0
    object_count = 0
    storage_tiers = []

    try:
        # 전체 객체 수
        response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/S3',
            MetricName='NumberOfObjects',
            Dimensions=[{'Name': 'BucketName', 'Value': bucket_name}, {'Name': 'StorageType', 'Value': 'AllStorageTypes'}],
            StartTime=datetime.utcnow() - timedelta(days=2),
            EndTime=datetime.utcnow(),
            Period=86400,
            Statistics=['Average']
        )
        if response['Datapoints']:
            object_count = int(response['Datapoints'][0]['Average'])

        # 스토리지 티어별 크기
        metrics_response = cloudwatch_client.list_metrics(
            Namespace='AWS/S3',
            MetricName='BucketSizeBytes',
            Dimensions=[{'Name': 'BucketName', 'Value': bucket_name}]
        )
        
        total_size_bytes = 0
        for metric in metrics_response['Metrics']:
            storage_type = next((dim['Value'] for dim in metric['Dimensions'] if dim['Name'] == 'StorageType'), None)
            if storage_type and storage_type != 'AllStorageTypes':
                response = cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/S3',
                    MetricName='BucketSizeBytes',
                    Dimensions=metric['Dimensions'],
                    StartTime=datetime.utcnow() - timedelta(days=2),
                    EndTime=datetime.utcnow(),
                    Period=86400,
                    Statistics=['Average']
                )
                if response['Datapoints']:
                    size_bytes = response['Datapoints'][0]['Average']
                    total_size_bytes += size_bytes
                    tier_name = storage_type.replace("Storage", "")
                    storage_tiers.append(tier_name)
        
        size_gb = round(total_size_bytes / (1024**3), 2)

    except ClientError as e:
        log_info_non_console(f"CloudWatch 메트릭 조회 실패 (Bucket: {bucket_name}): {e}")

    return size_gb, object_count, ", ".join(storage_tiers) if storage_tiers else "Standard"

def fetch_s3_one_account(account_id, profile_name, name_filter):
    log_info_non_console(f"S3 정보 수집 시작: Account={account_id}")
    session = boto3.Session(profile_name=profile_name)
    s3_client = session.client("s3")
    
    rows = []
    
    try:
        buckets = s3_client.list_buckets().get('Buckets', [])
    except Exception as e:
        log_info_non_console(f"S3 버킷 목록 조회 실패: {e}")
        return []

    for bucket in buckets:
        bucket_name = bucket['Name']
        if name_filter and name_filter.lower() not in bucket_name.lower():
            continue

        try:
            location_resp = s3_client.get_bucket_location(Bucket=bucket_name)
            region = location_resp.get("LocationConstraint") or "us-east-1"
            
            # 해당 버킷의 리전에 맞는 클라이언트 생성
            regional_s3_client = boto3.Session(profile_name=profile_name, region_name=region).client('s3')
            cloudwatch_client = boto3.Session(profile_name=profile_name, region_name=region).client('cloudwatch')
            
            try:
                public_access = regional_s3_client.get_public_access_block(Bucket=bucket_name)['PublicAccessBlockConfiguration']
                access_block = "All Blocked" if all(public_access.values()) else "Partial/Open"
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchPublicAccessBlockConfiguration':
                    access_block = "Not Configured"
                else:
                    access_block = "Error"
            
            size_gb, object_count, storage_tier = get_bucket_metrics(cloudwatch_client, bucket_name)

            rows.append({
                "account": account_id,
                "region": region,
                "bucket_name": bucket_name,
                "access": access_block,
                "storage_tier": storage_tier,
                "size_gb": size_gb,
                "object_count": object_count,
            })

        except ClientError as e:
            log_info_non_console(f"버킷 '{bucket_name}' 정보 조회 실패: {e.response['Error']['Code']}")
            rows.append({
                "account": account_id,
                "region": "Error", "bucket_name": bucket_name, "access": "Error",
                "storage_tier": "Error", "size_gb": "Error", "object_count": "Error",
            })

    return rows

def print_s3_table(all_rows):
    if not all_rows:
        console.print("[yellow]표시할 S3 버킷 정보가 없습니다.[/yellow]")
        return
        
    all_rows.sort(key=lambda x: (x["account"], x["region"], x["bucket_name"]))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    table.show_edge = False
    
    headers = ["Account", "Region", "Bucket Name", "Access", "Storage Tier", "Size(GB)", "Object Count"]
    keys = ["account", "region", "bucket_name", "access", "storage_tier", "size_gb", "object_count"]
    
    for h in headers:
        style = {}
        if h == "Account": style = {"style": "bold magenta"}
        elif h == "Region": style = {"style": "bold cyan"}
        elif h in ["Size(GB)", "Object Count"]: style = {"justify": "right"}
        table.add_column(h, **style)

    last_account = None
    last_region = None
    for i, row in enumerate(all_rows):
        account_changed = row["account"] != last_account
        region_changed = row["region"] != last_region

        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
        
        display_values = []
        display_values.append(row["account"] if account_changed else "")
        display_values.append(row["region"] if account_changed or region_changed else "")

        for k in keys[2:]:
            display_values.append(str(row.get(k, "-")))
        
        table.add_row(*display_values)

        last_account = row["account"]
        last_region = row["region"]
        
    console.print(table)


def main(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    profiles_map = get_profiles()
    name_filter = args.name if hasattr(args, 'name') and args.name else None

    # Calculate total operations for progress tracking
    valid_accounts = []
    for acct in accounts:
        profile_name = profiles_map.get(acct)
        if not profile_name:
            log_info_non_console(f"Account {acct} 에 대한 프로파일을 찾을 수 없습니다.")
            continue
        valid_accounts.append((acct, profile_name))
    
    total_operations = len(valid_accounts)
    
    all_rows = []
    with ManualProgress("Collecting S3 buckets across accounts", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = {}
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                future = executor.submit(fetch_s3_one_account, acct, profile_name, name_filter)
                futures[future] = acct
                future_to_info[future] = acct

            completed = 0
            for future in as_completed(futures):
                acct = future_to_info[future]
                try:
                    result = future.result()
                    all_rows.extend(result)
                    completed += 1
                    progress.update(f"Processed {acct} - Found {len(result)} S3 buckets", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect S3 data for {acct}: {e}")
                    progress.update(f"Failed {acct} - {str(e)[:50]}...", advance=1)

    print_s3_table(all_rows)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-n', '--name', help='S3 버킷 이름 필터 (부분 일치)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS S3 정보 (병렬 수집)")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
