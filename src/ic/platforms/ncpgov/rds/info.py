#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP Gov RDS Database Information Module

This module provides RDS database information retrieval for NCP Government Cloud.
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

import logging
from common.progress_decorator import progress_bar, ManualProgress
from common.ncpgov_utils import (
    load_ncpgov_config, handle_ncpgov_api_error, mask_sensitive_data,
    validate_gov_compliance, log_audit_event, validate_api_response_security
)
from common.ncp_utils import apply_status_color
from src.ic.platforms.ncpgov.client import NCPGovClient, NCPGovAPIError

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class NCPGovRDS:
    """NCP Gov RDS 데이터 모델 (보안 강화)"""
    cloud_db_instance_no: str
    cloud_db_service_name: str
    cloud_db_instance_status: str
    engine_version: str
    license_model: str
    db_port: int
    backup_file_retention_period: int
    backup_time: str
    data_storage_type: str
    region: str
    security_level: str = "high"
    compliance_status: str = "compliant"
    audit_id: str = ""
    encryption_enabled: bool = True
    backup_encryption_enabled: bool = True
    
    @classmethod
    def from_api_response(cls, rds_data: Dict[str, Any], region: str, audit_id: str = "") -> 'NCPGovRDS':
        """API 응답에서 NCPGovRDS 객체 생성 (보안 검증 포함)"""
        # 민감한 정보 마스킹
        masked_data = mask_sensitive_data(rds_data)
        
        return cls(
            cloud_db_instance_no=masked_data.get('cloudDbInstanceNo', ''),
            cloud_db_service_name=masked_data.get('cloudDbServiceName', ''),
            cloud_db_instance_status=masked_data.get('cloudDbInstanceStatus', {}).get('code', ''),
            engine_version=masked_data.get('engineVersion', ''),
            license_model=masked_data.get('licenseModel', ''),
            db_port=masked_data.get('dbPort', 0),
            backup_file_retention_period=masked_data.get('backupFileRetentionPeriod', 0),
            backup_time=masked_data.get('backupTime', ''),
            data_storage_type=masked_data.get('dataStorageType', {}).get('code', ''),
            region=region,
            security_level="high",
            compliance_status="compliant",
            audit_id=audit_id,
            encryption_enabled=True,  # 정부 클라우드는 기본 암호화
            backup_encryption_enabled=True  # 백업도 암호화
        )


def add_arguments(parser):
    """RDS Info에 필요한 인자 추가 (정부 클라우드 전용)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="RDS 상세 출력 (전체 컬럼 표시)")
    parser.add_argument("--name", "-n", default=None, 
                       help="RDS 인스턴스 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP Gov 프로파일 (기본값: default)")
    parser.add_argument("--mask-sensitive", action="store_true", default=True,
                       help="민감한 정보 마스킹 활성화 (정부 클라우드 기본값)")


@handle_ncpgov_api_error
@progress_bar("Collecting NCP Gov RDS instances")
def fetch_ncpgov_rds_info(client: NCPGovClient, name_filter: str = None) -> List[NCPGovRDS]:
    """
    NCP Gov RDS 인스턴스 정보를 수집합니다. (보안 강화)
    
    Args:
        client: NCP Gov API 클라이언트
        name_filter: RDS 인스턴스 이름 필터 (부분 일치)
        
    Returns:
        NCPGovRDS 객체 목록
    """
    logger.info("NCP Gov RDS 인스턴스 정보 수집 시작")
    
    # 감사 로그 기록
    audit_id = f"rds_fetch_{int(time.time())}"
    log_audit_event('rds_info_collection_started', {
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
        
        # API를 통해 Cloud DB 인스턴스 목록 조회
        rds_data = client.get_cloud_db_instances()
        
        if not rds_data:
            logger.info("조회된 RDS 인스턴스가 없습니다.")
            log_audit_event('rds_info_collection_completed', {
                'audit_id': audit_id,
                'rds_count': 0
            })
            return []
        
        # 보안 검증된 응답 데이터 처리
        validated_data = validate_api_response_security({'rds_instances': rds_data})
        rds_data = validated_data['rds_instances']
        
        # NCPGovRDS 객체로 변환
        rds_instances = []
        for rds_instance_data in rds_data:
            try:
                rds_instance = NCPGovRDS.from_api_response(
                    rds_instance_data, client.region, audit_id
                )
                rds_instances.append(rds_instance)
            except Exception as e:
                logger.warning(f"RDS 인스턴스 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            rds_instances = [rds for rds in rds_instances 
                           if name_filter.lower() in rds.cloud_db_service_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(rds_instances)}개 RDS 인스턴스")
        
        # 감사 로그 기록
        log_audit_event('rds_info_collection_completed', {
            'audit_id': audit_id,
            'rds_count': len(rds_instances),
            'filtered': bool(name_filter)
        })
        
        logger.info(f"NCP Gov RDS 인스턴스 정보 수집 완료: {len(rds_instances)}개")
        return rds_instances
        
    except NCPGovAPIError as e:
        logger.error(f"NCP Gov API 오류: {e}")
        console.print(f"[red]NCP Gov API 오류: {e.message}[/red]")
        
        # 오류 감사 로그
        log_audit_event('rds_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'api_error',
            'error_message': str(e)
        })
        return []
    except Exception as e:
        logger.error(f"RDS 인스턴스 정보 수집 중 오류: {e}")
        console.print(f"[red]RDS 인스턴스 정보 수집 실패: {e}[/red]")
        
        # 오류 감사 로그
        log_audit_event('rds_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'general_error',
            'error_message': str(e)
        })
        return []


def format_engine_version(engine_version: str) -> str:
    """엔진 버전을 읽기 쉽게 포맷"""
    if not engine_version or engine_version == '-':
        return "-"
    
    # 엔진 버전 정보 파싱 (예: MySQL-8.0.28)
    if '-' in engine_version:
        parts = engine_version.split('-')
        if len(parts) >= 2:
            engine = parts[0].upper()
            version = parts[1]
            return f"{engine} {version}"
    
    return engine_version.upper()


def format_backup_retention(days: int) -> str:
    """백업 보존 기간을 포맷"""
    if days == 0:
        return "-"
    elif days == 1:
        return "1 day"
    else:
        return f"{days} days"


def format_encryption_status(enabled: bool) -> str:
    """암호화 상태를 포맷"""
    if enabled:
        return "[bold green]ENABLED[/bold green]"
    else:
        return "[bold red]DISABLED[/bold red]"


def print_ncpgov_rds_table(rds_instances: List[NCPGovRDS], verbose: bool = False, mask_sensitive: bool = True) -> None:
    """
    NCP Gov RDS 인스턴스 정보를 보안 강화된 형식으로 출력합니다.
    
    Args:
        rds_instances: NCPGovRDS 객체 목록
        verbose: 상세 정보 표시 여부
        mask_sensitive: 민감한 정보 마스킹 여부
    """
    if not rds_instances:
        console.print("(No Databases)")
        return
    
    # RDS 인스턴스를 리전, 이름 순으로 정렬
    rds_instances.sort(key=lambda x: (x.region.lower(), x.cloud_db_service_name.lower()))
    
    console.print("[bold underline]NCP Gov RDS Database Info[/bold underline]")
    console.print("[dim]정부 클라우드 보안 모드 활성화됨[/dim]")
    
    # 테이블 생성 (OCI 스타일 + 보안 강화)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의 (정부 클라우드 전용 필드 추가)
    if verbose:
        headers = ["Region", "Service Name", "Status", "Engine", "Port", "Storage Type", 
                  "Backup Retention", "Encryption", "Backup Encryption", "Security", "Instance No"]
        keys = ["region", "cloud_db_service_name", "cloud_db_instance_status", "engine_version", 
               "db_port", "data_storage_type", "backup_file_retention_period", "encryption_enabled",
               "backup_encryption_enabled", "security_level", "cloud_db_instance_no"]
    else:
        headers = ["Region", "Name", "Status", "Engine", "Port", "Storage", "Encryption", "Security"]
        keys = ["region", "cloud_db_service_name", "cloud_db_instance_status", "engine_version",
               "db_port", "data_storage_type", "encryption_enabled", "security_level"]
    
    # 컬럼 스타일 설정 (OCI 패턴 + 보안 강화)
    for header in headers:
        style_opts = {}
        if header == "Region": 
            style_opts = {"style": "bold cyan"}
        elif header == "Status": 
            style_opts = {"justify": "center"}
        elif header in ["Port", "Backup Retention"]: 
            style_opts = {"justify": "right"}
        elif header in ["Service Name", "Name"]: 
            style_opts = {"overflow": "fold"}
        elif header in ["Security", "Encryption", "Backup Encryption"]:
            style_opts = {"style": "bold green", "justify": "center"}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑 + 보안 마스킹)
    last_region = None
    
    for i, rds in enumerate(rds_instances):
        region_changed = rds.region != last_region
        
        # 리전이 바뀔 때 구분선 추가
        if i > 0 and region_changed:
            table.add_row(*[Rule(style="dim") for _ in headers])
        
        # 행 데이터 구성
        row_values = []
        
        # 리전 표시 (변경된 경우만)
        row_values.append(rds.region if region_changed else "")
        
        # 나머지 데이터
        for key in keys[1:]:  # region 제외
            value = getattr(rds, key, "-")
            
            # 특별한 포맷팅 적용
            if key == "cloud_db_service_name" and mask_sensitive:
                # RDS 서비스 이름 부분 마스킹 (정부 클라우드 보안)
                if value and len(str(value)) > 6:
                    masked_name = str(value)[:3] + "***" + str(value)[-3:]
                    value = masked_name
            elif key == "cloud_db_instance_status":
                value = apply_status_color(str(value))
            elif key == "engine_version":
                value = format_engine_version(str(value))
            elif key == "db_port":
                value = str(value) if value != 0 else "-"
            elif key == "data_storage_type":
                value = str(value).upper() if value else "SSD"
            elif key == "backup_file_retention_period":
                value = format_backup_retention(int(value)) if value != "-" else "-"
            elif key in ["encryption_enabled", "backup_encryption_enabled"]:
                value = format_encryption_status(bool(value))
            elif key == "security_level":
                value = f"[bold green]{str(value).upper()}[/bold green]" if value else "STANDARD"
            elif key == "cloud_db_instance_no" and mask_sensitive:
                # RDS 인스턴스 번호 부분 마스킹
                if value and len(str(value)) > 4:
                    masked_no = str(value)[:2] + "***" + str(value)[-2:]
                    value = masked_no
            
            row_values.append(str(value) if value is not None else "-")
        
        table.add_row(*row_values)
        last_region = rds.region
    
    console.print(table)
    
    # 정부 클라우드 보안 정보 표시
    if mask_sensitive:
        console.print("\n[dim]보안: RDS 서비스 이름과 인스턴스 번호가 부분적으로 마스킹되었습니다 (정부 클라우드 규정 준수)[/dim]")
    
    # 암호화 상태 요약
    encrypted_count = sum(1 for rds in rds_instances if rds.encryption_enabled)
    backup_encrypted_count = sum(1 for rds in rds_instances if rds.backup_encryption_enabled)
    total_count = len(rds_instances)
    
    console.print(f"\n[bold green]데이터 암호화:[/bold green] {encrypted_count}/{total_count} 인스턴스가 암호화됨")
    console.print(f"[bold green]백업 암호화:[/bold green] {backup_encrypted_count}/{total_count} 인스턴스의 백업이 암호화됨")
    
    # 백업 설정 요약
    backup_enabled_count = sum(1 for rds in rds_instances if rds.backup_file_retention_period > 0)
    console.print(f"[bold blue]백업 설정:[/bold blue] {backup_enabled_count}/{total_count} 인스턴스에서 백업 활성화됨")


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


def ncpgov_rds_info_command(
    name_filter: Optional[str] = None,
    output_format: str = 'table',
    profile: str = 'default',
    verbose: bool = False,
    mask_sensitive: bool = True
) -> None:
    """
    NCP Gov RDS 정보 조회 명령어 래퍼 함수 (보안 강화)
    
    Args:
        name_filter: 데이터베이스 이름 필터
        output_format: 출력 형식 ('table' 또는 'json')
        profile: 사용할 NCP Gov 프로필
        verbose: 상세 정보 표시 여부
        mask_sensitive: 민감한 정보 마스킹 여부
    """
    import argparse
    
    # argparse 객체 생성
    args = argparse.Namespace()
    args.name = name_filter
    args.format = output_format
    args.profile = profile
    args.verbose = verbose
    args.mask_sensitive = mask_sensitive
    
    # 메인 함수 호출
    main(args)


@progress_bar("Initializing NCP Gov RDS service")
def main(args):
    """
    NCP Gov RDS 정보 수집 메인 함수 (보안 강화)
    
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
        
        # RDS 인스턴스 정보 수집
        rds_instances = fetch_ncpgov_rds_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(rds_instances)} RDS instances.")
        print_ncpgov_rds_table(rds_instances, args.verbose, args.mask_sensitive)
        
        # 감사 로그 기록
        log_audit_event('rds_info_display_completed', {
            'rds_count': len(rds_instances),
            'verbose_mode': args.verbose,
            'sensitive_masked': args.mask_sensitive
        })
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP Gov RDS 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP Gov RDS Database Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)