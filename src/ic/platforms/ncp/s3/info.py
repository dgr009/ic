#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP S3 Object Storage Information Module

This module provides S3 Object Storage bucket information retrieval for NCP (Naver Cloud Platform).
It follows the same architectural patterns as the OCI and EC2 modules for consistent user experience.

Features:
- Object Storage bucket information retrieval
- Human-readable bucket size formatting
- S3-specific error handling for permission and access issues
- Bucket resource counting and display
- Support for both Classic and VPC platform bucket access
"""

import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

import logging
from common.progress_decorator import progress_bar, ManualProgress
from common.ncp_utils import (
    load_ncp_config, handle_ncp_api_error, apply_status_color, 
    filter_resources_by_name, format_bytes
)
from src.ic.platforms.ncp.client import NCPClient, NCPAPIError

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class NCPBucket:
    """NCP S3 버킷 데이터 모델"""
    bucket_name: str
    region: str
    creation_date: str
    object_count: int
    bucket_size: int
    storage_class: str
    access_control: str
    versioning_status: str
    encryption_status: str
    
    @classmethod
    def from_api_response(cls, bucket_data: Dict[str, Any], region: str) -> 'NCPBucket':
        """API 응답에서 NCPBucket 객체 생성"""
        return cls(
            bucket_name=bucket_data.get('bucketName', ''),
            region=region,
            creation_date=bucket_data.get('creationDate', ''),
            object_count=bucket_data.get('objectCount', 0),
            bucket_size=bucket_data.get('bucketSize', 0),
            storage_class=bucket_data.get('storageClass', 'STANDARD'),
            access_control=bucket_data.get('accessControl', 'PRIVATE'),
            versioning_status=bucket_data.get('versioningStatus', 'Disabled'),
            encryption_status=bucket_data.get('encryptionStatus', 'Disabled')
        )


def add_arguments(parser):
    """S3 Info에 필요한 인자 추가 (OCI 패턴과 동일)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="버킷 상세 출력 (전체 컬럼 표시)")
    parser.add_argument("--name", "-n", default=None, 
                       help="버킷 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP 프로파일 (기본값: default)")


@handle_ncp_api_error
@progress_bar("Collecting NCP S3 buckets")
def fetch_ncp_s3_info(client: NCPClient, name_filter: str = None) -> List[NCPBucket]:
    """
    NCP S3 버킷 정보를 수집합니다.
    
    Args:
        client: NCP API 클라이언트
        name_filter: 버킷 이름 필터 (부분 일치)
        
    Returns:
        NCPBucket 객체 목록
    """
    logger.info("NCP S3 버킷 정보 수집 시작")
    
    try:
        # API를 통해 Object Storage 버킷 목록 조회
        buckets_data = client.get_object_storage_buckets()
        
        if not buckets_data:
            logger.info("조회된 버킷이 없습니다.")
            return []
        
        # NCPBucket 객체로 변환
        buckets = []
        for bucket_data in buckets_data:
            try:
                bucket = NCPBucket.from_api_response(bucket_data, client.region)
                buckets.append(bucket)
            except Exception as e:
                logger.warning(f"버킷 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            buckets = [bucket for bucket in buckets 
                      if name_filter.lower() in bucket.bucket_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(buckets)}개 버킷")
        
        logger.info(f"NCP S3 버킷 정보 수집 완료: {len(buckets)}개")
        return buckets
        
    except NCPAPIError as e:
        logger.error(f"NCP API 오류: {e}")
        console.print(f"[red]NCP API 오류: {e.message}[/red]")
        return []
    except Exception as e:
        logger.error(f"버킷 정보 수집 중 오류: {e}")
        console.print(f"[red]버킷 정보 수집 실패: {e}[/red]")
        return []


def format_bucket_size(size_bytes: int) -> str:
    """
    버킷 크기를 읽기 쉬운 형식으로 변환합니다.
    
    Args:
        size_bytes: 바이트 단위 크기
        
    Returns:
        포맷된 크기 문자열 (예: "1.5 GB")
    """
    if size_bytes == 0:
        return "0 B"
    
    return format_bytes(size_bytes)


def format_object_count(count: int) -> str:
    """
    객체 수를 읽기 쉬운 형식으로 변환합니다.
    
    Args:
        count: 객체 수
        
    Returns:
        포맷된 객체 수 문자열
    """
    if count == 0:
        return "0"
    elif count < 1000:
        return str(count)
    elif count < 1000000:
        return f"{count/1000:.1f}K"
    else:
        return f"{count/1000000:.1f}M"


def format_storage_class(storage_class: str) -> str:
    """스토리지 클래스를 읽기 쉽게 포맷"""
    class_mapping = {
        'STANDARD': 'Standard',
        'STANDARD_IA': 'Standard-IA',
        'COLD': 'Cold Storage',
        'ARCHIVE': 'Archive'
    }
    return class_mapping.get(storage_class.upper(), storage_class)


def format_access_control(access_control: str) -> str:
    """접근 제어를 읽기 쉽게 포맷"""
    if access_control.upper() == 'PRIVATE':
        return "[red]Private[/red]"
    elif access_control.upper() == 'PUBLIC_READ':
        return "[yellow]Public Read[/yellow]"
    elif access_control.upper() == 'PUBLIC_READ_WRITE':
        return "[red bold]Public R/W[/red bold]"
    else:
        return access_control


def format_feature_status(status: str) -> str:
    """기능 상태를 색상으로 포맷"""
    if status.lower() in ['enabled', 'active', 'on']:
        return "[green]Enabled[/green]"
    elif status.lower() in ['disabled', 'inactive', 'off']:
        return "[dim]Disabled[/dim]"
    else:
        return status


def print_ncp_s3_table(buckets: List[NCPBucket], verbose: bool = False) -> None:
    """
    NCP S3 버킷 정보를 OCI 스타일과 유사한 형식으로 출력합니다.
    
    Args:
        buckets: NCPBucket 객체 목록
        verbose: 상세 정보 표시 여부
    """
    if not buckets:
        console.print("(No Buckets)")
        return
    
    # 버킷을 리전, 이름 순으로 정렬
    buckets.sort(key=lambda x: (x.region.lower(), x.bucket_name.lower()))
    
    console.print("[bold underline]NCP S3 Object Storage Info[/bold underline]")
    
    # 테이블 생성 (OCI 스타일)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의
    if verbose:
        headers = ["Region", "Bucket Name", "Objects", "Size", "Storage Class", 
                  "Access Control", "Versioning", "Encryption", "Created"]
        keys = ["region", "bucket_name", "object_count", "bucket_size", "storage_class",
               "access_control", "versioning_status", "encryption_status", "creation_date"]
    else:
        headers = ["Region", "Bucket Name", "Objects", "Size", "Storage Class", "Access Control"]
        keys = ["region", "bucket_name", "object_count", "bucket_size", "storage_class", "access_control"]
    
    # 컬럼 스타일 설정 (OCI 패턴)
    for header in headers:
        style_opts = {}
        if header == "Region": 
            style_opts = {"style": "bold cyan"}
        elif header in ["Objects", "Size"]: 
            style_opts = {"justify": "right"}
        elif header == "Bucket Name": 
            style_opts = {"overflow": "fold"}
        elif header == "Access Control":
            style_opts = {"justify": "center"}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑)
    last_region = None
    
    for i, bucket in enumerate(buckets):
        region_changed = bucket.region != last_region
        
        # 리전이 바뀔 때 구분선 추가
        if i > 0 and region_changed:
            table.add_row(*[Rule(style="dim") for _ in headers])
        
        # 행 데이터 구성
        row_values = []
        
        # 리전 표시 (변경된 경우만)
        row_values.append(bucket.region if region_changed else "")
        
        # 나머지 데이터
        for key in keys[1:]:  # region 제외
            value = getattr(bucket, key, "-")
            
            # 특별한 포맷팅 적용
            if key == "object_count":
                value = format_object_count(int(value)) if value != "-" else "-"
            elif key == "bucket_size":
                value = format_bucket_size(int(value)) if value != "-" else "-"
            elif key == "storage_class":
                value = format_storage_class(str(value))
            elif key == "access_control":
                value = format_access_control(str(value))
            elif key in ["versioning_status", "encryption_status"]:
                value = format_feature_status(str(value))
            elif key == "creation_date" and value:
                # 날짜 포맷팅 (YYYY-MM-DD HH:MM:SS -> YYYY-MM-DD)
                try:
                    if 'T' in str(value):
                        value = str(value).split('T')[0]
                    elif ' ' in str(value):
                        value = str(value).split(' ')[0]
                except:
                    pass
            
            row_values.append(str(value) if value is not None else "-")
        
        table.add_row(*row_values)
        last_region = bucket.region
    
    console.print(table)


def validate_s3_permissions(client: NCPClient) -> bool:
    """
    S3 권한 유효성 검사
    
    Args:
        client: NCP API 클라이언트
        
    Returns:
        권한 검사 결과
    """
    try:
        # 간단한 버킷 목록 조회로 권한 테스트
        client.get_object_storage_buckets()
        return True
    except NCPAPIError as e:
        if "permission" in str(e).lower() or "access" in str(e).lower():
            console.print("[red]S3 Object Storage 접근 권한이 없습니다.[/red]")
            console.print("[yellow]NCP 콘솔에서 Object Storage 권한을 확인하세요.[/yellow]")
        else:
            console.print(f"[red]S3 권한 확인 실패: {e.message}[/red]")
        return False
    except Exception as e:
        logger.error(f"S3 권한 확인 중 오류: {e}")
        return False


def handle_s3_specific_errors(error: Exception) -> None:
    """
    S3 특화 오류 처리
    
    Args:
        error: 발생한 오류
    """
    error_msg = str(error).lower()
    
    if "permission denied" in error_msg or "access denied" in error_msg:
        console.print("[red]Object Storage 접근 권한이 거부되었습니다.[/red]")
        console.print("[yellow]다음을 확인하세요:[/yellow]")
        console.print("  • NCP 콘솔에서 Object Storage 서비스 활성화")
        console.print("  • API 키에 Object Storage 권한 부여")
        console.print("  • 올바른 리전 설정")
    elif "bucket not found" in error_msg:
        console.print("[red]지정된 버킷을 찾을 수 없습니다.[/red]")
    elif "invalid credentials" in error_msg:
        console.print("[red]NCP 인증 정보가 올바르지 않습니다.[/red]")
        console.print("[yellow]'ic config init' 명령어로 설정을 다시 생성하세요.[/yellow]")
    elif "rate limit" in error_msg:
        console.print("[yellow]API 호출 한도에 도달했습니다. 잠시 후 다시 시도하세요.[/yellow]")
    else:
        console.print(f"[red]S3 오류: {error}[/red]")


@progress_bar("Initializing NCP S3 service")
def main(args):
    """
    NCP S3 정보 수집 메인 함수
    
    Args:
        args: 명령행 인자
    """
    try:
        # NCP 설정 로드
        with ManualProgress("Loading NCP configuration", total=4) as progress:
            progress.update("Loading configuration file", advance=1)
            
            try:
                config = load_ncp_config(args.profile)
            except Exception as e:
                console.print(f"[red]NCP 설정 로드 실패: {e}[/red]")
                console.print("[yellow]'ic config init' 명령어로 NCP 설정을 생성하세요.[/yellow]")
                sys.exit(1)
            
            progress.update("Validating credentials", advance=1)
            
            # 인증 정보 유효성 검사
            required_keys = ['access_key', 'secret_key']
            for key in required_keys:
                if key not in config or not config[key]:
                    console.print(f"[red]필수 설정이 누락되었습니다: {key}[/red]")
                    console.print("[yellow]'ic config init' 명령어로 NCP 설정을 생성하세요.[/yellow]")
                    sys.exit(1)
            
            progress.update("Initializing NCP client", advance=1)
            
            # NCP 클라이언트 생성
            try:
                client = NCPClient(
                    access_key=config['access_key'],
                    secret_key=config['secret_key'],
                    region=config.get('region', 'KR'),
                    platform=config.get('platform', 'VPC')
                )
            except Exception as e:
                console.print(f"[red]NCP 클라이언트 초기화 실패: {e}[/red]")
                sys.exit(1)
            
            progress.update("Validating S3 permissions", advance=1)
            
            # S3 권한 확인
            if not validate_s3_permissions(client):
                sys.exit(1)
        
        # 버킷 정보 수집
        buckets = fetch_ncp_s3_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(buckets)} buckets.")
        print_ncp_s3_table(buckets, args.verbose)
        
        # 요약 정보 출력
        if buckets:
            total_objects = sum(bucket.object_count for bucket in buckets)
            total_size = sum(bucket.bucket_size for bucket in buckets)
            
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"  Total Buckets: {len(buckets)}")
            console.print(f"  Total Objects: {format_object_count(total_objects)}")
            console.print(f"  Total Size: {format_bucket_size(total_size)}")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP S3 정보 수집 중 오류: {e}")
        handle_s3_specific_errors(e)
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP S3 Object Storage Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)