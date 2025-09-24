#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP EC2 Instance Information Module

This module provides EC2 instance information retrieval for NCP (Naver Cloud Platform).
It follows the same architectural patterns as the OCI VM info module for consistent user experience.

Features:
- HMAC-SHA256 signature authentication
- Support for both Classic and VPC platforms
- OCI-style table formatting
- Progress indicators for long operations
- Error handling and validation
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
class NCPInstance:
    """NCP 인스턴스 데이터 모델"""
    server_instance_no: str
    server_name: str
    server_instance_status: str
    server_instance_type: str
    cpu_count: int
    memory_size: int
    platform_type: str
    public_ip: str
    private_ip: str
    vpc_name: str
    subnet_name: str
    region: str
    zone: str
    create_date: str
    
    @classmethod
    def from_api_response(cls, instance_data: Dict[str, Any], region: str) -> 'NCPInstance':
        """API 응답에서 NCPInstance 객체 생성"""
        return cls(
            server_instance_no=instance_data.get('serverInstanceNo', ''),
            server_name=instance_data.get('serverName', ''),
            server_instance_status=instance_data.get('serverInstanceStatus', {}).get('code', ''),
            server_instance_type=instance_data.get('serverInstanceType', {}).get('code', ''),
            cpu_count=instance_data.get('cpuCount', 0),
            memory_size=instance_data.get('memorySize', 0),
            platform_type=instance_data.get('platformType', {}).get('code', ''),
            public_ip=instance_data.get('publicIp', '-'),
            private_ip=instance_data.get('privateIp', '-'),
            vpc_name=instance_data.get('vpcName', '-'),
            subnet_name=instance_data.get('subnetName', '-'),
            region=region,
            zone=instance_data.get('zone', {}).get('zoneName', ''),
            create_date=instance_data.get('createDate', '')
        )

def add_arguments(parser):
    """EC2 Info에 필요한 인자 추가 (OCI VM info와 동일한 패턴)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="인스턴스 상세 출력 (전체 컬럼 표시)")
    parser.add_argument("--name", "-n", default=None, 
                       help="인스턴스 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP 프로파일 (기본값: default)")


@handle_ncp_api_error
@progress_bar("Collecting NCP EC2 instances")
def fetch_ncp_ec2_info(client: NCPClient, name_filter: str = None) -> List[NCPInstance]:
    """
    NCP EC2 인스턴스 정보를 수집합니다.
    
    Args:
        client: NCP API 클라이언트
        name_filter: 인스턴스 이름 필터 (부분 일치)
        
    Returns:
        NCPInstance 객체 목록
    """
    logger.info("NCP EC2 인스턴스 정보 수집 시작")
    
    try:
        # API를 통해 서버 인스턴스 목록 조회
        instances_data = client.get_server_instances()
        
        if not instances_data:
            logger.info("조회된 인스턴스가 없습니다.")
            return []
        
        # NCPInstance 객체로 변환
        instances = []
        for instance_data in instances_data:
            try:
                instance = NCPInstance.from_api_response(instance_data, client.region)
                instances.append(instance)
            except Exception as e:
                logger.warning(f"인스턴스 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            instances = [inst for inst in instances 
                        if name_filter.lower() in inst.server_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(instances)}개 인스턴스")
        
        logger.info(f"NCP EC2 인스턴스 정보 수집 완료: {len(instances)}개")
        return instances
        
    except NCPAPIError as e:
        logger.error(f"NCP API 오류: {e}")
        console.print(f"[red]NCP API 오류: {e.message}[/red]")
        return []
    except Exception as e:
        logger.error(f"인스턴스 정보 수집 중 오류: {e}")
        console.print(f"[red]인스턴스 정보 수집 실패: {e}[/red]")
        return []


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


def format_instance_type(instance_type: str) -> str:
    """인스턴스 타입을 읽기 쉽게 포맷"""
    if not instance_type or instance_type == '-':
        return "-"
    
    # NCP 인스턴스 타입 포맷팅 (예: SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002)
    # 간단한 표시를 위해 주요 정보만 추출
    parts = instance_type.split('.')
    if len(parts) >= 4:
        cpu_part = next((p for p in parts if p.startswith('C')), '')
        mem_part = next((p for p in parts if p.startswith('M')), '')
        if cpu_part and mem_part:
            cpu_count = cpu_part[1:] if len(cpu_part) > 1 else ''
            mem_size = mem_part[1:] if len(mem_part) > 1 else ''
            return f"C{cpu_count}M{mem_size}"
    
    return instance_type


def print_ncp_ec2_table(instances: List[NCPInstance], verbose: bool = False) -> None:
    """
    NCP EC2 인스턴스 정보를 OCI VM info와 유사한 형식으로 출력합니다.
    
    Args:
        instances: NCPInstance 객체 목록
        verbose: 상세 정보 표시 여부
    """
    if not instances:
        console.print("(No Instances)")
        return
    
    # 인스턴스를 리전, 존, 이름 순으로 정렬
    instances.sort(key=lambda x: (x.region.lower(), x.zone.lower(), x.server_name.lower()))
    
    console.print("[bold underline]NCP EC2 Instance Info[/bold underline]")
    
    # 테이블 생성 (OCI 스타일)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의
    if verbose:
        headers = ["Region", "Zone", "Instance Name", "Status", "Type", "CPU", "Memory", 
                  "Platform", "Private IP", "Public IP", "VPC", "Subnet", "Created"]
        keys = ["region", "zone", "server_name", "server_instance_status", "server_instance_type",
               "cpu_count", "memory_size", "platform_type", "private_ip", "public_ip", 
               "vpc_name", "subnet_name", "create_date"]
    else:
        headers = ["Region", "Zone", "Name", "Status", "Type", "CPU", "Memory", "Private IP", "Public IP"]
        keys = ["region", "zone", "server_name", "server_instance_status", "server_instance_type",
               "cpu_count", "memory_size", "private_ip", "public_ip"]
    
    # 컬럼 스타일 설정 (OCI 패턴)
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
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑)
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
        
        last_region = instance.region
        last_zone = instance.zone
    
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


@progress_bar("Initializing NCP EC2 service")
def main(args):
    """
    NCP EC2 정보 수집 메인 함수
    
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
        if not validate_platform_support(client.platform, 'ec2'):
            console.print(f"[yellow]EC2 서비스는 {client.platform} 플랫폼에서 지원됩니다.[/yellow]")
        
        # 인스턴스 정보 수집
        instances = fetch_ncp_ec2_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(instances)} instances.")
        print_ncp_ec2_table(instances, args.verbose)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP EC2 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="NCP EC2 Instance Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)