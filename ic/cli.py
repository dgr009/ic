#!/usr/bin/env python3

import argparse
import sys
from dotenv import load_dotenv
from common.log import log_error, log_env_short, log_args_short
from common.gather_env import gather_env_for_command
from aws.ec2 import list_tags as ec2_list_tags
from aws.ec2 import tag_check as ec2_tag_check
from aws.ec2 import list_info as ec2_list_info
from aws.lb import list_tags as lb_list_tags
from aws.lb import tag_check as lb_tag_check
from aws.vpc import tag_check as vpc_tag_check
from aws.vpc import list_tags as vpc_list_tags
from aws.rds import list_tags as rds_list_tags
from aws.rds import tag_check as rds_tag_check
from aws.s3 import list_tags as s3_list_tags
from aws.s3 import tag_check as s3_tag_check
from cf.dns import list_info as dns_list_info
from oci_module.info import oci_info as oci_info # Deprecated. 통합 oci info
from oci_module.vm import add_arguments as vm_add_args, main as vm_main
from oci_module.lb import add_arguments as lb_add_args, main as lb_main
from oci_module.nsg import add_arguments as nsg_add_args, main as nsg_main
from oci_module.volume import add_arguments as volume_add_args, main as volume_main
from oci_module.policy import add_arguments as policy_add_args, main as policy_main
from oci_module.policy import search as oci_policy_search
from oci_module.obj import add_arguments as obj_add_args, main as obj_main
from oci_module.cost import usage_add_arguments as cost_usage_add_args, usage_main as cost_usage_main
from oci_module.cost import credit_add_arguments as cost_credit_add_args, credit_main as cost_credit_main
from oci_module.vcn import info as vcn_info
from ssh import auto_ssh, server_info

load_dotenv()

def oci_info_deprecated(args):
    from rich.console import Console
    console = Console()
    console.print("\n[bold yellow]⚠️ 'ic oci info' 명령어는 더 이상 사용되지 않습니다.[/bold yellow]")
    console.print("대신 각 서비스별 `info` 명령어를 사용해주세요. 예시:\n")
    console.print("  - `ic oci vm info`")
    console.print("  - `ic oci lb info`")
    console.print("  - `ic oci nsg info`")
    console.print("  - `ic oci volume info`")
    console.print("  - `ic oci obj info`")
    console.print("  - `ic oci policy info`\n")
    console.print("  - 여러 서비스 : `ic oci vm,lb,nsg,volume,obj,policy info`\n")
    console.print("전체 OCI 명령어는 `ic oci --help`로 확인하실 수 있습니다.")

def main():
    """IC CLI 엔트리 포인트"""
    parser = argparse.ArgumentParser(
        description="Infra CLI: Platform Resource CLI Tool",
        usage="ic <platform> <service> <command> [options]"
    )
    platform_subparsers = parser.add_subparsers(
        dest="platform",
        required=True,
        help="클라우드 플랫폼 (aws, oci, cf, ssh, utill 등)"
    )
    
    aws_parser = platform_subparsers.add_parser("aws", help="AWS 관련 명령어")
    cf_parser = platform_subparsers.add_parser("cf", help="CloudFlare 관련 명령어")
    oci_parser = platform_subparsers.add_parser("oci", help="OCI 관련 명령어")
    ssh_parser = platform_subparsers.add_parser("ssh", help="SSH 관련 명령어")

    aws_subparsers = aws_parser.add_subparsers(dest="service",required=True,help="AWS 리소스 관리 서비스")
    cf_subparsers = cf_parser.add_subparsers(dest="service",required=True,help="CloudFlare 리소스 관리 서비스")
    oci_subparsers = oci_parser.add_subparsers(dest="service",required=True,help="OCI 리소스 관리 서비스")
    ssh_subparsers = ssh_parser.add_subparsers(dest="service",required=True,help="SSH 관리 서비스")

    # ---------------- AWS ----------------
    ec2_parser = aws_subparsers.add_parser("ec2", help="EC2 관련 명령어")
    ec2_subparsers = ec2_parser.add_subparsers(dest="command", required=True)
    ec2_list_tags_parser = ec2_subparsers.add_parser("list_tags", help="EC2 인스턴스 태그 나열")
    ec2_list_tags.add_arguments(ec2_list_tags_parser)
    ec2_list_tags_parser.set_defaults(func=ec2_list_tags.main)
    ec2_tag_check_parser = ec2_subparsers.add_parser("tag_check", help="EC2 태그 유효성 검사")
    ec2_tag_check.add_arguments(ec2_tag_check_parser)
    ec2_tag_check_parser.set_defaults(func=ec2_tag_check.main)
    ec2_list_info_parser = ec2_subparsers.add_parser("list_info", help="EC2 인스턴스 정보 나열")
    ec2_list_info.add_arguments(ec2_list_info_parser)
    ec2_list_info_parser.set_defaults(func=ec2_list_info.main)

    lb_parser = aws_subparsers.add_parser("lb", help="LB 관련 명령어")
    lb_subparsers = lb_parser.add_subparsers(dest="command", required=True)
    lb_list_parser = lb_subparsers.add_parser("list_tags", help="LB 태그 조회")
    lb_list_tags.add_arguments(lb_list_parser)
    lb_list_parser.set_defaults(func=lb_list_tags.main)
    lb_check_parser = lb_subparsers.add_parser("tag_check", help="LB 태그 유효성 검사")
    lb_tag_check.add_arguments(lb_check_parser)
    lb_check_parser.set_defaults(func=lb_tag_check.main)

    vpc_parser = aws_subparsers.add_parser("vpc", help="VPC + Gateway + VPN 관련 명령어")
    vpc_subparsers = vpc_parser.add_subparsers(dest="command", required=True)
    vpc_check_parser = vpc_subparsers.add_parser("tag_check", help="VPC + Gateway + VPN 태그 유효성 검사")
    vpc_tag_check.add_arguments(vpc_check_parser)
    vpc_check_parser.set_defaults(func=vpc_tag_check.main)
    vpc_list_parser = vpc_subparsers.add_parser("list_tags", help="VPC + Gateway + VPN 태그 조회")
    vpc_tag_check.add_arguments(vpc_list_parser)
    vpc_list_parser.set_defaults(func=vpc_list_tags.main)

    rds_parser = aws_subparsers.add_parser("rds", help="RDS 관련 명령어")
    rds_subparsers = rds_parser.add_subparsers(dest="command", required=True)
    rds_list_cmd = rds_subparsers.add_parser("list_tags", help="RDS 태그 조회")
    rds_list_tags.add_arguments(rds_list_cmd)
    rds_list_cmd.set_defaults(func=rds_list_tags.main)
    rds_check_cmd = rds_subparsers.add_parser("tag_check", help="RDS 태그 유효성 검사")
    rds_tag_check.add_arguments(rds_check_cmd)
    rds_check_cmd.set_defaults(func=rds_tag_check.main)

    s3_parser = aws_subparsers.add_parser("s3", help="S3 관련 명령어")
    s3_subparsers = s3_parser.add_subparsers(dest="command", required=True)
    s3_list_cmd = s3_subparsers.add_parser("list_tags", help="S3 버킷 태그 조회")
    s3_list_tags.add_arguments(s3_list_cmd)
    s3_list_cmd.set_defaults(func=s3_list_tags.main)
    s3_check_cmd = s3_subparsers.add_parser("tag_check", help="S3 태그 유효성 검사")
    s3_tag_check.add_arguments(s3_check_cmd)
    s3_check_cmd.set_defaults(func=s3_tag_check.main)

    # ---------------- CloudFlare ----------------
    cf_parser = cf_subparsers.add_parser("dns", help="DNS Record 관련 명령어")
    dns_subparsers = cf_parser.add_subparsers(dest="command", required=True)
    dns_list_cmd = dns_subparsers.add_parser("list_info", help="DNS Record 목록 조회")
    dns_list_info.add_arguments(dns_list_cmd)
    dns_list_cmd.set_defaults(func=dns_list_info.main)

    # ---------------- SSH ----------------
    # 'ic ssh info' - 서버 정보 상세 조회
    ssh_info_parser = ssh_subparsers.add_parser("info", help="등록된 SSH 서버의 상세 정보(CPU/Mem/Disk)를 스캔합니다.")
    ssh_info_parser.add_argument("--host", help="특정 호스트 문자열을 포함하는 서버만 필터링합니다.")
    ssh_info_parser.add_argument("--key", help="사용할 특정 프라이빗 키 파일을 지정합니다. (config 파일 우선)")
    ssh_info_parser.set_defaults(func=server_info.main)

    # 'ic ssh reg' - 신규 서버 스캔 및 등록
    ssh_reg_parser = ssh_subparsers.add_parser("reg", help="네트워크를 스캔하여 새로운 SSH 서버를 찾아 .ssh/config에 등록합니다.")
    ssh_reg_parser.set_defaults(func=lambda args: auto_ssh.main())

    # ---------------- OCI ----------------
    oci_info_parser = oci_subparsers.add_parser("info", help="[DEPRECATED] OCI 리소스 통합 조회. 각 서비스별 명령어를 사용하세요.")
    
    oci_info_parser.set_defaults(func=oci_info_deprecated)
    
    # ---- new structured services ----
    # VM
    vm_parser = oci_subparsers.add_parser("vm", help="OCI VM(Instance) 관련")
    vm_sub = vm_parser.add_subparsers(dest="command", required=True)
    vm_info_p = vm_sub.add_parser("info", help="VM 정보 조회")
    vm_add_args(vm_info_p)
    vm_info_p.set_defaults(func=vm_main)

    # LB
    lb_parser = oci_subparsers.add_parser("lb", help="OCI LoadBalancer 관련")
    lb_sub = lb_parser.add_subparsers(dest="command", required=True)
    lb_info_p = lb_sub.add_parser("info", help="LB 정보 조회")
    lb_add_args(lb_info_p)
    lb_info_p.set_defaults(func=lb_main)

    # NSG
    nsg_parser = oci_subparsers.add_parser("nsg", help="OCI NSG 관련")
    nsg_sub = nsg_parser.add_subparsers(dest="command", required=True)
    nsg_info_p = nsg_sub.add_parser("info", help="NSG 정보 조회")
    nsg_add_args(nsg_info_p)
    nsg_info_p.set_defaults(func=nsg_main)

    # VCN
    vcn_parser = oci_subparsers.add_parser("vcn", help="OCI VCN 관련")
    vcn_sub = vcn_parser.add_subparsers(dest="command", required=True)
    vcn_info_p = vcn_sub.add_parser("info", help="VCN, Subnet, Route Table 정보 조회")
    vcn_info.add_arguments(vcn_info_p)
    vcn_info_p.set_defaults(func=vcn_info.main)

    # Volume
    vol_parser = oci_subparsers.add_parser("volume", help="OCI Block/Boot Volume 관련")
    vol_sub = vol_parser.add_subparsers(dest="command", required=True)
    vol_info_p = vol_sub.add_parser("info", help="Volume 정보 조회")
    volume_add_args(vol_info_p)
    vol_info_p.set_defaults(func=volume_main)

    # Object Storage
    obj_parser = oci_subparsers.add_parser("obj", help="OCI Object Storage 관련")
    obj_sub = obj_parser.add_subparsers(dest="command", required=True)
    obj_info_p = obj_sub.add_parser("info", help="Bucket 정보 조회")
    obj_add_args(obj_info_p)
    obj_info_p.set_defaults(func=obj_main)

    # Policy
    pol_parser = oci_subparsers.add_parser("policy", help="OCI Policy 관련")
    pol_sub = pol_parser.add_subparsers(dest="command", required=True)
    pol_info_p = pol_sub.add_parser("info", help="Policy 목록/구문 조회")
    policy_add_args(pol_info_p)
    pol_info_p.set_defaults(func=policy_main)
    pol_search_p = pol_sub.add_parser("search", help="Policy 구문 검색")
    oci_policy_search.add_arguments(pol_search_p)
    pol_search_p.set_defaults(func=oci_policy_search.main)

    # Cost
    cost_parser = oci_subparsers.add_parser("cost", help="OCI 비용/크레딧 관련")
    cost_sub = cost_parser.add_subparsers(dest="command", required=True)
    cost_usage_p = cost_sub.add_parser("usage", help="비용 조회")
    cost_usage_add_args(cost_usage_p)
    cost_usage_p.set_defaults(func=cost_usage_main)
    cost_credit_p = cost_sub.add_parser("credit", help="크레딧 사용 조회")
    cost_credit_add_args(cost_credit_p)
    cost_credit_p.set_defaults(func=cost_credit_main)

    # 인수 처리
    process_and_execute_commands(parser)

def process_and_execute_commands(parser):
    """명령행 인수를 파싱하고 각 서비스에 대해 명령을 실행합니다."""
    # 'ic oci info'는 다른 인수와 상관없이 항상 deprecated 메시지를 출력합니다.
    if len(sys.argv) > 2 and sys.argv[1] == 'oci' and sys.argv[2] == 'info':
        oci_info_deprecated(None)
        sys.exit(0)
        
    # 서비스 인수에 콤마가 있는지 확인
    if len(sys.argv) > 2 and ',' in sys.argv[2]:
        platform = sys.argv[1]
        services = [s.strip() for s in sys.argv[2].split(',')]
        command_and_options = sys.argv[3:]
        
        has_error = False
        for service in services:
            print(f"--- Executing: ic {platform} {service} {' '.join(command_and_options)} ---")
            current_argv = [platform, service] + command_and_options
            try:
                args = parser.parse_args(current_argv)
                execute_single_command(args)
            except SystemExit:
                # argparse는 오류 발생 시 SystemExit을 호출하므로, 이를 잡아서 계속 진행합니다.
                print(f"--- Skipping service '{service}' due to an error or invalid arguments ---")
                has_error = True
            except Exception as e:
                log_error(f"Error processing service '{service}': {e}")
                has_error = True
        
        if has_error:
            sys.exit(1)
            
    else:
        # 단일 서비스 실행 (기존 로직)
        try:
            args = parser.parse_args()
            execute_single_command(args)
        except SystemExit:
            # 사용자가 도움말을 요청했거나 잘못된 인수를 입력한 경우, argparse가 종료됩니다.
            # 정상적인 동작이므로 추가 처리가 필요 없습니다.
            sys.exit(0)
        except Exception as e:
            log_error(f"명령어 실행 중 오류 발생: {e}")
            sys.exit(1)

def execute_single_command(args):
    """파싱된 인수를 기반으로 실제 단일 명령을 실행합니다."""
    if not hasattr(args, 'service') or not args.service:
        # 'ic' 또는 'ic oci'와 같이 service나 command가 없는 경우
        # argparse가 자동으로 도움말을 출력하고 종료하므로 이 부분은 거의 호출되지 않습니다.
        return

    # 기존의 예외처리 로직을 여기에 포함
    if args.platform == "ssh" and args.service == "info":
        args.command = "none"
    elif args.platform == "oci" and args.service == "info":
        args.command = "none"

    log_args_short(args)
    env_used = gather_env_for_command(args.platform, args.service, args.command)
    if env_used:
        log_env_short(env_used)

    if hasattr(args, 'func'):
        args.func(args)
    else:
        log_error(f"'{args.service}' 서비스에 대해 실행할 명령어가 지정되지 않았습니다. 'ic {args.platform} {args.service} --help'를 확인하세요.")
        raise ValueError("No function to execute")

if __name__ == "__main__":
    main() 