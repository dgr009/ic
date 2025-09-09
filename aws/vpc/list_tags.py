import os
import botocore
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from common.log import log_info, log_error, log_exception, log_decorator
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

# 새로운 설정 시스템에서 태그 키 가져오기
def get_tag_keys():
    """설정에서 태그 키를 가져옵니다."""
    if config and 'aws' in config and 'tags' in config['aws']:
        aws_tags = config['aws']['tags']
        required_tags = aws_tags.get('required', ['User', 'Team', 'Environment'])
        optional_tags = aws_tags.get('optional', ['Service', 'Application'])
    else:
        # Fallback to environment variables
        env_required = os.getenv("REQUIRED_TAGS", "User,Team,Environment")
        env_optional = os.getenv("OPTIONAL_TAGS", "Service,Application")
        required_tags = [t.strip() for t in env_required.split(",") if t.strip()]
        optional_tags = [t.strip() for t in env_optional.split(",") if t.strip()]
    
    return required_tags + optional_tags

TAG_KEYS = get_tag_keys()

@log_decorator
def fetch_vpc_and_tgw_tags(account_id, profile_name, region):
    """
    1) vpc_dict[vpc_id] = [ row_for_vpc, row_for_igw, row_for_nat, row_for_vgw,
                            row_for_peer, row_for_s2s, row_for_endpoint, ... ]
       (기본 VPC 제외)
    2) tgw_dict[tgw_id] = [ row_for_tgw_main, row_for_tgw_attach, ... ]
    """

    session = create_session(profile_name, region)
    if not session:
        log_error(f"Session creation failed for account {account_id} in region {region}")
        return {"vpc_dict": {}, "tgw_dict": {}}

    ec2 = session.client("ec2", region_name=region)

    vpc_dict = defaultdict(list)
    tgw_dict = defaultdict(list)

    # -------------- 1) VPC (exclude default) --------------
    try:
        vpcs_resp = ec2.describe_vpcs()
        for v in vpcs_resp.get("Vpcs", []):
            if v.get("IsDefault"):
                continue
            vpc_id = v["VpcId"]
            vtags = {t["Key"]: t["Value"] for t in v.get("Tags", [])}

            # VPC 행 => (VPC, "-")
            row_data = [account_id, region, vpc_id, "VPC", "-"]
            for tk in TAG_KEYS:
                row_data.append(vtags.get(tk, "-"))
            vpc_dict[vpc_id].append(row_data)

    except Exception as e:
        log_exception(e)
        log_error(f"Error describing VPCs in {account_id}/{region}")

    # -------------- 2) IGW --------------
    try:
        igw_resp = ec2.describe_internet_gateways()
        for igw in igw_resp.get("InternetGateways", []):
            igw_id = igw["InternetGatewayId"]
            igw_tags = {t["Key"]: t["Value"] for t in igw.get("Tags", [])}

            for attach in igw.get("Attachments", []):
                vpc_id = attach.get("VpcId")
                if not vpc_id or vpc_id not in vpc_dict:
                    continue

                row_data = [account_id, region, vpc_id, "IGW", igw_id]
                for tk in TAG_KEYS:
                    row_data.append(igw_tags.get(tk, "-"))
                vpc_dict[vpc_id].append(row_data)
    except Exception as e:
        log_exception(e)

    # -------------- 3) NAT Gateway (NGW) --------------
    try:
        nat_resp = ec2.describe_nat_gateways()
        for nat in nat_resp.get("NatGateways", []):
            nat_id = nat["NatGatewayId"]
            vpc_id = nat.get("VpcId")
            if not vpc_id or vpc_id not in vpc_dict:
                continue
            nat_tags = {t["Key"]: t["Value"] for t in nat.get("Tags", [])}

            row_data = [account_id, region, vpc_id, "NGW", nat_id]
            for tk in TAG_KEYS:
                row_data.append(nat_tags.get(tk, "-"))
            vpc_dict[vpc_id].append(row_data)
    except Exception as e:
        log_exception(e)

    # -------------- 4) VGW --------------
    try:
        vgw_resp = ec2.describe_vpn_gateways()
        for vgw in vgw_resp.get("VpnGateways", []):
            vgw_id = vgw["VpnGatewayId"]
            vgw_tags = {t["Key"]: t["Value"] for t in vgw.get("Tags", [])}
            for attach in vgw.get("VpcAttachments", []):
                v_id = attach.get("VpcId")
                if not v_id or v_id not in vpc_dict:
                    continue

                row_data = [account_id, region, v_id, "VGW", vgw_id]
                for tk in TAG_KEYS:
                    row_data.append(vgw_tags.get(tk, "-"))
                vpc_dict[v_id].append(row_data)
    except Exception as e:
        log_exception(e)

    # -------------- 5) VPC Peering => "Peer" --------------
    try:
        peer_resp = ec2.describe_vpc_peering_connections()
        for pcx in peer_resp.get("VpcPeeringConnections", []):
            pcx_id = pcx["VpcPeeringConnectionId"]
            pcx_tags = {t["Key"]: t["Value"] for t in pcx.get("Tags", [])}

            # requester
            req_vpc = pcx["RequesterVpcInfo"].get("VpcId")
            if req_vpc and req_vpc in vpc_dict:
                row_data = [account_id, region, req_vpc, "Peer", pcx_id]
                for tk in TAG_KEYS:
                    row_data.append(pcx_tags.get(tk, "-"))
                vpc_dict[req_vpc].append(row_data)

            # accepter
            acc_vpc = pcx["AccepterVpcInfo"].get("VpcId")
            if acc_vpc and acc_vpc in vpc_dict:
                row_data = [account_id, region, acc_vpc, "Peer", pcx_id]
                for tk in TAG_KEYS:
                    row_data.append(pcx_tags.get(tk, "-"))
                vpc_dict[acc_vpc].append(row_data)
    except Exception as e:
        log_exception(e)

    # -------------- 6) Site-to-Site => "s2s" --------------
    try:
        vpn_conn_resp = ec2.describe_vpn_connections()
        for vpn_conn in vpn_conn_resp.get("VpnConnections", []):
            vpn_id = vpn_conn["VpnConnectionId"]
            vgw_id = vpn_conn.get("VpnGatewayId")
            if not vgw_id:
                continue

            vpn_tags = {t["Key"]: t["Value"] for t in vpn_conn.get("Tags", [])}

            # re-describe the VGW to find attached VPC
            try:
                single_vgw = ec2.describe_vpn_gateways(VpnGatewayIds=[vgw_id])["VpnGateways"][0]
                attachments = single_vgw.get("VpcAttachments", [])
                for att in attachments:
                    v_id = att.get("VpcId")
                    if v_id and v_id in vpc_dict:
                        row_data = [account_id, region, v_id, "s2s", vpn_id]
                        for tk in TAG_KEYS:
                            row_data.append(vpn_tags.get(tk, "-"))
                        vpc_dict[v_id].append(row_data)
            except Exception as e2:
                log_exception(e2)
    except Exception as e:
        log_exception(e)

    # -------------- 7) VPC Endpoint => "ENDPOINT" --------------
    try:
        vpce_resp = ec2.describe_vpc_endpoints()
        for ep in vpce_resp.get("VpcEndpoints", []):
            ep_id = ep["VpcEndpointId"]
            v_id = ep.get("VpcId")
            if not v_id or v_id not in vpc_dict:
                continue

            ep_tags = {t["Key"]: t["Value"] for t in ep.get("Tags", [])}

            row_data = [account_id, region, v_id, "ENDPOINT", ep_id]
            for tk in TAG_KEYS:
                row_data.append(ep_tags.get(tk, "-"))
            vpc_dict[v_id].append(row_data)
    except Exception as e:
        log_exception(e)

    # -------------- 8) TGW 본체 => "TGW" --------------
    tgw_dict_local = {}  # collect in-case we do multi calls
    try:
        tgw_resp = ec2.describe_transit_gateways()
        for tgw in tgw_resp.get("TransitGateways", []):
            tgw_id = tgw["TransitGatewayId"]
            tgw_tags = {t["Key"]: t["Value"] for t in tgw.get("Tags", [])}

            row_data = [account_id, region, "-", "TGW", tgw_id]
            for tk in TAG_KEYS:
                row_data.append(tgw_tags.get(tk, "-"))
            tgw_dict[tgw_id].append(row_data)
            tgw_dict_local[tgw_id] = True
    except Exception as e:
        log_exception(e)

    # -------------- 9) TGW Attach(VPC) => "tgw-attach" --------------
    try:
        tgw_attach_resp = ec2.describe_transit_gateway_attachments()
        for attach in tgw_attach_resp.get("TransitGatewayAttachments", []):
            tgw_id = attach["TransitGatewayId"]
            attach_id = attach["TransitGatewayAttachmentId"]
            attach_tags = {t["Key"]: t["Value"] for t in attach.get("Tags", [])}
            row_data = [account_id, region, tgw_id, "tgw-attach", attach_id]
            for tk in TAG_KEYS:
                row_data.append(attach_tags.get(tk, "-"))
            tgw_dict[tgw_id].append(row_data)
    except Exception as e:
        log_exception(e)

    return {"vpc_dict": dict(vpc_dict), "tgw_dict": dict(tgw_dict)}

@log_decorator
def list_vpc_tags(args):
    """
    최종:
      1) vpc_dict[vpc_id] => (VPC, IGW, NGW, VGW, Peer, s2s, ENDPOINT, etc.)
      2) tgw_dict[tgw_id] => (TGW, tgw-attach)
    """
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles = get_profiles()

    table = Table(title="VPC + TGW Tags (Peering, s2s, Endpoint)", show_header=True, header_style="bold magenta")
    table.add_column("Account", style="green")
    table.add_column("Region", style="blue")
    table.add_column("VPC/TGW", style="cyan")
    table.add_column("Resource")  # VPC, IGW, NGW, VGW, Peer, s2s, ENDPOINT, TGW, tgw-attach
    table.add_column("ResourceID")      # ID or "-"

    for tk in TAG_KEYS:
        table.add_column(tk)

    final_rows = []

    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles.get(acct)
            if not profile_name:
                log_info(f"Account {acct} not found in profiles")
                continue
            for reg in regions:
                futures.append(
                    executor.submit(fetch_vpc_and_tgw_tags, acct, profile_name, reg)
                )

        for fut in as_completed(futures):
            try:
                res = fut.result()
                if not res:
                    continue
                vpc_dict = res.get("vpc_dict", {})
                tgw_dict = res.get("tgw_dict", {})

                # VPC쪽
                for vpc_id in sorted(vpc_dict.keys()):
                    final_rows.extend(vpc_dict[vpc_id])

                # TGW쪽
                for tgw_id in sorted(tgw_dict.keys()):
                    final_rows.extend(tgw_dict[tgw_id])

            except Exception as e:
                log_exception(e)

    for row in final_rows:
        table.add_row(*row)

    log_info("VPC + TGW 태그 조회 결과 (with Endpoint):")
    console.print(table)

def add_arguments(parser):
    parser.add_argument('-a', '--account', help='조회할 AWS 계정 (,) (없으면 .env 로드)')
    parser.add_argument('-r', '--regions', help='조회할 리전 (,) (없으면 .env 로드)')

def main(args):
    list_vpc_tags(args)