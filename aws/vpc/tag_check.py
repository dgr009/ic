# aws/vpc/tag_check.py

import os
import re
import botocore
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from common.log import log_info, log_error, log_exception, log_decorator
from common.slack import send_slack_blocks_table_with_color
from common.utils import create_session, get_profiles, get_env_accounts, DEFINED_REGIONS
from rich.console import Console
from rich.table import Table

# 새로운 설정 시스템 import
try:
    from ic.config.manager import ConfigManager
    config_manager = ConfigManager()
    config = config_manager.get_config()
except ImportError:
    # 호환성을 위한 fallback
    from dotenv import load_dotenv
    load_dotenv()
    config = {}

console = Console()

def get_tag_validation_config():
    """설정에서 태그 검증 규칙을 가져옵니다."""
    if config and 'aws' in config and 'tags' in config['aws']:
        aws_tags = config['aws']['tags']
        required_keys = aws_tags.get('required', ['User', 'Team', 'Environment'])
        rules = aws_tags.get('rules', {
            'User': r'^.+$',
            'Team': r'^\d+$',
            'Environment': r'^(PROD|STG|DEV|TEST|QA)$'
        })
    else:
        # Fallback to environment variables
        DEFAULT_REQUIRED_KEYS = ["User", "Team", "Environment"]
        DEFAULT_RULES = {
            "User": r"^.+$",
            "Team": r"^\d+$",
            "Environment": r"^(PROD|STG|DEV|TEST|QA)$"
        }
        
        env_required = os.getenv("REQUIRED_TAGS", "")
        env_required_list = [t.strip() for t in env_required.split(",") if t.strip()]
        
        ENV_RULES = {}
        for k in env_required_list:
            env_key = f"RULE_{k.upper()}"
            if env_key in os.environ:
                ENV_RULES[k] = os.environ[env_key]
        
        required_keys = sorted(set(DEFAULT_REQUIRED_KEYS + env_required_list))
        rules = {**DEFAULT_RULES, **ENV_RULES}
    
    return required_keys, rules

REQUIRED_KEYS, RULES = get_tag_validation_config()

# 콘솔 출력용 전체 열
CONSOLE_HEADER = ["Account", "Region", "VPC/TGW", "Resource", "ResourceID", "Validation Results"]

# Slack 전송용 축소 열
SLACK_HEADER = ["Account", "Region", "ResourceID", "Validation Results"]

def validate_tags(tag_dict):
    """
    필수 태그 존재 & 정규식 검사.
    """
    errors = []
    for key in REQUIRED_KEYS:
        val = tag_dict.get(key)
        if not val:
            errors.append(f"필수 '{key}' 누락")
        else:
            rule = RULES.get(key)
            if rule and not re.match(rule, val):
                errors.append(f"'{key}' 불일치: {val}")
    return errors

@log_decorator
def check_vpc_and_tgw_tags(account_id, profile_name, region):
    """
    VPC, IGW, NAT, VGW, Peering, s2s, Endpoint + TGW(본체, attach) 모두 태그 검사.
    기본 VPC는 제외.

    - rows_full: 콘솔용 (6열)
    - rows_slack: Slack용 (4열)
    """
    rows_full = []
    rows_slack = []

    session = create_session(profile_name, region)
    if not session:
        log_error(f"Session creation failed for {account_id} / {region}")
        return {"rows_full": [], "rows_slack": []}

    ec2 = session.client("ec2", region_name=region)

    # ---------------- 1) VPC (exclude default) ----------------
    valid_vpcs = {}
    try:
        vpcs_resp = ec2.describe_vpcs()
        for v in vpcs_resp.get("Vpcs", []):
            if v.get("IsDefault"):
                continue
            vpc_id = v["VpcId"]
            tag_dict = {t["Key"]: t["Value"] for t in v.get("Tags", [])}
            valid_vpcs[vpc_id] = tag_dict

            errs = validate_tags(tag_dict)
            if errs:
                err_str = " / ".join(errs)
                rows_full.append([account_id, region, vpc_id, "VPC", "-", err_str])
                rows_slack.append([account_id, region, vpc_id, err_str])
    except Exception as e:
        log_exception(e)

    # -------------- IGW --------------
    try:
        igw_resp = ec2.describe_internet_gateways()
        for igw in igw_resp.get("InternetGateways", []):
            igw_id = igw["InternetGatewayId"]
            igw_tags = {t["Key"]: t["Value"] for t in igw.get("Tags", [])}
            for attach in igw.get("Attachments", []):
                vpc_id = attach.get("VpcId")
                if not vpc_id or vpc_id not in valid_vpcs:
                    continue

                errs = validate_tags(igw_tags)
                if errs:
                    err_str = " / ".join(errs)
                    rows_full.append([account_id, region, vpc_id, "IGW", igw_id, err_str])
                    rows_slack.append([account_id, region, igw_id, err_str])
    except Exception as e:
        log_exception(e)

    # -------------- NAT (NGW) --------------
    try:
        nat_resp = ec2.describe_nat_gateways()
        for natgw in nat_resp.get("NatGateways", []):
            nat_id = natgw["NatGatewayId"]
            vpc_id = natgw.get("VpcId")
            if not vpc_id or vpc_id not in valid_vpcs:
                continue
            nat_tags = {t["Key"]: t["Value"] for t in natgw.get("Tags", [])}

            errs = validate_tags(nat_tags)
            if errs:
                err_str = " / ".join(errs)
                rows_full.append([account_id, region, vpc_id, "NGW", nat_id, err_str])
                rows_slack.append([account_id, region, nat_id, err_str])
    except Exception as e:
        log_exception(e)

    # -------------- VGW --------------
    try:
        vgw_resp = ec2.describe_vpn_gateways()
        for vgw in vgw_resp.get("VpnGateways", []):
            vgw_id = vgw["VpnGatewayId"]
            vgw_tags = {t["Key"]: t["Value"] for t in vgw.get("Tags", [])}
            for attach in vgw.get("VpcAttachments", []):
                v_id = attach.get("VpcId")
                if v_id and v_id in valid_vpcs:
                    errs = validate_tags(vgw_tags)
                    if errs:
                        err_str = " / ".join(errs)
                        rows_full.append([account_id, region, v_id, "VGW", vgw_id, err_str])
                        rows_slack.append([account_id, region, vgw_id, err_str])
    except Exception as e:
        log_exception(e)

    # -------------- Peering => Peer --------------
    try:
        peer_resp = ec2.describe_vpc_peering_connections()
        for pcx in peer_resp.get("VpcPeeringConnections", []):
            pcx_id = pcx["VpcPeeringConnectionId"]
            pcx_tags = {t["Key"]: t["Value"] for t in pcx.get("Tags", [])}
            errs = validate_tags(pcx_tags)
            if not errs:
                continue
            err_str = " / ".join(errs)

            req_vpc = pcx["RequesterVpcInfo"].get("VpcId")
            if req_vpc and req_vpc in valid_vpcs:
                rows_full.append([account_id, region, req_vpc, "Peer", pcx_id, err_str])
                rows_slack.append([account_id, region, pcx_id, err_str])

            acc_vpc = pcx["AccepterVpcInfo"].get("VpcId")
            if acc_vpc and acc_vpc in valid_vpcs:
                rows_full.append([account_id, region, acc_vpc, "Peer", pcx_id, err_str])
                rows_slack.append([account_id, region, pcx_id, err_str])
    except Exception as e:
        log_exception(e)

    # -------------- s2s --------------
    try:
        vpn_conn_resp = ec2.describe_vpn_connections()
        for vpn_conn in vpn_conn_resp.get("VpnConnections", []):
            vpn_id = vpn_conn["VpnConnectionId"]
            vgw_id = vpn_conn.get("VpnGatewayId")
            if not vgw_id:
                continue
            vpn_tags = {t["Key"]: t["Value"] for t in vpn_conn.get("Tags", [])}
            errs = validate_tags(vpn_tags)
            if not errs:
                continue
            err_str = " / ".join(errs)

            # find VPC
            try:
                single_vgw = ec2.describe_vpn_gateways(VpnGatewayIds=[vgw_id])["VpnGateways"][0]
                for att in single_vgw.get("VpcAttachments", []):
                    v_id = att.get("VpcId")
                    if v_id and v_id in valid_vpcs:
                        rows_full.append([account_id, region, v_id, "s2s", vpn_id, err_str])
                        rows_slack.append([account_id, region, vpn_id, err_str])
            except Exception as e2:
                log_exception(e2)
    except Exception as e:
        log_exception(e)

    # -------------- Endpoint => ENDPOINT --------------
    try:
        ep_resp = ec2.describe_vpc_endpoints()
        for ep in ep_resp.get("VpcEndpoints", []):
            ep_id = ep["VpcEndpointId"]
            v_id = ep.get("VpcId")
            if v_id and v_id in valid_vpcs:
                ep_tags = {t["Key"]: t["Value"] for t in ep.get("Tags", [])}
                errs = validate_tags(ep_tags)
                if errs:
                    err_str = " / ".join(errs)
                    rows_full.append([account_id, region, v_id, "ENDPOINT", ep_id, err_str])
                    rows_slack.append([account_id, region, ep_id, err_str])
    except Exception as e:
        log_exception(e)

    # -------------- TGW 본체 => "TGW" => vpc_col="-" --------------
    try:
        tgw_resp = ec2.describe_transit_gateways()
        for tgw in tgw_resp.get("TransitGateways", []):
            tgw_id = tgw["TransitGatewayId"]
            tgw_tags = {t["Key"]: t["Value"] for t in tgw.get("Tags", [])}
            errs = validate_tags(tgw_tags)
            if errs:
                err_str = " / ".join(errs)
                rows_full.append([account_id, region, "-", "TGW", tgw_id, err_str])
                rows_slack.append([account_id, region, tgw_id, err_str])
    except Exception as e:
        log_exception(e)

    # -------------- TGW Attach => "tgw-attach" => vpc_col="tgw_id"? "-"?
    try:
        tgw_attach_resp = ec2.describe_transit_gateway_attachments()
        for attach in tgw_attach_resp.get("TransitGatewayAttachments", []):
            tgw_id = attach["TransitGatewayId"]
            attach_id = attach["TransitGatewayAttachmentId"]
            attach_tags = {t["Key"]: t["Value"] for t in attach.get("Tags", [])}
            errs = validate_tags(attach_tags)
            if errs:
                err_str = " / ".join(errs)
                # 여기선 "VPC/TGW" col을 tgw_id로 표시
                rows_full.append([account_id, region, tgw_id, "tgw-attach", attach_id, err_str])
                rows_slack.append([account_id, region, attach_id, err_str])
    except Exception as e:
        log_exception(e)

    return {"rows_full": rows_full, "rows_slack": rows_slack}

@log_decorator
def check_all_vpc_tags(args):
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    # # 콘솔용 테이블
    # table = Table(title="VPC + TGW Tag Validation", show_header=True, header_style="bold magenta")
    # for col in CONSOLE_HEADER:
    #     table.add_column(col)
    # 결과 테이블
    table = Table(title="VPC + TGW Tag Validation", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("VPC/TGW", style="cyan")
    table.add_column("Resource")
    table.add_column("ResourceID")
    table.add_column("Validation Results", style="red")
    # Slack 데이터 (축소 열)
    slack_data = []

    found_issues = False

    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles.get(acct)
            if not profile_name:
                log_info(f"Account {acct} not found in profiles")
                continue
            for reg in regions:
                futures.append(
                    executor.submit(check_vpc_and_tgw_tags, acct, profile_name, reg)
                )

        for fut in as_completed(futures):
            try:
                res = fut.result()
                if not res:
                    continue

                rows_full = res["rows_full"]
                rows_slack = res["rows_slack"]

                if rows_full or rows_slack:
                    found_issues = True
                    # 콘솔 테이블
                    for row_f in rows_full:
                        table.add_row(*row_f)
                    # Slack
                    slack_data.extend(rows_slack)
            except Exception as e:
                log_exception(e)

    if found_issues:
        log_info("VPC + TGW 태그 검사 결과 (이슈 있음):")
        console.print(table)

        # Slack 전송
        send_slack_blocks_table_with_color(
            "VPC+TGW 태그 검사 결과(축소)",
            SLACK_HEADER,
            slack_data
        )
    else:
        log_info("모든 VPC+TGW 관련 태그가 유효합니다.")
        minimal = [["-", "-", "-", "All Good!"]]
        send_slack_blocks_table_with_color("VPC+TGW 태그 검사 결과(축소)", SLACK_HEADER, minimal)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='특정 AWS 계정 (,) (없으면 .env 로드)')
    parser.add_argument('-r', '--regions', help='특정 리전 (,) (없으면 .env 로드)')

def main(args):
    check_all_vpc_tags(args)