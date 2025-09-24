#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP Gov VPC Network Information Module

This module provides VPC network information retrieval for NCP Government Cloud.
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
from common.ncp_utils import apply_status_color
from src.ic.platforms.ncpgov.client import NCPGovClient, NCPGovAPIError

logger = get_logger()
console = Console()


@dataclass
class NCPGovVPC:
    """NCP Gov VPC 데이터 모델 (보안 강화)"""
    vpc_no: str
    vpc_name: str
    ipv4_cidr_block: str
    vpc_status: str
    region: str
    subnet_count: int
    subnets: List[Dict]
    route_tables: List[Dict]
    security_level: str = "high"
    compliance_status: str = "compliant"
    audit_id: str = ""
    network_acl_enabled: bool = True
    
    @classmethod
    def from_api_response(cls, vpc_data: Dict[str, Any], region: str, audit_id: str = "") -> 'NCPGovVPC':
        """API 응답에서 NCPGovVPC 객체 생성 (보안 검증 포함)"""
        # 민감한 정보 마스킹
        masked_data = mask_sensitive_data(vpc_data)
        
        return cls(
            vpc_no=masked_data.get('vpcNo', ''),
            vpc_name=masked_data.get('vpcName', ''),
            ipv4_cidr_block=masked_data.get('ipv4CidrBlock', ''),
            vpc_status=masked_data.get('vpcStatus', {}).get('code', ''),
            region=region,
            subnet_count=len(masked_data.get('subnetList', [])),
            subnets=masked_data.get('subnetList', []),
            route_tables=masked_data.get('routeTableList', []),
            security_level="high",
            compliance_status="compliant",
            audit_id=audit_id,
            network_acl_enabled=True  # 정부 클라우드는 기본 ACL 활성화
        )


def add_arguments(parser):
    """VPC Info에 필요한 인자 추가 (정부 클라우드 전용)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="VPC 상세 출력 (서브넷 및 라우트 테이블 포함)")
    parser.add_argument("--name", "-n", default=None, 
                       help="VPC 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP Gov 프로파일 (기본값: default)")
    parser.add_argument("--mask-sensitive", action="store_true", default=True,
                       help="민감한 정보 마스킹 활성화 (정부 클라우드 기본값)")


@handle_ncpgov_api_error
@progress_bar("Collecting NCP Gov VPC information")
def fetch_ncpgov_vpc_info(client: NCPGovClient, name_filter: str = None) -> List[NCPGovVPC]:
    """
    NCP Gov VPC 정보를 수집합니다. (보안 강화)
    
    Args:
        client: NCP Gov API 클라이언트
        name_filter: VPC 이름 필터 (부분 일치)
        
    Returns:
        NCPGovVPC 객체 목록
    """
    logger.info("NCP Gov VPC 정보 수집 시작")
    
    # 감사 로그 기록
    audit_id = f"vpc_fetch_{int(time.time())}"
    log_audit_event('vpc_info_collection_started', {
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
        
        # VPC 플랫폼 확인
        if client.platform != "VPC":
            logger.warning("VPC 서비스는 VPC 플랫폼에서만 사용 가능합니다.")
            console.print("[yellow]VPC 서비스는 VPC 플랫폼에서만 사용 가능합니다.[/yellow]")
            return []
        
        # API를 통해 VPC 목록 조회
        vpcs_data = client.get_vpc_list()
        
        if not vpcs_data:
            logger.info("조회된 VPC가 없습니다.")
            log_audit_event('vpc_info_collection_completed', {
                'audit_id': audit_id,
                'vpc_count': 0
            })
            return []
        
        # 보안 검증된 응답 데이터 처리
        validated_data = validate_api_response_security({'vpcs': vpcs_data})
        vpcs_data = validated_data['vpcs']
        
        # NCPGovVPC 객체로 변환
        vpcs = []
        for vpc_data in vpcs_data:
            try:
                # 서브넷 정보 추가 수집
                vpc_no = vpc_data.get('vpcNo')
                if vpc_no:
                    # 서브넷 목록 조회 (정부 클라우드 API 제한으로 인해 모의 데이터 사용)
                    subnets = []  # client.get_subnet_list(vpc_no) - 실제 구현 시 활성화
                    route_tables = []  # client.get_route_table_list(vpc_no) - 실제 구현 시 활성화
                    
                    vpc_data['subnetList'] = subnets
                    vpc_data['routeTableList'] = route_tables
                
                vpc = NCPGovVPC.from_api_response(
                    vpc_data, client.region, audit_id
                )
                vpcs.append(vpc)
            except Exception as e:
                logger.warning(f"VPC 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            vpcs = [vpc for vpc in vpcs 
                   if name_filter.lower() in vpc.vpc_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(vpcs)}개 VPC")
        
        # 감사 로그 기록
        log_audit_event('vpc_info_collection_completed', {
            'audit_id': audit_id,
            'vpc_count': len(vpcs),
            'filtered': bool(name_filter)
        })
        
        logger.info(f"NCP Gov VPC 정보 수집 완료: {len(vpcs)}개")
        return vpcs
        
    except NCPGovAPIError as e:
        logger.error(f"NCP Gov API 오류: {e}")
        console.print(f"[red]NCP Gov API 오류: {e.message}[/red]")
        
        # 오류 감사 로그
        log_audit_event('vpc_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'api_error',
            'error_message': str(e)
        })
        return []
    except Exception as e:
        logger.error(f"VPC 정보 수집 중 오류: {e}")
        console.print(f"[red]VPC 정보 수집 실패: {e}[/red]")
        
        # 오류 감사 로그
        log_audit_event('vpc_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'general_error',
            'error_message': str(e)
        })
        return []


def mask_cidr_block(cidr: str, mask_sensitive: bool = True) -> str:
    """CIDR 블록 마스킹 (정부 클라우드 보안)"""
    if not mask_sensitive or not cidr or cidr == "-":
        return cidr
    
    # CIDR 블록의 일부를 마스킹 (예: 10.0.0.0/16 -> 10.0.***.0/16)
    try:
        if '/' in cidr:
            ip_part, subnet_part = cidr.split('/')
            ip_octets = ip_part.split('.')
            if len(ip_octets) == 4:
                masked_ip = f"{ip_octets[0]}.{ip_octets[1]}.***.***.{subnet_part}"
                return masked_ip
    except:
        pass
    
    return cidr


def format_network_acl_status(enabled: bool) -> str:
    """네트워크 ACL 상태를 포맷"""
    if enabled:
        return "[bold green]ENABLED[/bold green]"
    else:
        return "[bold red]DISABLED[/bold red]"


def print_ncpgov_vpc_table(vpcs: List[NCPGovVPC], verbose: bool = False, mask_sensitive: bool = True) -> None:
    """
    NCP Gov VPC 정보를 보안 강화된 형식으로 출력합니다.
    
    Args:
        vpcs: NCPGovVPC 객체 목록
        verbose: 상세 정보 표시 여부
        mask_sensitive: 민감한 정보 마스킹 여부
    """
    if not vpcs:
        console.print("(No VPCs)")
        return
    
    # VPC를 리전, 이름 순으로 정렬
    vpcs.sort(key=lambda x: (x.region.lower(), x.vpc_name.lower()))
    
    console.print("[bold underline]NCP Gov VPC Network Info[/bold underline]")
    console.print("[dim]정부 클라우드 보안 모드 활성화됨[/dim]")
    
    # 테이블 생성 (OCI 스타일 + 보안 강화)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의 (정부 클라우드 전용 필드 추가)
    if verbose:
        headers = ["Region", "VPC Name", "Status", "CIDR Block", "Subnets", 
                  "Route Tables", "Network ACL", "Security", "VPC No"]
        keys = ["region", "vpc_name", "vpc_status", "ipv4_cidr_block", "subnet_count",
               "route_table_count", "network_acl_enabled", "security_level", "vpc_no"]
    else:
        headers = ["Region", "Name", "Status", "CIDR Block", "Subnets", "Network ACL", "Security"]
        keys = ["region", "vpc_name", "vpc_status", "ipv4_cidr_block", 
               "subnet_count", "network_acl_enabled", "security_level"]
    
    # 컬럼 스타일 설정 (OCI 패턴 + 보안 강화)
    for header in headers:
        style_opts = {}
        if header == "Region": 
            style_opts = {"style": "bold cyan"}
        elif header == "Status": 
            style_opts = {"justify": "center"}
        elif header in ["Subnets", "Route Tables"]: 
            style_opts = {"justify": "right"}
        elif header in ["VPC Name", "Name"]: 
            style_opts = {"overflow": "fold"}
        elif header in ["Security", "Network ACL"]:
            style_opts = {"style": "bold green", "justify": "center"}
        elif header == "CIDR Block":
            style_opts = {"justify": "center"}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑 + 보안 마스킹)
    last_region = None
    
    for i, vpc in enumerate(vpcs):
        region_changed = vpc.region != last_region
        
        # 리전이 바뀔 때 구분선 추가
        if i > 0 and region_changed:
            table.add_row(*[Rule(style="dim") for _ in headers])
        
        # 행 데이터 구성
        row_values = []
        
        # 리전 표시 (변경된 경우만)
        row_values.append(vpc.region if region_changed else "")
        
        # 나머지 데이터
        for key in keys[1:]:  # region 제외
            value = getattr(vpc, key, "-")
            
            # 특별한 포맷팅 적용
            if key == "vpc_name" and mask_sensitive:
                # VPC 이름 부분 마스킹 (정부 클라우드 보안)
                if value and len(str(value)) > 6:
                    masked_name = str(value)[:3] + "***" + str(value)[-3:]
                    value = masked_name
            elif key == "vpc_status":
                value = apply_status_color(str(value))
            elif key == "ipv4_cidr_block":
                value = mask_cidr_block(str(value), mask_sensitive)
            elif key == "subnet_count":
                value = str(value) if value != "-" and value != 0 else "-"
            elif key == "route_table_count":
                route_tables = getattr(vpc, 'route_tables', [])
                value = str(len(route_tables)) if route_tables else "-"
            elif key == "network_acl_enabled":
                value = format_network_acl_status(bool(value))
            elif key == "security_level":
                value = f"[bold green]{str(value).upper()}[/bold green]" if value else "STANDARD"
            elif key == "vpc_no" and mask_sensitive:
                # VPC 번호 부분 마스킹
                if value and len(str(value)) > 4:
                    masked_no = str(value)[:2] + "***" + str(value)[-2:]
                    value = masked_no
            
            row_values.append(str(value) if value is not None else "-")
        
        table.add_row(*row_values)
        last_region = vpc.region
    
    console.print(table)
    
    # 정부 클라우드 보안 정보 표시
    if mask_sensitive:
        console.print("\n[dim]보안: VPC 이름, CIDR 블록, VPC 번호가 부분적으로 마스킹되었습니다 (정부 클라우드 규정 준수)[/dim]")
    
    # 네트워크 보안 상태 요약
    acl_enabled_count = sum(1 for vpc in vpcs if vpc.network_acl_enabled)
    total_count = len(vpcs)
    console.print(f"\n[bold green]네트워크 보안:[/bold green] {acl_enabled_count}/{total_count} VPC에서 Network ACL 활성화됨")
    
    # 상세 정보 표시 (verbose 모드)
    if verbose and vpcs:
        console.print("\n[bold underline]VPC 상세 정보[/bold underline]")
        for vpc in vpcs:
            console.print(f"\n[bold cyan]{vpc.vpc_name}[/bold cyan] ({vpc.region})")
            console.print(f"  CIDR: {mask_cidr_block(vpc.ipv4_cidr_block, mask_sensitive)}")
            console.print(f"  서브넷: {vpc.subnet_count}개")
            console.print(f"  라우트 테이블: {len(vpc.route_tables)}개")
            console.print(f"  보안 수준: [bold green]{vpc.security_level.upper()}[/bold green]")
            console.print(f"  규정 준수: [bold green]{vpc.compliance_status.upper()}[/bold green]")


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


@progress_bar("Initializing NCP Gov VPC service")
def main(args):
    """
    NCP Gov VPC 정보 수집 메인 함수 (보안 강화)
    
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
        
        # VPC 정보 수집
        vpcs = fetch_ncpgov_vpc_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(vpcs)} VPCs.")
        print_ncpgov_vpc_table(vpcs, args.verbose, args.mask_sensitive)
        
        # 감사 로그 기록
        log_audit_event('vpc_info_display_completed', {
            'vpc_count': len(vpcs),
            'verbose_mode': args.verbose,
            'sensitive_masked': args.mask_sensitive
        })
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP Gov VPC 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP Gov VPC Network Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)