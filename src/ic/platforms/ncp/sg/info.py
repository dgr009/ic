#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP Security Group (Access Control Group) Information Module

This module provides security group information retrieval for NCP (Naver Cloud Platform).
It follows the same architectural patterns as the OCI and other NCP service modules for consistent user experience.

Features:
- HMAC-SHA256 signature authentication
- Support for both Classic and VPC platforms
- Security group rules display with inbound/outbound separation
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
class NCPSecurityGroupRule:
    """NCP 보안 그룹 규칙 데이터 모델"""
    protocol_type: str
    ip_block: str
    port_range: str
    access_control_group_sequence: str
    description: str
    
    @classmethod
    def from_api_response(cls, rule_data: Dict[str, Any]) -> 'NCPSecurityGroupRule':
        """API 응답에서 NCPSecurityGroupRule 객체 생성"""
        # 포트 범위 구성
        port_range = "-"
        if rule_data.get('portRange'):
            port_range = rule_data['portRange']
        elif rule_data.get('fromPort') and rule_data.get('toPort'):
            from_port = rule_data['fromPort']
            to_port = rule_data['toPort']
            if from_port == to_port:
                port_range = str(from_port)
            else:
                port_range = f"{from_port}-{to_port}"
        
        return cls(
            protocol_type=rule_data.get('protocolType', {}).get('code', ''),
            ip_block=rule_data.get('ipBlock', ''),
            port_range=port_range,
            access_control_group_sequence=rule_data.get('accessControlGroupSequence', ''),
            description=rule_data.get('accessControlGroupRuleDescription', '')
        )


@dataclass
class NCPSecurityGroup:
    """NCP 보안 그룹 데이터 모델"""
    access_control_group_no: str
    access_control_group_name: str
    access_control_group_description: str
    vpc_no: str
    vpc_name: str
    access_control_group_status: str
    platform_type: str
    region: str
    inbound_rules: List[NCPSecurityGroupRule]
    outbound_rules: List[NCPSecurityGroupRule]
    create_date: str
    
    @classmethod
    def from_api_response(cls, sg_data: Dict[str, Any], region: str) -> 'NCPSecurityGroup':
        """API 응답에서 NCPSecurityGroup 객체 생성"""
        # 인바운드/아웃바운드 규칙 분리
        inbound_rules = []
        outbound_rules = []
        
        # accessControlRuleList에서 규칙 추출
        rules_list = sg_data.get('accessControlRuleList', [])
        for rule_data in rules_list:
            rule = NCPSecurityGroupRule.from_api_response(rule_data)
            
            # 규칙 방향 결정 (NCP API 스펙에 따라)
            rule_type = rule_data.get('accessControlRuleType', {}).get('code', '')
            if rule_type == 'INBND':
                inbound_rules.append(rule)
            elif rule_type == 'OTBND':
                outbound_rules.append(rule)
            else:
                # 기본적으로 인바운드로 처리
                inbound_rules.append(rule)
        
        return cls(
            access_control_group_no=sg_data.get('accessControlGroupNo', ''),
            access_control_group_name=sg_data.get('accessControlGroupName', ''),
            access_control_group_description=sg_data.get('accessControlGroupDescription', ''),
            vpc_no=sg_data.get('vpcNo', ''),
            vpc_name=sg_data.get('vpcName', '-'),
            access_control_group_status=sg_data.get('accessControlGroupStatus', {}).get('code', ''),
            platform_type=sg_data.get('platformType', {}).get('code', ''),
            region=region,
            inbound_rules=inbound_rules,
            outbound_rules=outbound_rules,
            create_date=sg_data.get('createDate', '')
        )


def add_arguments(parser):
    """Security Group Info에 필요한 인자 추가 (OCI 패턴)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="보안 그룹 상세 출력 (규칙 포함)")
    parser.add_argument("--name", "-n", default=None, 
                       help="보안 그룹 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP 프로파일 (기본값: default)")


@handle_ncp_api_error
@progress_bar("Collecting NCP Security Groups")
def fetch_ncp_sg_info(client: NCPClient, name_filter: str = None) -> List[NCPSecurityGroup]:
    """
    NCP 보안 그룹 정보를 수집합니다.
    
    Args:
        client: NCP API 클라이언트
        name_filter: 보안 그룹 이름 필터 (부분 일치)
        
    Returns:
        NCPSecurityGroup 객체 목록
    """
    logger.info("NCP 보안 그룹 정보 수집 시작")
    
    try:
        # API를 통해 보안 그룹 목록 조회
        security_groups_data = client.get_access_control_groups()
        
        if not security_groups_data:
            logger.info("조회된 보안 그룹이 없습니다.")
            return []
        
        # NCPSecurityGroup 객체로 변환
        security_groups = []
        for sg_data in security_groups_data:
            try:
                security_group = NCPSecurityGroup.from_api_response(sg_data, client.region)
                
                # 규칙이 포함되지 않은 경우 별도로 조회
                if not security_group.inbound_rules and not security_group.outbound_rules:
                    try:
                        rules_data = client.get_access_control_group_rules(security_group.access_control_group_no)
                        
                        # 규칙 데이터를 인바운드/아웃바운드로 분리
                        inbound_rules = []
                        outbound_rules = []
                        
                        for rule_data in rules_data:
                            rule = NCPSecurityGroupRule.from_api_response(rule_data)
                            rule_type = rule_data.get('accessControlRuleType', {}).get('code', '')
                            
                            if rule_type == 'INBND':
                                inbound_rules.append(rule)
                            elif rule_type == 'OTBND':
                                outbound_rules.append(rule)
                            else:
                                # 기본적으로 인바운드로 처리
                                inbound_rules.append(rule)
                        
                        # 규칙 업데이트
                        security_group.inbound_rules = inbound_rules
                        security_group.outbound_rules = outbound_rules
                        
                    except Exception as rule_error:
                        logger.warning(f"보안 그룹 {security_group.access_control_group_name} 규칙 조회 실패: {rule_error}")
                
                security_groups.append(security_group)
                
            except Exception as e:
                logger.warning(f"보안 그룹 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            security_groups = [sg for sg in security_groups 
                             if name_filter.lower() in sg.access_control_group_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(security_groups)}개 보안 그룹")
        
        logger.info(f"NCP 보안 그룹 정보 수집 완료: {len(security_groups)}개")
        return security_groups
        
    except NCPAPIError as e:
        logger.error(f"NCP API 오류: {e}")
        console.print(f"[red]NCP API 오류: {e.message}[/red]")
        return []
    except Exception as e:
        logger.error(f"보안 그룹 정보 수집 중 오류: {e}")
        console.print(f"[red]보안 그룹 정보 수집 실패: {e}[/red]")
        return []


def format_rule_description(description: str, max_length: int = 30) -> str:
    """규칙 설명을 적절한 길이로 포맷"""
    if not description or description.strip() == '':
        return "-"
    
    description = description.strip()
    if len(description) <= max_length:
        return description
    
    return description[:max_length-3] + "..."


def format_protocol_and_port(protocol: str, port_range: str) -> str:
    """프로토콜과 포트를 조합하여 표시"""
    if not protocol:
        protocol = "ALL"
    
    if not port_range or port_range == "-":
        if protocol.upper() in ["ICMP", "ALL"]:
            return protocol.upper()
        else:
            return f"{protocol.upper()}/ALL"
    
    return f"{protocol.upper()}/{port_range}"


def print_security_group_rules(rules: List[NCPSecurityGroupRule], rule_type: str) -> None:
    """
    보안 그룹 규칙을 테이블 형식으로 출력
    
    Args:
        rules: 보안 그룹 규칙 목록
        rule_type: 규칙 타입 ("Inbound" 또는 "Outbound")
    """
    if not rules:
        console.print(f"    [dim]{rule_type}: No rules[/dim]")
        return
    
    console.print(f"    [bold]{rule_type} Rules:[/bold]")
    
    # 규칙 테이블 생성
    rule_table = Table(show_lines=False, box=None, show_header=True, 
                      header_style="dim", expand=False, padding=(0, 1))
    
    rule_table.add_column("Protocol/Port", style="cyan")
    rule_table.add_column("Source/Destination", style="yellow")
    rule_table.add_column("Description", style="dim")
    
    for rule in rules:
        protocol_port = format_protocol_and_port(rule.protocol_type, rule.port_range)
        ip_block = rule.ip_block if rule.ip_block else "0.0.0.0/0"
        description = format_rule_description(rule.description)
        
        rule_table.add_row(protocol_port, ip_block, description)
    
    console.print(rule_table)


def print_ncp_sg_table(security_groups: List[NCPSecurityGroup], verbose: bool = False) -> None:
    """
    NCP 보안 그룹 정보를 OCI 스타일 형식으로 출력합니다.
    
    Args:
        security_groups: NCPSecurityGroup 객체 목록
        verbose: 상세 정보 표시 여부 (규칙 포함)
    """
    if not security_groups:
        console.print("(No Security Groups)")
        return
    
    # 보안 그룹을 리전, 플랫폼, 이름 순으로 정렬
    security_groups.sort(key=lambda x: (x.region.lower(), x.platform_type.lower(), x.access_control_group_name.lower()))
    
    console.print("[bold underline]NCP Security Group Info[/bold underline]")
    
    # 테이블 생성 (OCI 스타일)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의
    if verbose:
        headers = ["Region", "Platform", "Name", "Status", "VPC", "Rules", "Description", "Created"]
        keys = ["region", "platform_type", "access_control_group_name", "access_control_group_status",
               "vpc_name", "rules_count", "access_control_group_description", "create_date"]
    else:
        headers = ["Region", "Platform", "Name", "Status", "VPC", "In/Out Rules", "Description"]
        keys = ["region", "platform_type", "access_control_group_name", "access_control_group_status",
               "vpc_name", "rules_count", "access_control_group_description"]
    
    # 컬럼 스타일 설정 (OCI 패턴)
    for header in headers:
        style_opts = {}
        if header in ["Region", "Platform"]: 
            style_opts = {"style": "bold cyan"}
        elif header == "Status": 
            style_opts = {"justify": "center"}
        elif header in ["Rules", "In/Out Rules"]: 
            style_opts = {"justify": "center"}
        elif header in ["Name"]: 
            style_opts = {"overflow": "fold"}
        elif header == "Description":
            style_opts = {"overflow": "fold", "max_width": 40}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑)
    last_region = None
    last_platform = None
    
    for i, sg in enumerate(security_groups):
        region_changed = sg.region != last_region
        platform_changed = sg.platform_type != last_platform
        
        # 리전이 바뀔 때 구분선 추가
        if i > 0 and region_changed:
            table.add_row(*[Rule(style="dim") for _ in headers])
        # 같은 리전 내에서 플랫폼이 바뀔 때 작은 구분선 추가
        elif i > 0 and platform_changed:
            table.add_row("", *[Rule(style="dim") for _ in headers[1:]])
        
        # 행 데이터 구성
        row_values = []
        
        # 리전 표시 (변경된 경우만)
        row_values.append(sg.region if region_changed else "")
        
        # 플랫폼 표시 (변경된 경우만)
        row_values.append(sg.platform_type if region_changed or platform_changed else "")
        
        # 나머지 데이터
        for key in keys[2:]:  # region, platform_type 제외
            if key == "rules_count":
                # 인바운드/아웃바운드 규칙 수 표시
                inbound_count = len(sg.inbound_rules)
                outbound_count = len(sg.outbound_rules)
                value = f"{inbound_count}/{outbound_count}"
            elif key == "access_control_group_status":
                value = apply_status_color(str(getattr(sg, key, "-")))
            elif key == "create_date":
                value = getattr(sg, key, "-")
                # 날짜 포맷팅 (YYYY-MM-DD HH:MM:SS -> YYYY-MM-DD)
                try:
                    if value and 'T' in str(value):
                        value = str(value).split('T')[0]
                    elif value and ' ' in str(value):
                        value = str(value).split(' ')[0]
                except:
                    pass
            elif key == "access_control_group_description":
                value = getattr(sg, key, "-")
                if value and len(value) > 40:
                    value = value[:37] + "..."
            else:
                value = getattr(sg, key, "-")
            
            row_values.append(str(value) if value is not None else "-")
        
        table.add_row(*row_values)
        
        # Verbose 모드에서 규칙 상세 정보 출력
        if verbose and (sg.inbound_rules or sg.outbound_rules):
            console.print(table)  # 현재까지의 테이블 출력
            console.print(f"\n[bold]Security Group: {sg.access_control_group_name}[/bold]")
            
            if sg.inbound_rules:
                print_security_group_rules(sg.inbound_rules, "Inbound")
            
            if sg.outbound_rules:
                print_security_group_rules(sg.outbound_rules, "Outbound")
            
            console.print()  # 빈 줄 추가
            
            # 새 테이블 시작 (다음 보안 그룹을 위해)
            table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                         header_style="bold", expand=False)
            table.show_edge = False
            
            for header in headers:
                style_opts = {}
                if header in ["Region", "Platform"]: 
                    style_opts = {"style": "bold cyan"}
                elif header == "Status": 
                    style_opts = {"justify": "center"}
                elif header in ["Rules", "In/Out Rules"]: 
                    style_opts = {"justify": "center"}
                elif header in ["Name"]: 
                    style_opts = {"overflow": "fold"}
                elif header == "Description":
                    style_opts = {"overflow": "fold", "max_width": 40}
                
                table.add_column(header, **style_opts)
        
        last_region = sg.region
        last_platform = sg.platform_type
    
    # Verbose가 아닌 경우에만 최종 테이블 출력
    if not verbose:
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


@progress_bar("Initializing NCP Security Group service")
def main(args):
    """
    NCP 보안 그룹 정보 수집 메인 함수
    
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
        if not validate_platform_support(client.platform, 'sg'):
            console.print(f"[yellow]Security Group 서비스는 {client.platform} 플랫폼에서 지원됩니다.[/yellow]")
        
        # 보안 그룹 정보 수집
        security_groups = fetch_ncp_sg_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(security_groups)} security groups.")
        print_ncp_sg_table(security_groups, args.verbose)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP 보안 그룹 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP Security Group Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)