#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCI IAM Policy 검색 모듈

사용자 또는 그룹을 선택하여 관련된 IAM 정책을 트리 형태로 출력합니다.
IC 프로젝트의 공용 모듈을 사용하도록 리팩토링되었습니다.
"""

import oci
import os
import re
from ic.config.manager import ConfigManager
from InquirerPy import inquirer
from rich.console import Console
from rich.tree import Tree
from rich.prompt import Prompt

from common.log import log_info, log_error, log_exception, console
from common.progress_decorator import progress_bar, ManualProgress

# Initialize config manager
_config_manager = ConfigManager()


def add_arguments(parser):
    """CLI 인자 정의"""
    # parser.add_argument("-p", "--policy", action="store_true", 
    #                    help="사용자/그룹의 IAM 정책 검색")
    parser.add_argument("--config-path", default=None,
                       help="OCI config 파일 경로 (기본: ~/.oci/config)")
    parser.add_argument("--profile", default="DEFAULT",
                       help="OCI config 프로파일 (기본: DEFAULT)")
    parser.add_argument("--show-empty", action="store_true",
                       help="정책이 없는 컴파트먼트도 표시")


def load_config_from_env(config_path=None, profile="DEFAULT"):
    """환경변수 또는 인자에서 OCI config 로드"""
    if not config_path:
        config_path = os.environ.get("OCI_CONFIG_PATH", os.path.expanduser("~/.oci/config"))
    
    try:
        config = oci.config.from_file(file_location=config_path, profile_name=profile)
        # log_info(f"OCI config 로드 성공: {config_path} (profile: {profile})")
        return config
    except Exception as e:
        log_exception(e)
        log_error(f"OCI config를 불러오는 데 실패했습니다: {e}")
        raise RuntimeError(f"❌ OCI config를 불러오는 데 실패했습니다: {e}")


@progress_bar("Loading OCI users and groups")
def select_user_or_group(config):
    """사용자 또는 그룹 선택"""
    identity = oci.identity.IdentityClient(config)
    
    try:
        # 사용자 및 그룹 목록 가져오기
        # log_info("사용자 및 그룹 목록을 가져오는 중...")
        users = identity.list_users(config["tenancy"]).data
        groups = identity.list_groups(config["tenancy"]).data
        
        # 선택지 생성
        user_choices = [f"User: {user.name}" for user in users]
        group_choices = [f"Group: {group.name}" for group in groups]
        choices = user_choices + group_choices
        
        if not choices:
            log_error("사용 가능한 사용자나 그룹이 없습니다")
            return None
        
        selected_name = inquirer.fuzzy(
            message="📁 사용할 사용자 또는 그룹을 선택하세요:",
            choices=choices
        ).execute()
                
        # log_info(f"선택된 항목: {selected_name}")
        console.print(f"[green]✅ 선택된 항목:[/green] {selected_name}")
        return selected_name
        
    except Exception as e:
        log_exception(e)
        log_error(f"사용자/그룹 목록 조회 실패: {e}")
        raise


def list_related_policies(selected_name, config, show_empty_compartments=False):
    """선택된 사용자/그룹과 관련된 정책들을 트리 형태로 출력"""
    identity = oci.identity.IdentityClient(config)
    
    try:
        tree = Tree(f"[bold green]Selected: {selected_name}[/bold green]")
        
        user_group_names = set()
        is_user = selected_name.startswith("User:")
        selected_value = selected_name.split(": ")[1]
        
        if is_user:
            # 사용자가 속한 그룹 이름들을 수집
            # log_info(f"사용자 {selected_value}의 그룹 멤버십 조회 중...")
            users = identity.list_users(config["tenancy"]).data
            user = next((u for u in users if u.name == selected_value), None)
            if user:
                memberships = identity.list_user_group_memberships(
                    compartment_id=config["tenancy"], 
                    user_id=user.id
                ).data
                if memberships:
                    group_branch = tree.add("[cyan]Groups:[/cyan]")
                    for membership in memberships:
                        group = identity.get_group(membership.group_id).data
                        group_branch.add(f"[cyan]{group.name}[/cyan]")
                        user_group_names.add(group.name)
                        
        # Compartment 및 정책 가져오기
        # log_info("컴파트먼트 및 정책 정보 조회 중...")
        compartments = identity.list_compartments(
            config["tenancy"], 
            compartment_id_in_subtree=True, 
            access_level="ACCESSIBLE"
        ).data
        root_tenancy = identity.get_compartment(config["tenancy"]).data
        compartments.insert(0, root_tenancy)
        
        policy_found = False
        
        with ManualProgress(f"Searching policies across {len(compartments)} compartments", total=len(compartments)) as progress:
            for i, compartment in enumerate(compartments):
                try:
                    policies = identity.list_policies(compartment.id).data
                    if not policies and not show_empty_compartments:
                        progress.update(f"Skipped {compartment.name} (no policies)", advance=1)
                        continue
                        
                    compartment_branch = None
                    compartment_has_matching_policies = False
                    matching_policies_count = 0
                    
                    for policy in policies:
                        matched_statements = []
                        for statement in policy.statements:
                            if is_user:
                                # 사용자의 경우 그룹 멤버십을 통해 정책 확인
                                if any(re.search(rf"\bGROUP {re.escape(group_name)}\b", statement) 
                                      for group_name in user_group_names):
                                    matched_statements.append(statement)
                            else:
                                # 그룹의 경우 직접 정책 확인
                                group_name = selected_value
                                if re.search(rf"\bGROUP {re.escape(group_name)}\b", statement):
                                    matched_statements.append(statement)
                        
                        if matched_statements:
                            # 매칭되는 정책이 있을 때만 compartment branch 생성
                            if compartment_branch is None:
                                compartment_branch = tree.add(f"[blue]Compartment: {compartment.name}[/blue]")
                            
                            policy_branch = compartment_branch.add(f"[dark_orange]Policy: {policy.name}[/dark_orange]")
                            for statement in matched_statements:
                                policy_branch.add(f"[bold white]{statement}[/bold white]")
                            compartment_has_matching_policies = True
                            matching_policies_count += 1
                            policy_found = True
                            
                    # show_empty가 true이고 정책이 있지만 매칭되는 게 없으면 빈 compartment 표시
                    if show_empty_compartments and policies and not compartment_has_matching_policies:
                        if compartment_branch is None:
                            compartment_branch = tree.add(f"[blue]Compartment: {compartment.name}[/blue]")
                        compartment_branch.add("[dim](No matching policies)[/dim]")
                    
                    if matching_policies_count > 0:
                        progress.update(f"Processed {compartment.name} - Found {matching_policies_count} matching policies", advance=1)
                    else:
                        progress.update(f"Processed {compartment.name} - No matches", advance=1)
                         
                except Exception as e:
                    log_error(f"컴파트먼트 {compartment.name} 정책 조회 실패: {e}")
                    progress.update(f"Failed to process {compartment.name}", advance=1)
                    continue
                
        if not policy_found:
            tree.add("[yellow]⚠️  관련된 정책을 찾을 수 없습니다.[/yellow]")
        
        # 구분선과 함께 결과 출력
        console.rule("[bold blue]🔍 OCI IAM Policy 검색 결과[/bold blue]", style="blue")
        console.print(tree)
        console.rule(style="blue")
        # log_info("정책 검색 완료")
        
    except Exception as e:
        log_exception(e)
        log_error(f"정책 조회 실패: {e}")
        raise


@progress_bar("Initializing OCI policy search")
def main(args):
    """OCI 정책 검색 메인 함수"""
    try:
        # if not args.policy:
        #     console.print("[yellow]⚠️  -p 또는 --policy 옵션을 사용하여 정책 검색을 활성화하세요.[/yellow]")
        #     console.print("[cyan]사용법:[/cyan] ic oci search -p")
        #     return
            
        # log_info("OCI 정책 검색 시작")
        
        # OCI config 로드
        config = load_config_from_env(args.config_path, args.profile)
        
        # 사용자 또는 그룹 선택
        selected_name = select_user_or_group(config)
        if not selected_name:
            log_error("사용자/그룹이 선택되지 않았습니다")
            return
            
        # 관련 정책 및 문장 나열
        list_related_policies(selected_name, config, args.show_empty)
        
        # log_info("OCI 정책 검색 완료")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  사용자에 의해 취소되었습니다.[/yellow]")
    except Exception as e:
        log_exception(e)
        log_error(f"정책 검색 중 오류 발생: {e}")
        console.print(f"[bold red]❌ 오류 발생:[/bold red] {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OCI IAM Policy 검색")
    add_arguments(parser)
    args = parser.parse_args()
    main(args) 