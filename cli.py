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
from aws.vpc import tag_check as vpc_tag_check
from aws.vpc import list_tags as vpc_list_tags
from aws.rds import list_tags as rds_list_tags
from aws.rds import tag_check as rds_tag_check
from aws.s3 import list_tags as s3_list_tags
from aws.s3 import tag_check as s3_tag_check
from cf.dns import list_info as dns_list_info
from oci_module.info import oci_info as oci_info
from ssh import server_info as ssh_info

load_dotenv()

def main():
    """IC CLI 엔트리 포인트"""
    parser = argparse.ArgumentParser(
        description="Infra CLI: Platform Resource CLI Tool",
        usage="ic <service> <command> [options]"
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
    # aws_subparsers = aws_parser.add_subparsers(dest="service",required=True,help="AWS 리소스 관리 서비스")

    #-------------------------------------------------------------------------
    #------------------------------- AWS -------------------------------------
    #-------------------------------------------------------------------------

    # EC2 명령어 추가
    ec2_parser = aws_subparsers.add_parser("ec2", help="EC2 관련 명령어")
    ec2_subparsers = ec2_parser.add_subparsers(dest="command", required=True)

    # list_tags 명령어 추가
    ec2_list_tags_parser = ec2_subparsers.add_parser("list_tags", help="EC2 인스턴스 태그 나열")
    ec2_list_tags.add_arguments(ec2_list_tags_parser)
    ec2_list_tags_parser.set_defaults(func=ec2_list_tags.main)

    # tag_check 명령어 추가
    ec2_tag_check_parser = ec2_subparsers.add_parser("tag_check", help="EC2 태그 유효성 검사")
    ec2_tag_check.add_arguments(ec2_tag_check_parser)
    ec2_tag_check_parser.set_defaults(func=ec2_tag_check.main)

    # list_info 명령어 추가
    ec2_list_info_parser = ec2_subparsers.add_parser("list_info", help="EC2 인스턴스 정보 나열")
    ec2_list_info.add_arguments(ec2_list_info_parser)
    ec2_list_info_parser.set_defaults(func=ec2_list_info.main)

    # LB 명령어 추가
    lb_parser = aws_subparsers.add_parser("lb", help="LB 관련 명령어")
    lb_subparsers = lb_parser.add_subparsers(dest="command", required=True)

    lb_list_parser = lb_subparsers.add_parser("list_tags", help="LB 태그 조회")
    lb_list_tags.add_arguments(lb_list_parser)
    lb_list_parser.set_defaults(func=lb_list_tags.main)

    lb_check_parser = lb_subparsers.add_parser("tag_check", help="LB 태그 유효성 검사")
    lb_tag_check.add_arguments(lb_check_parser)
    lb_check_parser.set_defaults(func=lb_tag_check.main)

    # VPC 명령어 추가
    vpc_parser = aws_subparsers.add_parser("vpc", help="VPC + Gateway + VPN 관련 명령어")
    vpc_subparsers = vpc_parser.add_subparsers(dest="command", required=True)

    vpc_check_parser = vpc_subparsers.add_parser("tag_check", help="VPC + Gateway + VPN 태그 유효성 검사")
    vpc_tag_check.add_arguments(vpc_check_parser)
    vpc_check_parser.set_defaults(func=vpc_tag_check.main)


    vpc_list_parser = vpc_subparsers.add_parser("list_tags", help="VPC + Gateway + VPN 태그 조회")
    vpc_tag_check.add_arguments(vpc_list_parser)
    vpc_list_parser.set_defaults(func=vpc_list_tags.main)

    # RDS 명령어 추가
    rds_parser = aws_subparsers.add_parser("rds", help="RDS 관련 명령어")
    rds_subparsers = rds_parser.add_subparsers(dest="command", required=True)

    rds_list_cmd = rds_subparsers.add_parser("list_tags", help="RDS 태그 조회")
    rds_list_tags.add_arguments(rds_list_cmd)
    rds_list_cmd.set_defaults(func=rds_list_tags.main)

    rds_check_cmd = rds_subparsers.add_parser("tag_check", help="RDS 태그 유효성 검사")
    rds_tag_check.add_arguments(rds_check_cmd)
    rds_check_cmd.set_defaults(func=rds_tag_check.main)

    # S3 명령어 추가
    s3_parser = aws_subparsers.add_parser("s3", help="S3 관련 명령어")
    s3_subparsers = s3_parser.add_subparsers(dest="command", required=True)

    s3_list_cmd = s3_subparsers.add_parser("list_tags", help="S3 버킷 태그 조회")
    s3_list_tags.add_arguments(s3_list_cmd)
    s3_list_cmd.set_defaults(func=s3_list_tags.main)

    s3_check_cmd = s3_subparsers.add_parser("tag_check", help="S3 태그 유효성 검사")
    s3_tag_check.add_arguments(s3_check_cmd)
    s3_check_cmd.set_defaults(func=s3_tag_check.main)

    #-------------------------------------------------------------------------
    #----------------------------- CloudFlare --------------------------------
    #-------------------------------------------------------------------------
    cf_parser = cf_subparsers.add_parser("dns", help="DNS Record 관련 명령어")
    dns_subparsers = cf_parser.add_subparsers(dest="command", required=True)

    dns_list_cmd = dns_subparsers.add_parser("list_info", help="DNS Record 목록 조회")
    dns_list_info.add_arguments(dns_list_cmd)
    dns_list_cmd.set_defaults(func=dns_list_info.main)


    #-------------------------------------------------------------------------
    #-------------------------------- OCI ------------------------------------
    #-------------------------------------------------------------------------
    oci_parser = oci_subparsers.add_parser("info", help="OCI 관련 명령어")
    oci_info.add_arguments(oci_parser)
    oci_parser.set_defaults(func=oci_info.main)


    #-------------------------------------------------------------------------
    #-------------------------------- SSH ------------------------------------
    #-------------------------------------------------------------------------
    ssh_parser = ssh_subparsers.add_parser("info", help="SSH 등록된 서버정보 출력")
    ssh_parser.set_defaults(func=ssh_info.main)

    # 명령어 인수 처리
    args = parser.parse_args()

    if not args.service:
        parser.print_help()
        sys.exit(1)
    elif args.platform == "oci" or args.platform == "ssh":
        args.command = "none"

    log_args_short(args)
    env_used = gather_env_for_command(args.platform, args.service, args.command)
    if env_used:
        log_env_short(env_used)  # dict 형태 그대로 찍어도 좋음


    try:
        args.func(args)  # 실행할 함수 호출
    except Exception as e:
        log_error(f"명령어 실행 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
