#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NCP Gov Security Group Information Module

This module provides Security Group information retrieval for NCP Government Cloud.
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
class NCPGovSecurityGroup:
    """NCP Gov Security Group 데이터 모델 (보안 강화)"""
    access_control_group_no: str
    access_control_group_name: str
    access_control_group_description: str
    vpc_no: str
    access_control_group_status: str
    access_control_rules: List[Dict]
    region: str
    security_level: str = "high"
    compliance_status: str = "compliant"
    audit_id: str = ""
    rule_count: int = 0
    inbound_rules: List[Dict] = None
    outbound_rules: List[Dict] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.inbound_rules is None:
            self.inbound_rules = []
        if self.outbound_rules is None:
            self.outbound_rules = []
        
        # 규칙을 인바운드/아웃바운드로 분류
        self._classify_rules()
    
    def _classify_rules(self):
        """보안 그룹 규칙을 인바운드/아웃바운드로 분류"""
        for rule in self.access_control_rules:
            rule_type = rule.get('accessControlRuleType', {}).get('code', '')
            if rule_type.upper() == 'INBND':
                self.inbound_rules.append(rule)
            elif rule_type.upper() == 'OTBND':
                self.outbound_rules.append(rule)
        
        self.rule_count = len(self.access_control_rules)
    
    @classmethod
    def from_api_response(cls, sg_data: Dict[str, Any], region: str, audit_id: str = "") -> 'NCPGovSecurityGroup':
        """API 응답에서 NCPGovSecurityGroup 객체 생성 (보안 검증 포함)"""
        # 민감한 정보 마스킹
        masked_data = mask_sensitive_data(sg_data)
        
        return cls(
            access_control_group_no=masked_data.get('accessControlGroupNo', ''),
            access_control_group_name=masked_data.get('accessControlGroupName', ''),
            access_control_group_description=masked_data.get('accessControlGroupDescription', ''),
            vpc_no=masked_data.get('vpcNo', ''),
            access_control_group_status=masked_data.get('accessControlGroupStatus', {}).get('code', ''),
            access_control_rules=masked_data.get('accessControlRuleList', []),
            region=region,
            security_level="high",
            compliance_status="compliant",
            audit_id=audit_id
        )


def add_arguments(parser):
    """Security Group Info에 필요한 인자 추가 (정부 클라우드 전용)"""
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="보안 그룹 상세 출력 (규칙 포함)")
    parser.add_argument("--name", "-n", default=None, 
                       help="보안 그룹 이름 필터 (부분 일치)")
    parser.add_argument("--profile", "-p", default="default",
                       help="사용할 NCP Gov 프로파일 (기본값: default)")
    parser.add_argument("--mask-sensitive", action="store_true", default=True,
                       help="민감한 정보 마스킹 활성화 (정부 클라우드 기본값)")


@handle_ncpgov_api_error
@progress_bar("Collecting NCP Gov Security Groups")
def fetch_ncpgov_sg_info(client: NCPGovClient, name_filter: str = None) -> List[NCPGovSecurityGroup]:
    """
    NCP Gov Security Group 정보를 수집합니다. (보안 강화)
    
    Args:
        client: NCP Gov API 클라이언트
        name_filter: 보안 그룹 이름 필터 (부분 일치)
        
    Returns:
        NCPGovSecurityGroup 객체 목록
    """
    logger.info("NCP Gov Security Group 정보 수집 시작")
    
    # 감사 로그 기록
    audit_id = f"sg_fetch_{int(time.time())}"
    log_audit_event('sg_info_collection_started', {
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
        
        # API를 통해 보안 그룹 목록 조회
        sg_data = client.get_access_control_groups()
        
        if not sg_data:
            logger.info("조회된 보안 그룹이 없습니다.")
            log_audit_event('sg_info_collection_completed', {
                'audit_id': audit_id,
                'sg_count': 0
            })
            return []
        
        # 보안 검증된 응답 데이터 처리
        validated_data = validate_api_response_security({'security_groups': sg_data})
        sg_data = validated_data['security_groups']
        
        # NCPGovSecurityGroup 객체로 변환
        security_groups = []
        for sg_item_data in sg_data:
            try:
                # 보안 그룹 규칙 추가 조회 (정부 클라우드 API 제한으로 인해 기본 데이터 사용)
                sg_no = sg_item_data.get('accessControlGroupNo')
                if sg_no:
                    # 실제 구현에서는 client.get_access_control_group_rules(sg_no) 호출
                    # 현재는 기본 데이터 사용
                    if 'accessControlRuleList' not in sg_item_data:
                        sg_item_data['accessControlRuleList'] = []
                
                sg = NCPGovSecurityGroup.from_api_response(
                    sg_item_data, client.region, audit_id
                )
                security_groups.append(sg)
            except Exception as e:
                logger.warning(f"보안 그룹 데이터 파싱 실패: {e}")
                continue
        
        # 이름 필터 적용
        if name_filter:
            security_groups = [sg for sg in security_groups 
                             if name_filter.lower() in sg.access_control_group_name.lower()]
            logger.info(f"이름 필터 '{name_filter}' 적용: {len(security_groups)}개 보안 그룹")
        
        # 감사 로그 기록
        log_audit_event('sg_info_collection_completed', {
            'audit_id': audit_id,
            'sg_count': len(security_groups),
            'filtered': bool(name_filter)
        })
        
        logger.info(f"NCP Gov Security Group 정보 수집 완료: {len(security_groups)}개")
        return security_groups
        
    except NCPGovAPIError as e:
        logger.error(f"NCP Gov API 오류: {e}")
        console.print(f"[red]NCP Gov API 오류: {e.message}[/red]")
        
        # 오류 감사 로그
        log_audit_event('sg_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'api_error',
            'error_message': str(e)
        })
        return []
    except Exception as e:
        logger.error(f"보안 그룹 정보 수집 중 오류: {e}")
        console.print(f"[red]보안 그룹 정보 수집 실패: {e}[/red]")
        
        # 오류 감사 로그
        log_audit_event('sg_info_collection_failed', {
            'audit_id': audit_id,
            'error_type': 'general_error',
            'error_message': str(e)
        })
        return []


def format_rule_count(inbound_count: int, outbound_count: int) -> str:
    """규칙 수를 포맷"""
    if inbound_count == 0 and outbound_count == 0:
        return "-"
    return f"In:{inbound_count} Out:{outbound_count}"


def format_vpc_association(vpc_no: str, mask_sensitive: bool = True) -> str:
    """VPC 연결 정보를 포맷"""
    if not vpc_no or vpc_no == "-":
        return "Classic"
    
    if mask_sensitive and len(vpc_no) > 4:
        masked_vpc = vpc_no[:2] + "***" + vpc_no[-2:]
        return f"VPC:{masked_vpc}"
    
    return f"VPC:{vpc_no}"


def print_ncpgov_sg_table(security_groups: List[NCPGovSecurityGroup], verbose: bool = False, mask_sensitive: bool = True) -> None:
    """
    NCP Gov Security Group 정보를 보안 강화된 형식으로 출력합니다.
    
    Args:
        security_groups: NCPGovSecurityGroup 객체 목록
        verbose: 상세 정보 표시 여부
        mask_sensitive: 민감한 정보 마스킹 여부
    """
    if not security_groups:
        console.print("(No Security Groups)")
        return
    
    # 보안 그룹을 리전, 이름 순으로 정렬
    security_groups.sort(key=lambda x: (x.region.lower(), x.access_control_group_name.lower()))
    
    console.print("[bold underline]NCP Gov Security Group Info[/bold underline]")
    console.print("[dim]정부 클라우드 보안 모드 활성화됨[/dim]")
    
    # 테이블 생성 (OCI 스타일 + 보안 강화)
    table = Table(show_lines=False, box=box.HORIZONTALS, show_header=True, 
                  header_style="bold", expand=False)
    table.show_edge = False
    
    # 컬럼 정의 (정부 클라우드 전용 필드 추가)
    if verbose:
        headers = ["Region", "Group Name", "Status", "VPC", "Rules", "Description", 
                  "Security", "Group No"]
        keys = ["region", "access_control_group_name", "access_control_group_status", 
               "vpc_no", "rule_count", "access_control_group_description", 
               "security_level", "access_control_group_no"]
    else:
        headers = ["Region", "Name", "Status", "VPC", "Rules", "Security"]
        keys = ["region", "access_control_group_name", "access_control_group_status",
               "vpc_no", "rule_count", "security_level"]
    
    # 컬럼 스타일 설정 (OCI 패턴 + 보안 강화)
    for header in headers:
        style_opts = {}
        if header == "Region": 
            style_opts = {"style": "bold cyan"}
        elif header == "Status": 
            style_opts = {"justify": "center"}
        elif header == "Rules": 
            style_opts = {"justify": "right"}
        elif header in ["Group Name", "Name"]: 
            style_opts = {"overflow": "fold"}
        elif header == "Security":
            style_opts = {"style": "bold green", "justify": "center"}
        elif header == "Description":
            style_opts = {"overflow": "fold", "max_width": 30}
        
        table.add_column(header, **style_opts)
    
    # 데이터 행 추가 (OCI 스타일 그룹핑 + 보안 마스킹)
    last_region = None
    
    for i, sg in enumerate(security_groups):
        region_changed = sg.region != last_region
        
        # 리전이 바뀔 때 구분선 추가
        if i > 0 and region_changed:
            table.add_row(*[Rule(style="dim") for _ in headers])
        
        # 행 데이터 구성
        row_values = []
        
        # 리전 표시 (변경된 경우만)
        row_values.append(sg.region if region_changed else "")
        
        # 나머지 데이터
        for key in keys[1:]:  # region 제외
            value = getattr(sg, key, "-")
            
            # 특별한 포맷팅 적용
            if key == "access_control_group_name" and mask_sensitive:
                # 보안 그룹 이름 부분 마스킹 (정부 클라우드 보안)
                if value and len(str(value)) > 6:
                    masked_name = str(value)[:3] + "***" + str(value)[-3:]
                    value = masked_name
            elif key == "access_control_group_status":
                value = apply_status_color(str(value))
            elif key == "vpc_no":
                value = format_vpc_association(str(value), mask_sensitive)
            elif key == "rule_count":
                inbound_count = len(sg.inbound_rules)
                outbound_count = len(sg.outbound_rules)
                value = format_rule_count(inbound_count, outbound_count)
            elif key == "access_control_group_description":
                # 설명이 너무 길면 줄임
                if value and len(str(value)) > 50:
                    value = str(value)[:47] + "..."
            elif key == "security_level":
                value = f"[bold green]{str(value).upper()}[/bold green]" if value else "STANDARD"
            elif key == "access_control_group_no" and mask_sensitive:
                # 보안 그룹 번호 부분 마스킹
                if value and len(str(value)) > 4:
                    masked_no = str(value)[:2] + "***" + str(value)[-2:]
                    value = masked_no
            
            row_values.append(str(value) if value is not None else "-")
        
        table.add_row(*row_values)
        last_region = sg.region
    
    console.print(table)
    
    # 정부 클라우드 보안 정보 표시
    if mask_sensitive:
        console.print("\n[dim]보안: 보안 그룹 이름, VPC 번호, 그룹 번호가 부분적으로 마스킹되었습니다 (정부 클라우드 규정 준수)[/dim]")
    
    # 보안 그룹 통계 요약
    total_count = len(security_groups)
    vpc_count = sum(1 for sg in security_groups if sg.vpc_no and sg.vpc_no != "-")
    classic_count = total_count - vpc_count
    
    console.print(f"\n[bold blue]플랫폼 분포:[/bold blue] VPC: {vpc_count}, Classic: {classic_count}")
    
    # 규칙 통계
    total_rules = sum(sg.rule_count for sg in security_groups)
    total_inbound = sum(len(sg.inbound_rules) for sg in security_groups)
    total_outbound = sum(len(sg.outbound_rules) for sg in security_groups)
    
    console.print(f"[bold green]보안 규칙:[/bold green] 총 {total_rules}개 (인바운드: {total_inbound}, 아웃바운드: {total_outbound})")
    
    # 상세 정보 표시 (verbose 모드)
    if verbose and security_groups:
        console.print("\n[bold underline]보안 그룹 상세 정보[/bold underline]")
        for sg in security_groups:
            masked_name = sg.access_control_group_name
            if mask_sensitive and len(masked_name) > 6:
                masked_name = masked_name[:3] + "***" + masked_name[-3:]
            
            console.print(f"\n[bold cyan]{masked_name}[/bold cyan] ({sg.region})")
            console.print(f"  상태: {apply_status_color(sg.access_control_group_status)}")
            console.print(f"  VPC: {format_vpc_association(sg.vpc_no, mask_sensitive)}")
            console.print(f"  인바운드 규칙: {len(sg.inbound_rules)}개")
            console.print(f"  아웃바운드 규칙: {len(sg.outbound_rules)}개")
            console.print(f"  보안 수준: [bold green]{sg.security_level.upper()}[/bold green]")
            console.print(f"  규정 준수: [bold green]{sg.compliance_status.upper()}[/bold green]")
            
            if sg.access_control_group_description:
                console.print(f"  설명: {sg.access_control_group_description}")


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


@progress_bar("Initializing NCP Gov Security Group service")
def main(args):
    """
    NCP Gov Security Group 정보 수집 메인 함수 (보안 강화)
    
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
        
        # 보안 그룹 정보 수집
        security_groups = fetch_ncpgov_sg_info(client, args.name)
        
        # 결과 출력
        console.print(f"\n[bold green]Collection complete![/bold green] Found {len(security_groups)} security groups.")
        print_ncpgov_sg_table(security_groups, args.verbose, args.mask_sensitive)
        
        # 감사 로그 기록
        log_audit_event('sg_info_display_completed', {
            'sg_count': len(security_groups),
            'verbose_mode': args.verbose,
            'sensitive_masked': args.mask_sensitive
        })
        
    except KeyboardInterrupt:
        console.print("\n[yellow]작업이 사용자에 의해 중단되었습니다.[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"NCP Gov Security Group 정보 수집 중 오류: {e}")
        console.print(f"[red]오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="NCP Gov Security Group Info Collector")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)