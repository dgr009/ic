#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP RDS (Cloud DB) Information Module

This module provides Cloud DB instance information retrieval for NCP (Naver Cloud Platform).
It follows the same architectural patterns as the OCI and EC2 modules for consistent user experience.

Features:
- HMAC-SHA256 signature authentication
- Support for both Classic and VPC platforms
- Database engine type and version display
- OCI-style table formatting
- Progress indicators for long operations
- RDS-specific error handling
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
    filter_resources_by_name, validate_platform_support
)
from src.ic.platforms.ncp.client import NCPClient, NCPAPIError

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class NCPCloudDB:
    """NCP Cloud DB 인스턴스 데이터 모델"""
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
    zone: str
    create_date: str
    cpu_count: int
    memory_size: int
    data_storage_size: int
    
    @classmethod
    def from_api_response(cls, db_data: Dict[str, Any], region: str) -> 'NCPCloudDB':
        """API 응답에서 NCPCloudDB 객체 생성"""
        return cls(
            cloud_db_instance_no=db_data.get('cloudDbInstanceNo', ''),
            cloud_db_service_name=db_data.get('cloudDbServiceName', ''),
            cloud_db_instance_status=db_data.get('cloudDbInstanceStatus', {}).get('code', ''),
            engine_version=db_data.get('engineVersion', ''),
            license_model=db_data.get('licenseModel', {}).get('code', ''),
            db_port=db_data.get('dbPort', 0),
            backup_file_retention_period=db_data.get('backupFileRetentionPeriod', 0),
            backup_time=db_data.get('backupTime', ''),
            data_storage_type=db_data.get('dataStorageType', {}).get('code', ''),
            region=region,
            zone=db_data.get('zone', {}).get('zoneName', ''),
            create_date=db_data.get('createDate', ''),
            cpu_count=db_data.get('cpuCount', 0),
            memory_size=db_data.get('memorySize', 0),
            data_storage_size=db_data.get('dataStorageSize', 0)
        )


def add_arguments(parser):
    """RDS Info에 필요한 인자 추가 (OCI 패턴과 동일)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="데이터베이스 상세 출력 (전체 컬럼 표시)")
    parser.add_argument("--name", "-n", default=None, 
                       help="데이터베이스 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP 프로파일 (기본값: default)")


@handle_ncp_api_error
@progress_bar("Collecting NCP Cloud DB instances")
def fetch_ncp_rds_info(client: NCPClient, name_filter: str = None) -> List[NCPCloudDB]:
    """
    NCP Cloud DB 인스턴스 정보를 수집합니다.
    
    Args:
        client: NCP API 클라이언트
        name_filter: 데이터베이스 이름 필터 (부분 일치)
        
    Returns:
        NCPCloudDB 객체 목록
    """
    logger.info("NCP Cloud DB 인스턴스 정보 수집 시작")
    
    try:
        # API를 통해 Cloud DB 인스턴스 목록 조회
        db_instances_data = client.get_cloud_db_instances()
        
        if not db_instances_data:
            logger.info("조회된 데이터베이스 인스턴스가 없습니다.")
            return []
        
        # NCPCloudDB 객체로 변환
        db_instances = []
        for db_data in db_instances_data:
            try:
                db_instance = NCPCloudDB.from_api_response(db_data, client.region)
                db_instances.append(db_instance)
            except Exception as e:
                logger.warning(f"데이터베이스 인스턴스 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            db_instances = [db for db in db_instances 
                           if name_filter.lower() in db.cloud_db_service_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(db_instances)}개 인스턴스")
        
        logger.info(f"NCP Cloud DB 인스턴스 정보 수집 완료: {len(db_instances)}개")
        return db_instances
        
    except NCPAPIError as e:
        logger.error(f"NCP API 오류: {e}")
        console.print(f"[red]NCP API 오류: {e.message}[/red]")
        return []
    except Exception as e:
        logger.error(f"데이터베이스 인스턴스 정보 수집 중 오류: {e}")
        console.print(f"[red]데이터베이스 인스턴스 정보 수집 실패: {e}[/red]")
        return []


def format_storage_size(size_gb: int) -> str:
    """스토리지 크기를 읽기 쉽게 포맷"""
    if size_gb == 0:
        return "-"
    
    if size_gb < 1024:
        return f"{size_gb}GB"
    else:
        size_tb = size_gb / 1024
        return f"{size_tb:.1f}TB"


def format_memory_size(memory_bytes: int) -> str:
    """메모리 크기를 GB 단위로 포맷"""
    if memory_bytes == 0:
        return "-"
    
    # NCP API는 보통 바이트 단위로 반환
    memory_gb = memory_bytes / (1024 ** 3)
    if memory_gb < 1:
        memory_mb = memory_bytes / (1024 ** 2)
        return f"{memory_mb:.0f}MB"
    else:
        return f"{memory_gb:.1f}GB"


def format_engine_version(engine_version: str) -> str:
    """엔진 버전을 읽기 쉽게 포맷"""
    if not engine_version or engine_version == '-':
        return "-"
    
    # 엔진 타입과 버전 분리 (예: MYSQL5.7 -> MySQL 5.7)
    engine_version = engine_version.upper()
    
    if engine_version.startswith('MYSQL'):
        version = engine_version.replace('MYSQL', '')
        return f"MySQL {version}"
    elif engine_version.startswith('MARIADB'):
        version = engine_version.replace('MARIADB', '')
        return f"MariaDB {version}"
    elif engine_version.startswith('POSTGRESQL'):
        version = engine_version.replace('POSTGRESQL', '')
        return f"PostgreSQL {version}"
    elif engine_version.startswith('REDIS'):
        version = engine_version.replace('REDIS', '')
        return f"Redis {version}"
    
    return engine_version


def format_backup_retention(retention_days: int) -> str:
    """백업 보존 기간을 포맷"""
    if retention_days == 0:
        return "Disabled"
    elif retention_days == 1:
        return "1 day"
    else:
        return f"{retention_days} days"


def print_ncp_rds_table(db_instances: List[NCPCloudDB], verbose: bool = False) -> None:
    """
    NCP Cloud DB 인스턴스 정보를 OCI 스타일과 유사한 형식으로 출력합니다.
    
    Args:
        db_instances: NCPCloudDB 객체 목록
        verbose: 상세 정보 표시 여부
    """
    if not db_instances:
        console.print("(No Databases)")
        return
    
    # 인스턴스를 리전, 존, 이름 순으로 정렬
    db_instances.sort(key=lambda x: (x.region.lower(), x.zone.lower(), x.cloud_db_service_name.lower()))
    
    console.print("[bold underline]NCP Cloud DB Instance Info[/bold underline]")
    
    # 테이블 생성 (OCI 스타일)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의
    if verbose:
        headers = ["Region", "Zone", "DB Name", "Status", "Engine", "CPU", "Memory", 
                  "Storage", "Port", "Backup", "License", "Created"]
        keys = ["region", "zone", "cloud_db_service_name", "cloud_db_instance_status", 
               "engine_version", "cpu_count", "memory_size", "data_storage_size", 
               "db_port", "backup_file_retention_period", "license_model", "create_date"]
    else:
        headers = ["Region", "Zone", "DB Name", "Status", "Engine", "CPU", "Memory", "Storage"]
        keys = ["region", "zone", "cloud_db_service_name", "cloud_db_instance_status", 
               "engine_version", "cpu_count", "memory_size", "data_storage_size"]
    
    # 컬럼 스타일 설정 (OCI 패턴)
    for header in headers:
        style_opts = {}
        if header in ["Region", "Zone"]: 
            style_opts = {"style": "bold cyan"}
        elif header == "Status": 
            style_opts = {"justify": "center"}
        elif header in ["CPU", "Memory", "Storage", "Port"]: 
            style_opts = {"justify": "right"}
        elif header in ["DB Name"]: 
            style_opts = {"overflow": "fold"}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑)
    last_region = None
    last_zone = None
    
    for i, db_instance in enumerate(db_instances):
        region_changed = db_instance.region != last_region
        zone_changed = db_instance.zone != last_zone
        
        # 리전이 바뀔 때 구분선 추가
        if i > 0 and region_changed:
            table.add_row(*[Rule(style="dim") for _ in headers])
        # 같은 리전 내에서 존이 바뀔 때 작은 구분선 추가
        elif i > 0 and zone_changed:
            table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
        
        # 행 데이터 구성
        row_values = []
        
        # 리전 표시 (변경된 경우만)
        row_values.append(db_instance.region if region_changed else "")
        
        # 존 표시 (변경된 경우만)
        row_values.append(db_instance.zone if region_changed or zone_changed else "")
        
        # 나머지 데이터
        for key in keys[2:]:  # region, zone 제외
            value = getattr(db_instance, key, "-")
            
            # 특별한 포맷팅 적용
            if key == "cloud_db_instance_status":
                value = apply_status_color(str(value))
            elif key == "engine_version":
                value = format_engine_version(str(value))
            elif key == "memory_size":
                value = format_memory_size(int(value)) if value != "-" else "-"
            elif key == "data_storage_size":
                value = format_storage_size(int(value)) if value != "-" else "-"
            elif key == "cpu_count":
                value = str(value) if value != 0 else "-"
            elif key == "db_port":
                value = str(value) if value != 0 else "-"
            elif key == "backup_file_retention_period":
                value = format_backup_retention(int(value)) if value != "-" else "-"
            elif key == "license_model":
                value = str(value).replace('_', ' ').title() if value != "-" else "-"
            elif key == "create_date" and value:
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
        
        last_region = db_instance.region
        last_zone = db_instance.zone
    
    console.print(table)


def validate_ncp_credentials(config: Dict[str, Any]) -> bool:
    """
    NCP 인증 정보 유효성 검사
    
    Args:
        config: NCP 설정 딕셔너리
        
    Returns:
        유효성 검사 결과
    """
    required_keys = ['access_key', 'secret_key']
    
    for key in required_keys:
        if key not in config or not config[key]:
            console.print(f"[red]필수 설정이 누락되었습니다: {key}[/red]")
            console.print("[yellow]'ic config init' 명령어로 NCP 설정을 생성하세요.[/yellow]")
            return False
    
    return True


def ncp_rds_info_command(
    name_filter: Optional[str] = None,
    output_format: str = 'table',
    profile: str = 'default',
    verbose: bool = False
) -> None:
    """
    NCP RDS 정보 조회 명령어 래퍼 함수
    
    Args:
        name_filter: 데이터베이스 이름 필터
        output_format: 출력 형식 ('table' 또는 'json')
        profile: 사용할 NCP 프로필
        verbose: 상세 정보 표시 여부
    """
    import argparse
    
    # argparse 객체 생성
    args = argparse.Namespace()
    args.name = name_filter
    args.format = output_format
    args.profile = profile
    args.verbose = verbose
    
    # 메인 함수 호출
    main(args)


@progress_bar("Initializing NCP RDS service")
def main(args):
    """
    NCP Cloud DB 정보 수집 메인 함수
    
    Args:
        args: 명령행 인자
    """
    try:
        # NCP 설정 로드
        with ManualProgress("Loading NCP configuration", total=3) as progress:
            progress.update("Loading configuration file", advance=1)
            
            try:
                config = load_ncp_config(args.profile)
            except Exception as e:
                console.print(f"[red]NCP 설정 로드 실패: {e}[/red]")
                console.print("[yellow]'ic config init' 명령어로 NCP 설정을 생성하세요.[/yellow]")
                sys.exit(1)
            
            progress.update("Validating credentials", advance=1)
            
            # 인증 정보 유효성 검사
            if not validate_ncp_credentials(config):
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
        
        # 플랫폼 지원 여부 확인
        if not validate_platform_support(client.platform, 'rds'):
            console.print(f"[yellow]Cloud DB 서비스는 {client.platform} 플랫폼에서 지원됩니다.[/yellow]")
        
        # 데이터베이스 인스턴스 정보 수집
        db_instances = fetch_ncp_rds_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(db_instances)} database instances.")
        print_ncp_rds_table(db_instances, args.verbose)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP Cloud DB 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP Cloud DB Instance Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)