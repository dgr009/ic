#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP VPC Information Module

This module provides VPC and subnet information retrieval for NCP (Naver Cloud Platform).
It follows the same architectural patterns as the OCI VCN info module for consistent user experience.

Features:
- VPC and subnet information display similar to OCI VCN info
- VPC resource counting functionality (connected resources)
- VPC-specific error handling and validation
- Classic platform handling (VPC not available message)
- Route table information display
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
class NCPSubnet:
    """NCP 서브넷 데이터 모델"""
    subnet_no: str
    subnet_name: str
    subnet: str  # CIDR
    zone: str
    subnet_type: str
    usage_type: str
    subnet_status: str
    
    @classmethod
    def from_api_response(cls, subnet_data: Dict[str, Any]) -> 'NCPSubnet':
        """API 응답에서 NCPSubnet 객체 생성"""
        return cls(
            subnet_no=subnet_data.get('subnetNo', ''),
            subnet_name=subnet_data.get('subnetName', ''),
            subnet=subnet_data.get('subnet', ''),
            zone=subnet_data.get('zone', {}).get('zoneName', ''),
            subnet_type=subnet_data.get('subnetType', {}).get('code', ''),
            usage_type=subnet_data.get('usageType', {}).get('code', ''),
            subnet_status=subnet_data.get('subnetStatus', {}).get('code', '')
        )


@dataclass
class NCPRouteTable:
    """NCP 라우트 테이블 데이터 모델"""
    route_table_no: str
    route_table_name: str
    supported_subnet_type: str
    is_default: bool
    route_table_status: str
    
    @classmethod
    def from_api_response(cls, route_data: Dict[str, Any]) -> 'NCPRouteTable':
        """API 응답에서 NCPRouteTable 객체 생성"""
        return cls(
            route_table_no=route_data.get('routeTableNo', ''),
            route_table_name=route_data.get('routeTableName', ''),
            supported_subnet_type=route_data.get('supportedSubnetType', {}).get('code', ''),
            is_default=route_data.get('isDefault', False),
            route_table_status=route_data.get('routeTableStatus', {}).get('code', '')
        )


@dataclass
class NCPVPC:
    """NCP VPC 데이터 모델"""
    vpc_no: str
    vpc_name: str
    ipv4_cidr_block: str
    vpc_status: str
    region: str
    subnets: List[NCPSubnet]
    route_tables: List[NCPRouteTable]
    subnet_count: int
    route_table_count: int
    
    @classmethod
    def from_api_response(cls, vpc_data: Dict[str, Any], region: str, 
                         subnets: List[NCPSubnet] = None, 
                         route_tables: List[NCPRouteTable] = None) -> 'NCPVPC':
        """API 응답에서 NCPVPC 객체 생성"""
        subnets = subnets or []
        route_tables = route_tables or []
        
        return cls(
            vpc_no=vpc_data.get('vpcNo', ''),
            vpc_name=vpc_data.get('vpcName', ''),
            ipv4_cidr_block=vpc_data.get('ipv4CidrBlock', ''),
            vpc_status=vpc_data.get('vpcStatus', {}).get('code', ''),
            region=region,
            subnets=subnets,
            route_tables=route_tables,
            subnet_count=len(subnets),
            route_table_count=len(route_tables)
        )


def add_arguments(parser):
    """VPC Info에 필요한 인자 추가 (OCI VCN info와 동일한 패턴)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="VPC 상세 출력 (서브넷 및 라우트 테이블 포함)")
    parser.add_argument("--name", "-n", default=None, 
                       help="VPC 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP 프로파일 (기본값: default)")


@handle_ncp_api_error
def fetch_vpc_subnets(client: NCPClient, vpc_no: str) -> List[NCPSubnet]:
    """
    특정 VPC의 서브넷 목록을 조회합니다.
    
    Args:
        client: NCP API 클라이언트
        vpc_no: VPC 번호
        
    Returns:
        NCPSubnet 객체 목록
    """
    try:
        # VPC 서브넷 목록 조회 API 호출
        subnets_data = client.get_subnet_list(vpc_no=vpc_no)
        subnets = []
        
        for subnet_data in subnets_data:
            try:
                subnet = NCPSubnet.from_api_response(subnet_data)
                subnets.append(subnet)
            except Exception as e:
                logger.warning(f"서브넷 데이터 파싱 실패: {e}")
                continue
        
        logger.debug(f"VPC {vpc_no}의 서브넷 {len(subnets)}개 조회 완료")
        return subnets
        
    except NCPAPIError as e:
        logger.error(f"서브넷 조회 실패: {e}")
        return []
    except Exception as e:
        logger.error(f"서브넷 조회 중 오류: {e}")
        return []


@handle_ncp_api_error
def fetch_vpc_route_tables(client: NCPClient, vpc_no: str) -> List[NCPRouteTable]:
    """
    특정 VPC의 라우트 테이블 목록을 조회합니다.
    
    Args:
        client: NCP API 클라이언트
        vpc_no: VPC 번호
        
    Returns:
        NCPRouteTable 객체 목록
    """
    try:
        # VPC 라우트 테이블 목록 조회 API 호출
        route_tables_data = client.get_route_table_list(vpc_no=vpc_no)
        route_tables = []
        
        for route_data in route_tables_data:
            try:
                route_table = NCPRouteTable.from_api_response(route_data)
                route_tables.append(route_table)
            except Exception as e:
                logger.warning(f"라우트 테이블 데이터 파싱 실패: {e}")
                continue
        
        logger.debug(f"VPC {vpc_no}의 라우트 테이블 {len(route_tables)}개 조회 완료")
        return route_tables
        
    except NCPAPIError as e:
        logger.error(f"라우트 테이블 조회 실패: {e}")
        return []
    except Exception as e:
        logger.error(f"라우트 테이블 조회 중 오류: {e}")
        return []


@handle_ncp_api_error
def count_vpc_resources(vpc_no: str, client: NCPClient) -> Dict[str, int]:
    """
    VPC에 연결된 리소스 수를 계산합니다.
    
    Args:
        vpc_no: VPC 번호
        client: NCP API 클라이언트
        
    Returns:
        리소스 수 딕셔너리
    """
    resource_counts = {
        'instances': 0,
        'load_balancers': 0,
        'nat_gateways': 0,
        'network_interfaces': 0
    }
    
    try:
        # 서버 인스턴스 수 계산
        instances = client.get_server_instances()
        vpc_instances = [inst for inst in instances 
                        if inst.get('vpcNo') == vpc_no]
        resource_counts['instances'] = len(vpc_instances)
        
        # 다른 리소스들은 별도 API 호출이 필요하므로 현재는 0으로 설정
        # 실제 구현 시 각 서비스별 API를 호출하여 계산
        
        logger.debug(f"VPC {vpc_no} 리소스 수 계산 완료: {resource_counts}")
        return resource_counts
        
    except Exception as e:
        logger.warning(f"VPC 리소스 수 계산 실패: {e}")
        return resource_counts


@handle_ncp_api_error
@progress_bar("Collecting NCP VPC information")
def fetch_ncp_vpc_info(client: NCPClient, name_filter: str = None) -> List[NCPVPC]:
    """
    NCP VPC 정보를 수집합니다.
    
    Args:
        client: NCP API 클라이언트
        name_filter: VPC 이름 필터 (부분 일치)
        
    Returns:
        NCPVPC 객체 목록
    """
    logger.info("NCP VPC 정보 수집 시작")
    
    # Classic 플랫폼 확인
    if client.platform == "CLASSIC":
        console.print("[yellow]VPC 서비스는 VPC 플랫폼에서만 사용 가능합니다.[/yellow]")
        console.print("[yellow]현재 설정: Classic 플랫폼[/yellow]")
        console.print("[cyan]VPC 플랫폼을 사용하려면 설정 파일에서 platform을 'VPC'로 변경하세요.[/cyan]")
        return []
    
    try:
        # API를 통해 VPC 목록 조회
        vpcs_data = client.get_vpc_list()
        
        if not vpcs_data:
            logger.info("조회된 VPC가 없습니다.")
            return []
        
        # NCPVPC 객체로 변환
        vpcs = []
        for vpc_data in vpcs_data:
            try:
                vpc_no = vpc_data.get('vpcNo', '')
                
                # 서브넷 정보 조회
                subnets = fetch_vpc_subnets(client, vpc_no)
                
                # 라우트 테이블 정보 조회
                route_tables = fetch_vpc_route_tables(client, vpc_no)
                
                # VPC 객체 생성
                vpc = NCPVPC.from_api_response(vpc_data, client.region, subnets, route_tables)
                vpcs.append(vpc)
                
            except Exception as e:
                logger.warning(f"VPC 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            vpcs = [vpc for vpc in vpcs 
                   if name_filter.lower() in vpc.vpc_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(vpcs)}개 VPC")
        
        logger.info(f"NCP VPC 정보 수집 완료: {len(vpcs)}개")
        return vpcs
        
    except NCPAPIError as e:
        logger.error(f"NCP API 오류: {e}")
        console.print(f"[red]NCP API 오류: {e.message}[/red]")
        return []
    except Exception as e:
        logger.error(f"VPC 정보 수집 중 오류: {e}")
        console.print(f"[red]VPC 정보 수집 실패: {e}[/red]")
        return []


def print_ncp_vpc_table(vpcs: List[NCPVPC], verbose: bool = False) -> None:
    """
    NCP VPC 정보를 OCI VCN info와 유사한 형식으로 출력합니다.
    
    Args:
        vpcs: NCPVPC 객체 목록
        verbose: 상세 정보 표시 여부 (서브넷 및 라우트 테이블 포함)
    """
    if not vpcs:
        console.print("(No VPCs)")
        return
    
    # VPC를 리전, 이름 순으로 정렬
    vpcs.sort(key=lambda x: (x.region.lower(), x.vpc_name.lower()))
    
    console.print("[bold underline]NCP VPC Information[/bold underline]")
    
    if not verbose:
        # 간단한 VPC 목록 표시
        table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                      header_style="bold", expand=False)
        table.show_edge = False
        
        # 컬럼 정의
        headers = ["Region", "VPC Name", "VPC CIDR", "Status", "Subnets", "Route Tables"]
        
        table.add_column("Region", style="bold cyan")
        table.add_column("VPC Name", style="bold green", overflow="fold")
        table.add_column("VPC CIDR", style="green")
        table.add_column("Status", justify="center")
        table.add_column("Subnets", justify="right")
        table.add_column("Route Tables", justify="right")
        
        # 데이터 행 추가
        last_region = None
        for i, vpc in enumerate(vpcs):
            region_changed = vpc.region != last_region
            
            if i > 0 and region_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            
            # 행 데이터 구성
            region_display = vpc.region if region_changed else ""
            status_display = apply_status_color(vpc.vpc_status)
            
            table.add_row(
                region_display,
                vpc.vpc_name,
                vpc.ipv4_cidr_block,
                status_display,
                str(vpc.subnet_count),
                str(vpc.route_table_count)
            )
            
            last_region = vpc.region
        
        console.print(table)
    
    else:
        # 상세한 VPC 정보 표시 (OCI VCN 스타일)
        table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                      header_style="bold", expand=False)
        table.show_edge = False
        
        # 컬럼 정의 (OCI VCN 스타일)
        headers = ["Region", "VPC Name", "VPC CIDR", "Subnet Name", "Subnet CIDR", "Zone", "Route Table"]
        
        table.add_column("Region", style="bold cyan")
        table.add_column("VPC Name", style="bold green")
        table.add_column("VPC CIDR", style="green")
        table.add_column("Subnet Name", style="cyan")
        table.add_column("Subnet CIDR", style="cyan")
        table.add_column("Zone", style="blue")
        table.add_column("Route Table", style="white")
        
        # 데이터 행 추가 (계층적 표시)
        last_region = None
        last_vpc = None
        
        for vpc in vpcs:
            region_changed = vpc.region != last_region
            vpc_changed = vpc.vpc_name != last_vpc
            
            # 리전이 바뀔 때 구분선 추가
            if last_region is not None and region_changed:
                table.add_row(*[Rule(style="dim") for _ in headers])
            
            # VPC가 바뀔 때 작은 구분선 추가
            elif last_vpc is not None and vpc_changed and not region_changed:
                table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
            
            if not vpc.subnets:
                # 서브넷이 없는 경우
                region_display = vpc.region if region_changed else ""
                vpc_display = vpc.vpc_name if vpc_changed else ""
                vpc_cidr_display = vpc.ipv4_cidr_block if vpc_changed else ""
                
                table.add_row(
                    region_display,
                    vpc_display,
                    vpc_cidr_display,
                    "No Subnets",
                    "-",
                    "-",
                    "-"
                )
            else:
                # 서브넷별로 행 추가
                for i, subnet in enumerate(vpc.subnets):
                    is_first_subnet = i == 0
                    
                    region_display = vpc.region if region_changed and is_first_subnet else ""
                    vpc_display = vpc.vpc_name if vpc_changed and is_first_subnet else ""
                    vpc_cidr_display = vpc.ipv4_cidr_block if vpc_changed and is_first_subnet else ""
                    
                    # 라우트 테이블 정보 (간단히 개수만 표시)
                    route_info = f"{vpc.route_table_count} tables" if is_first_subnet else ""
                    
                    table.add_row(
                        region_display,
                        vpc_display,
                        vpc_cidr_display,
                        subnet.subnet_name,
                        subnet.subnet,
                        subnet.zone,
                        route_info
                    )
            
            last_region = vpc.region
            last_vpc = vpc.vpc_name
        
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


@progress_bar("Initializing NCP VPC service")
def main(args):
    """
    NCP VPC 정보 수집 메인 함수
    
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
        if not validate_platform_support(client.platform, 'vpc'):
            # VPC는 VPC 플랫폼 전용이므로 여기서 처리됨
            pass
        
        # VPC 정보 수집
        vpcs = fetch_ncp_vpc_info(client, args.name)
        
        # 결과 출력
        if vpcs:
            console.print(f"\n[bold green]Collection complete![/bold green] Found {len(vpcs)} VPCs.")
            print_ncp_vpc_table(vpcs, args.verbose)
        else:
            console.print("\n[yellow]No VPCs found or VPC service not available.[/yellow]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP VPC 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP VPC Information Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)