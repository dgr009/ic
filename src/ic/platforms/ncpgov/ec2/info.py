#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP Gov EC2 Instance Information Module

This module provides EC2 instance information retrieval for NCP Government Cloud.
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
from src.ic.platforms.ncp.ec2.info import NCPInstance, format_memory_size, format_instance_type
from common.ncp_utils import apply_status_color
from src.ic.platforms.ncpgov.client import NCPGovClient, NCPGovAPIError

logger = get_logger()
console = Console()


@dataclass
class NCPGovInstance(NCPInstance):
    """NCP Gov 인스턴스 데이터 모델 (보안 강화)"""
    security_level: str = "high"
    compliance_status: str = "compliant"
    audit_id: str = ""
    
    @classmethod
    def from_api_response(cls, instance_data: Dict[str, Any], region: str, audit_id: str = "") -> 'NCPGovInstance':
        """API 응답에서 NCPGovInstance 객체 생성 (보안 검증 포함)"""
        # 민감한 정보 마스킹
        masked_data = mask_sensitive_data(instance_data)
        
        # 기본 인스턴스 정보 생성
        base_instance = NCPInstance.from_api_response(masked_data, region)
        
        # 정부 클라우드 전용 필드 추가
        return cls(
            server_instance_no=base_instance.server_instance_no,
            server_name=base_instance.server_name,
            server_instance_status=base_instance.server_instance_status,
            server_instance_type=base_instance.server_instance_type,
            cpu_count=base_instance.cpu_count,
            memory_size=base_instance.memory_size,
            platform_type=base_instance.platform_type,
            public_ip=base_instance.public_ip,
            private_ip=base_instance.private_ip,
            vpc_name=base_instance.vpc_name,
            subnet_name=base_instance.subnet_name,
            region=region,
            zone=base_instance.zone,
            create_date=base_instance.create_date,
            security_level="high",
            compliance_status="compliant",
            audit_id=audit_id
        )


def add_arguments(parser):
    """EC2 Info에 필요한 인자 추가 (정부 클라우드 전용)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="인스턴스 상세 출력 (전체 컬럼 표시)")
    parser.add_argument("--name", "-n", default=None, 
                       help="인스턴스 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP Gov 프로파일 (기본값: default)")
    parser.add_argument("--mask-sensitive", action="store_true", default=True,
                       help="민감한 정보 마스킹 활성화 (정부 클라우드 기본값)")


@handle_ncpgov_api_error
@progress_bar("Collecting NCP Gov EC2 instances")
def fetch_ncpgov_ec2_info(client: NCPGovClient, name_filter: str = None) -> List[NCPGovInstance]:
    """
    NCP Gov EC2 인스턴스 정보를 수집합니다. (보안 강화)
    
    Args:
        client: NCP Gov API 클라이언트
        name_filter: 인스턴스 이름 필터 (부분 일치)
        
    Returns:
        NCPGovInstance 객체 목록
    """
    logger.info("NCP Gov EC2 인스턴스 정보 수집 시작")
    
    # 감사 로그 기록
    audit_id = f"ec2_fetch_{int(time.time())}"
    log_audit_event('ec2_info_collection_started', {
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
        
        # API를 통해 서버 인스턴스 목록 조회
        instances_data = client.get_server_instances()
        
        if not instances_data:
            logger.info("조회된 인스턴스가 없습니다.")
            log_audit_event('ec2_info_collection_completed', {
                'audit_id': audit_id,
                'instance_count': 0
            })
            return []
        
        # 보안 검증된 응답 데이터 처리
        validated_data = validate_api_response_security({'instances': instances_data})
        instances_data = validated_data['instances']
        
        # NCPGovInstance 객체로 변환
        instances = []
        for instance_data in instances_data:
            try:
                instance = NCPGovInstance.from_api_response(
                    instance_data, client.region, audit_id
                )
                instances.append(instance)
            except Exception as e:
                logger.warning(f"인스턴스 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            instances = [inst for inst in instances 
                        if name_filter.lower() in inst.server_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(instances)}개 인스턴스")
        
        # 감사 로그 기록
        log_audit_event('ec2_info_collection_completed', {
            'audit_id': audit_id,
            'instance_count': len(instances),
            'filtered': bool(name_filter)
        })
        
        logger.info(f"NCP Gov EC2 인스턴스 정보 수집 완료: {len(instances)}개")
        return instances
        
    except NCPGovAPIError as e:
        logger.error(f"NCP Gov API 오류: {e}")
        console.print(f"[red]NCP Gov API 오류: {e.message}[/red]")
        
        # 오류 감사 로그
        log_audit_event('ec2_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'api_error',
            'error_message': str(e)
        })
        return []
    except Exception as e:
        logger.error(f"인스턴스 정보 수집 중 오류: {e}")
        console.print(f"[red]인스턴스 정보 수집 실패: {e}[/red]")
        
        # 오류 감사 로그
        log_audit_event('ec2_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'general_error',
            'error_message': str(e)
        })
        return []


def print_ncpgov_ec2_table(instances: List[NCPGovInstance], verbose: bool = False, mask_sensitive: bool = True) -> None:
    """
    NCP Gov EC2 인스턴스 정보를 보안 강화된 형식으로 출력합니다.
    
    Args:
        instances: NCPGovInstance 객체 목록
        verbose: 상세 정보 표시 여부
        mask_sensitive: 민감한 정보 마스킹 여부
    """
    if not instances:
        console.print("(No Instances)")
        return
    
    # 인스턴스를 리전, 존, 이름 순으로 정렬
    instances.sort(key=lambda x: (x.region.lower(), x.zone.lower(), x.server_name.lower()))
    
    console.print("[bold underline]NCP Gov EC2 Instance Info[/bold underline]")
    console.print("[dim]정부 클라우드 보안 모드 활성화됨[/dim]")
    
    # 테이블 생성 (OCI 스타일 + 보안 강화)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의 (정부 클라우드 전용 필드 추가)
    if verbose:
        headers = ["Region", "Zone", "Instance Name", "Status", "Type", "CPU", "Memory", 
                  "Platform", "Private IP", "Public IP", "VPC", "Subnet", "Security", "Created"]
        keys = ["region", "zone", "server_name", "server_instance_status", "server_instance_type",
               "cpu_count", "memory_size", "platform_type", "private_ip", "public_ip", 
               "vpc_name", "subnet_name", "security_level", "create_date"]
    else:
        headers = ["Region", "Zone", "Name", "Status", "Type", "CPU", "Memory", "Private IP", "Security"]
        keys = ["region", "zone", "server_name", "server_instance_status", "server_instance_type",
               "cpu_count", "memory_size", "private_ip", "security_level"]
    
    # 컬럼 스타일 설정 (OCI 패턴 + 보안 강화)
    for header in headers:
        style_opts = {}
        if header in ["Region", "Zone"]: 
            style_opts = {"style": "bold cyan"}
        elif header == "Status": 
            style_opts = {"justify": "center"}
        elif header in ["CPU", "Memory"]: 
            style_opts = {"justify": "right"}
        elif header in ["Instance Name", "Name"]: 
            style_opts = {"overflow": "fold"}
        elif header == "Security":
            style_opts = {"style": "bold green", "justify": "center"}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑 + 보안 마스킹)
    last_region = None
    last_zone = None
    
    for i, instance in enumerate(instances):
        region_changed = instance.region != last_region
        zone_changed = instance.zone != last_zone
        
        # 리전이 바뀔 때 구분선 추가
        if i > 0 and region_changed:
            table.add_row(*[Rule(style="dim") for _ in headers])
        # 같은 리전 내에서 존이 바뀔 때 작은 구분선 추가
        elif i > 0 and zone_changed:
            table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
        
        # 행 데이터 구성
        row_values = []
        
        # 리전 표시 (변경된 경우만)
        row_values.append(instance.region if region_changed else "")
        
        # 존 표시 (변경된 경우만)
        row_values.append(instance.zone if region_changed or zone_changed else "")
        
        # 나머지 데이터
        for key in keys[2:]:  # region, zone 제외
            value = getattr(instance, key, "-")
            
            # 특별한 포맷팅 적용
            if key == "server_instance_status":
                value = apply_status_color(str(value))
            elif key == "server_instance_type":
                value = format_instance_type(str(value))
            elif key == "memory_size":
                value = format_memory_size(int(value)) if value != "-" else "-"
            elif key == "cpu_count":
                value = str(value) if value != 0 else "-"
            elif key == "security_level":
                value = f"[bold green]{value.upper()}[/bold green]" if value else "STANDARD"
            elif key in ["private_ip", "public_ip"] and mask_sensitive:
                # IP 주소 마스킹 (정부 클라우드 보안)
                if value and value != "-":
                    parts = str(value).split('.')
                    if len(parts) == 4:
                        value = f"{parts[0]}.{parts[1]}.***.***.***"
            elif key == "create_date" and value:
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
        
        last_region = instance.region
        last_zone = instance.zone
    
    console.print(table)
    
    # 정부 클라우드 보안 정보 표시
    if mask_sensitive:
        console.print("\n[dim]보안: IP 주소가 마스킹되었습니다 (정부 클라우드 규정 준수)[/dim]")


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


@progress_bar("Initializing NCP Gov EC2 service")
def main(args):
    """
    NCP Gov EC2 정보 수집 메인 함수 (보안 강화)
    
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
        
        # 인스턴스 정보 수집
        instances = fetch_ncpgov_ec2_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(instances)} instances.")
        print_ncpgov_ec2_table(instances, args.verbose, args.mask_sensitive)
        
        # 감사 로그 기록
        log_audit_event('ec2_info_display_completed', {
            'instance_count': len(instances),
            'verbose_mode': args.verbose,
            'sensitive_masked': args.mask_sensitive
        })
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP Gov EC2 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP Gov EC2 Instance Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)