import os

def gather_env_for_command(platform, service, command):
    """
    특정 플랫폼/서비스/커맨드에서 실제로 사용하는 .env 변수만 골라 dict로 반환.
    command(= subcommand)도 고려해서, 필요한 env만 선택적으로 표시할 수 있음.
    """
    env_dict = {}
    
    # -----------------------------------
    # Cloudflare (cf)
    # -----------------------------------
    if platform == "cf":
        if service == "dns":
            # Cloudflare DNS 명령들(list_info 등)에서 사용하는 env
            # (사용 중인 항목만 추려서 나열)
            relevant_keys = [
                "CLOUDFLARE_EMAIL",
                "CLOUDFLARE_API_TOKEN",
                "CLOUDFLARE_ACCOUNTS",
                "CLOUDFLARE_ZONES",
                "SLACK_WEBHOOK_URL",         # (Slack 알림 쓰면)
                "LOG_LEVEL",                 # (원하면 로깅레벨도 함께)
            ]
            for k in relevant_keys:
                val = os.getenv(k)
                if val:
                    env_dict[k] = val

    # -----------------------------------
    # AWS
    # -----------------------------------
    elif platform == "aws":
        # 예: EC2, LB, NAT, RDS, S3, VPC 등 공통으로 쓰이는 env
        # command가 "ec2", "lb", "nat", "rds" ... 등에 따라 세분화 가능
        relevant_keys = [
            "AWS_ACCOUNTS",       # 여러 계정 ID 콤마구분 (111111111111,222222222222)
            "REGIONS",            # ex) ap-northeast-1,ap-northeast-2
            "REQUIRED_TAGS",      # 태그 필수 항목, ex) User,Team,Environment
            "OPTIONAL_TAGS",      # 태그 선택 항목, ex) Service,Application
            "LOG_LEVEL",
            "SLACK_WEBHOOK_URL",  # 만약 태그 검사 시 Slack 전송에 쓰인다면
        ]
        # command(=service) 세분화할 수도 있음
        # 예: if service=="ec2": relevant_keys.append("EC2_SOMETHING") ...
        for k in relevant_keys:
            val = os.getenv(k)
            if val:
                env_dict[k] = val

    # -----------------------------------
    # OCI
    # -----------------------------------
    elif platform == "oci":
        if service == "info":
            # oci_info.py에서 사용될 수 있는 env
            relevant_keys = [
                "OCI_TENANCY_OCID",    # 예: OCI에서 tenancy OCID
                "OCI_USER_OCID",
                "OCI_KEY_FILE",        # API 서명용 private key 경로
                "OCI_FINGERPRINT",     # key fingerprint
                "OCI_REGION",          # ex) ap-seoul-1
                "LOG_LEVEL",
            ]
        elif service == "search":
            # policy_search.py에서 사용될 수 있는 env
            relevant_keys = [
                "OCI_CONFIG_PATH",     # ~/.oci/config 경로
                "OCI_TENANCY_OCID",    # tenancy OCID
                "OCI_USER_OCID",       # user OCID
                "OCI_KEY_FILE",        # API 서명용 private key 경로
                "OCI_FINGERPRINT",     # key fingerprint
                "OCI_REGION",          # region
                "SHOW_EMPTY_COMPARTMENTS",  # 빈 컴파트먼트 표시 여부
                "LOG_LEVEL",
            ]
        else:
            # 기본 OCI 환경변수
            relevant_keys = [
                "OCI_TENANCY_OCID",
                "OCI_USER_OCID", 
                "OCI_KEY_FILE",
                "OCI_FINGERPRINT",
                "OCI_REGION",
                "LOG_LEVEL",
            ]
        
        for k in relevant_keys:
            val = os.getenv(k)
            if val:
                env_dict[k] = val

    # -----------------------------------
    # SSH
    # -----------------------------------
    elif platform == "ssh":
        # auto_ssh.py, server_info.py 등에 사용
        relevant_keys = [
            "SSH_CONFIG_FILE",     # ~/.ssh/config 경로 (커스텀일 수 있음)
            "SSH_KEY_DIR",         # 기본 키파일 디렉토리
            "SSH_MAX_WORKER",      # 병렬 스캔 스레드 수
            "PORT_OPEN_TIMEOUT",   # 포트스캔 timeout
            "SSH_TIMEOUT",         # SSH 접속 timeout
            "LOG_LEVEL",
        ]
        for k in relevant_keys:
            val = os.getenv(k)
            if val:
                env_dict[k] = val

    # -----------------------------------
    # 기타 플랫폼이면 pass
    # -----------------------------------
    
    return env_dict

