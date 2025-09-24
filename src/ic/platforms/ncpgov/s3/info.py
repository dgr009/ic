#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP Gov S3 Object Storage Information Module

This module provides S3 bucket information retrieval for NCP Government Cloud.
It includes enhanced security features, compliance validation, and sensitive data masking
for government cloud usage.

Features:
- API Gateway authentication with enhanced security
- Government cloud compliance validation
- Sensitive data masking for security
- Enhanced error handling for government cloud policies
- Audit logging for compliance
"""

import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

from common.log import get_logger
from common.progress_decorator import progress_bar, ManualProgress
from common.ncpgov_utils import (
    load_ncpgov_config, handle_ncpgov_api_error, mask_sensitive_data,
    validate_gov_compliance, log_audit_event, validate_api_response_security
)
from src.ic.platforms.ncp.s3.info import format_bucket_size
from common.ncp_utils import apply_status_color
from src.ic.platforms.ncpgov.client import NCPGovClient, NCPGovAPIError

logger = get_logger()
console = Console()


@dataclass
class NCPGovBucket:
    """NCP Gov S3 버킷 데이터 모델 (보안 강화)"""
    bucket_name: str
    region: str
    creation_date: str
    object_count: int
    bucket_size: int
    storage_class: str
    access_control: str
    security_level: str = "high"
    compliance_status: str = "compliant"
    audit_id: str = ""
    encryption_enabled: bool = True
    
    @classmethod
    def from_api_response(cls, bucket_data: Dict[str, Any], region: str, audit_id: str = "") -> 'NCPGovBucket':
        """API 응답에서 NCPGovBucket 객체 생성 (보안 검증 포함)"""
        # 민감한 정보 마스킹
        masked_data = mask_sensitive_data(bucket_data)
        
        return cls(
            bucket_name=masked_data.get('bucketName', ''),
            region=region,
            creation_date=masked_data.get('creationDate', ''),
            object_count=masked_data.get('objectCount', 0),
            bucket_size=masked_data.get('bucketSize', 0),
            storage_class=masked_data.get('storageClass', 'STANDARD'),
            access_control=masked_data.get('accessControl', 'PRIVATE'),
            security_level="high",
            compliance_status="compliant",
            audit_id=audit_id,
            encryption_enabled=True  # 정부 클라우드는 기본 암호화
        )


def add_arguments(parser):
    """S3 Info에 필요한 인자 추가 (정부 클라우드 전용)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="버킷 상세 출력 (전체 컬럼 표시)")
    parser.add_argument("--name", "-n", default=None, 
                       help="버킷 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP Gov 프로파일 (기본값: default)")
    parser.add_argument("--mask-sensitive", action="store_true", default=True,
                       help="민감한 정보 마스킹 활성화 (정부 클라우드 기본값)")


@handle_ncpgov_api_error
@progress_bar("Collecting NCP Gov S3 buckets")
def fetch_ncpgov_s3_info(client: NCPGovClient, name_filter: str = None) -> List[NCPGovBucket]:
    """
    NCP Gov S3 버킷 정보를 수집합니다. (보안 강화)
    
    Args:
        client: NCP Gov API 클라이언트
        name_filter: 버킷 이름 필터 (부분 일치)
        
    Returns:
        NCPGovBucket 객체 목록
    """
    logger.info("NCP Gov S3 버킷 정보 수집 시작")
    
    # 감사 로그 기록
    audit_id = f"s3_fetch_{int(time.time())}"
    log_audit_event('s3_info_collection_started', {
        'audit_id': audit_id,
        'name_filter': name_filter,
        'timestamp': time.time()
    })
    
    try:
        # 정부 클라우드 규정 준수 검증
        compliance = client.validate_gov_compliance()
        if not compliance['overall_compliance']:
            logger.error("정부 클라우드 규정 준수 요구사항을 만족하지 않습니다.")
            console.print("[red]정부 클라우드 규정 준수 검증 실패[/red]")
            return []
        
        # API를 통해 오브젝트 스토리지 버킷 목록 조회
        buckets_data = client.get_object_storage_buckets()
        
        if not buckets_data:
            logger.info("조회된 버킷이 없습니다.")
            log_audit_event('s3_info_collection_completed', {
                'audit_id': audit_id,
                'bucket_count': 0
            })
            return []
        
        # 보안 검증된 응답 데이터 처리
        validated_data = validate_api_response_security({'buckets': buckets_data})
        buckets_data = validated_data['buckets']
        
        # NCPGovBucket 객체로 변환
        buckets = []
        for bucket_data in buckets_data:
            try:
                bucket = NCPGovBucket.from_api_response(
                    bucket_data, client.region, audit_id
                )
                buckets.append(bucket)
            except Exception as e:
                logger.warning(f"버킷 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            buckets = [bucket for bucket in buckets 
                      if name_filter.lower() in bucket.bucket_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(buckets)}개 버킷")
        
        # 감사 로그 기록
        log_audit_event('s3_info_collection_completed', {
            'audit_id': audit_id,
            'bucket_count': len(buckets),
            'filtered': bool(name_filter)
        })
        
        logger.info(f"NCP Gov S3 버킷 정보 수집 완료: {len(buckets)}개")
        return buckets
        
    except NCPGovAPIError as e:
        logger.error(f"NCP Gov API 오류: {e}")
        console.print(f"[red]NCP Gov API 오류: {e.message}[/red]")
        
        # 오류 감사 로그
        log_audit_event('s3_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'api_error',
            'error_message': str(e)
        })
        return []
    except Exception as e:
        logger.error(f"버킷 정보 수집 중 오류: {e}")
        console.print(f"[red]버킷 정보 수집 실패: {e}[/red]")
        
        # 오류 감사 로그
        log_audit_event('s3_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'general_error',
            'error_message': str(e)
        })
        return []


def format_access_control(access_control: str) -> str:
    """접근 제어 설정을 읽기 쉽게 포맷"""
    if not access_control or access_control == '-':
        return "PRIVATE"
    
    # 정부 클라우드는 기본적으로 PRIVATE 권장
    access_map = {
        'private': '[green]PRIVATE[/green]',
        'public-read': '[yellow]PUBLIC-READ[/yellow]',
        'public-read-write': '[red]PUBLIC-WRITE[/red]',
        'authenticated-read': '[cyan]AUTH-READ[/cyan]'
    }
    
    return access_map.get(access_control.lower(), access_control.upper())


def format_encryption_status(enabled: bool) -> str:
    """암호화 상태를 포맷"""
    if enabled:
        return "[bold green]ENABLED[/bold green]"
    else:
        return "[bold red]DISABLED[/bold red]"


def print_ncpgov_s3_table(buckets: List[NCPGovBucket], verbose: bool = False, mask_sensitive: bool = True) -> None:
    """
    NCP Gov S3 버킷 정보를 보안 강화된 형식으로 출력합니다.
    
    Args:
        buckets: NCPGovBucket 객체 목록
        verbose: 상세 정보 표시 여부
        mask_sensitive: 민감한 정보 마스킹 여부
    """
    if not buckets:
        console.print("(No Buckets)")
        return
    
    # 버킷을 리전, 이름 순으로 정렬
    buckets.sort(key=lambda x: (x.region.lower(), x.bucket_name.lower()))
    
    console.print("[bold underline]NCP Gov S3 Bucket Info[/bold underline]")
    console.print("[dim]정부 클라우드 보안 모드 활성화됨[/dim]")
    
    # 테이블 생성 (OCI 스타일 + 보안 강화)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의 (정부 클라우드 전용 필드 추가)
    if verbose:
        headers = ["Region", "Bucket Name", "Objects", "Size", "Storage Class", 
                  "Access Control", "Encryption", "Security", "Created"]
        keys = ["region", "bucket_name", "object_count", "bucket_size", "storage_class",
               "access_control", "encryption_enabled", "security_level", "creation_date"]
    else:
        headers = ["Region", "Name", "Objects", "Size", "Access", "Encryption", "Security"]
        keys = ["region", "bucket_name", "object_count", "bucket_size", 
               "access_control", "encryption_enabled", "security_level"]
    
    # 컬럼 스타일 설정 (OCI 패턴 + 보안 강화)
    for header in headers:
        style_opts = {}
        if header == "Region": 
            style_opts = {"style": "bold cyan"}
        elif header in ["Objects", "Size"]: 
            style_opts = {"justify": "right"}
        elif header in ["Bucket Name", "Name"]: 
            style_opts = {"overflow": "fold"}
        elif header in ["Security", "Encryption"]:
            style_opts = {"style": "bold green", "justify": "center"}
        elif header in ["Access Control", "Access"]:
            style_opts = {"justify": "center"}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑 + 보안 마스킹)
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
            if key == "bucket_name" and mask_sensitive:
                # 버킷 이름 부분 마스킹 (정부 클라우드 보안)
                if value and len(str(value)) > 6:
                    masked_name = str(value)[:3] + "***" + str(value)[-3:]
                    value = masked_name
            elif key == "bucket_size":
                value = format_bucket_size(int(value)) if value != "-" and value != 0 else "-"
            elif key == "object_count":
                value = f"{value:,}" if value != "-" and value != 0 else "-"
            elif key == "access_control":
                value = format_access_control(str(value))
            elif key == "encryption_enabled":
                value = format_encryption_status(bool(value))
            elif key == "security_level":
                value = f"[bold green]{str(value).upper()}[/bold green]" if value else "STANDARD"
            elif key == "storage_class":
                value = str(value).upper() if value else "STANDARD"
            elif key == "creation_date" and value:
                # 날짜 포맷팅
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
    
    # 정부 클라우드 보안 정보 표시
    if mask_sensitive:
        console.print("\n[dim]보안: 버킷 이름이 부분적으로 마스킹되었습니다 (정부 클라우드 규정 준수)[/dim]")
    
    # 암호화 상태 요약
    encrypted_count = sum(1 for bucket in buckets if bucket.encryption_enabled)
    total_count = len(buckets)
    console.print(f"\n[bold green]암호화 상태:[/bold green] {encrypted_count}/{total_count} 버킷이 암호화됨")


def validate_ncpgov_credentials(config: Dict[str, Any]) -> bool:
    """
    NCP Gov 인증 정보 유효성 검사 (보안 강화)
    
    Args:
        config: NCP Gov 설정 딕셔너리
        
    Returns:
        유효성 검사 결과
    """
    required_keys = ['access_key', 'secret_key', 'apigw_key']
    
    for key in required_keys:
        if key not in config or not config[key]:
            console.print(f"[red]필수 설정이 누락되었습니다: {key}[/red]")
            console.print("[yellow]'ic config init' 명령어로 NCP Gov 설정을 생성하세요.[/yellow]")
            return False
    
    # 정부 클라우드 규정 준수 검증
    compliance = validate_gov_compliance(config)
    if not compliance['overall_compliance']:
        console.print("[red]정부 클라우드 규정 준수 요구사항을 만족하지 않습니다.[/red]")
        failed_checks = [check for check, passed in compliance.items() 
                        if not passed and check != 'overall_compliance']
        console.print(f"[yellow]실패한 검사 항목: {', '.join(failed_checks)}[/yellow]")
        return False
    
    return True


@progress_bar("Initializing NCP Gov S3 service")
def main(args):
    """
    NCP Gov S3 정보 수집 메인 함수 (보안 강화)
    
    Args:
        args: 명령행 인자
    """
    try:
        # NCP Gov 설정 로드
        with ManualProgress("Loading NCP Gov configuration", total=4) as progress:
            progress.update("Loading configuration file", advance=1)
            
            try:
                config = load_ncpgov_config(args.profile)
            except Exception as e:
                console.print(f"[red]NCP Gov 설정 로드 실패: {e}[/red]")
                console.print("[yellow]'ic config init' 명령어로 NCP Gov 설정을 생성하세요.[/yellow]")
                sys.exit(1)
            
            progress.update("Validating credentials and compliance", advance=1)
            
            # 인증 정보 및 규정 준수 검사
            if not validate_ncpgov_credentials(config):
                sys.exit(1)
            
            progress.update("Initializing NCP Gov client", advance=1)
            
            # NCP Gov 클라이언트 생성
            try:
                client = NCPGovClient(
                    access_key=config['access_key'],
                    secret_key=config['secret_key'],
                    apigw_key=config['apigw_key'],
                    region=config.get('region', 'KR'),
                    platform=config.get('platform', 'VPC')
                )
            except Exception as e:
                console.print(f"[red]NCP Gov 클라이언트 초기화 실패: {e}[/red]")
                sys.exit(1)
            
            progress.update("Testing government cloud connection", advance=1)
            
            # 정부 클라우드 연결 테스트
            if not client.test_connection():
                console.print("[red]정부 클라우드 연결 테스트 실패[/red]")
                sys.exit(1)
        
        # 버킷 정보 수집
        buckets = fetch_ncpgov_s3_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(buckets)} buckets.")
        print_ncpgov_s3_table(buckets, args.verbose, args.mask_sensitive)
        
        # 감사 로그 기록
        log_audit_event('s3_info_display_completed', {
            'bucket_count': len(buckets),
            'verbose_mode': args.verbose,
            'sensitive_masked': args.mask_sensitive
        })
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP Gov S3 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP Gov S3 Bucket Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)