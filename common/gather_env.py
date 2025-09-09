import os

# 새로운 설정 시스템 import
try:
    from ic.config.manager import ConfigManager
    config_manager = ConfigManager()
    config = config_manager.get_config()
    USE_NEW_CONFIG = True
except ImportError:
    # 호환성을 위한 fallback
    config = {}
    USE_NEW_CONFIG = False

def gather_env_for_command(platform, service, command):
    """
    특정 플랫폼/서비스/커맨드에서 실제로 사용하는 설정 변수만 골라 dict로 반환.
    새로운 설정 시스템을 우선 사용하고, 없으면 환경변수로 fallback.
    """
    env_dict = {}
    
    # -----------------------------------
    # Cloudflare (cf)
    # -----------------------------------
    if platform == "cf":
        if service == "dns":
            if USE_NEW_CONFIG and 'cloudflare' in config:
                cf_config = config['cloudflare']
                env_dict.update({
                    "CLOUDFLARE_EMAIL": cf_config.get('email', ''),
                    "CLOUDFLARE_API_TOKEN": cf_config.get('api_token', ''),
                    "CLOUDFLARE_ACCOUNTS": ','.join(cf_config.get('accounts', [])),
                    "CLOUDFLARE_ZONES": ','.join(cf_config.get('zones', [])),
                })
                if 'slack' in config:
                    env_dict["SLACK_WEBHOOK_URL"] = config['slack'].get('webhook_url', '')
                if 'logging' in config:
                    env_dict["LOG_LEVEL"] = config['logging'].get('console_level', 'INFO')
            else:
                # Fallback to environment variables
                relevant_keys = [
                    "CLOUDFLARE_EMAIL",
                    "CLOUDFLARE_API_TOKEN", 
                    "CLOUDFLARE_ACCOUNTS",
                    "CLOUDFLARE_ZONES",
                    "SLACK_WEBHOOK_URL",
                    "LOG_LEVEL",
                ]
                for k in relevant_keys:
                    val = os.getenv(k)
                    if val:
                        env_dict[k] = val

    # -----------------------------------
    # AWS
    # -----------------------------------
    elif platform == "aws":
        if USE_NEW_CONFIG and 'aws' in config:
            aws_config = config['aws']
            env_dict.update({
                "AWS_ACCOUNTS": ','.join(aws_config.get('accounts', [])),
                "REGIONS": ','.join(aws_config.get('regions', ['ap-northeast-2'])),
            })
            
            # 태그 설정
            if 'tags' in aws_config:
                tags_config = aws_config['tags']
                env_dict.update({
                    "REQUIRED_TAGS": ','.join(tags_config.get('required', ['User', 'Team', 'Environment'])),
                    "OPTIONAL_TAGS": ','.join(tags_config.get('optional', ['Service', 'Application'])),
                })
            
            # 공통 설정
            if 'logging' in config:
                env_dict["LOG_LEVEL"] = config['logging'].get('console_level', 'INFO')
            if 'slack' in config:
                env_dict["SLACK_WEBHOOK_URL"] = config['slack'].get('webhook_url', '')
        else:
            # Fallback to environment variables
            relevant_keys = [
                "AWS_ACCOUNTS",
                "REGIONS",
                "REQUIRED_TAGS",
                "OPTIONAL_TAGS",
                "LOG_LEVEL",
                "SLACK_WEBHOOK_URL",
            ]
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
    # GCP
    # -----------------------------------
    elif platform == "gcp":
        # GCP 서비스들에서 공통으로 사용하는 환경변수
        relevant_keys = [
            # MCP Server Configuration (Primary)
            "MCP_GCP_ENABLED",
            "MCP_GCP_ENDPOINT", 
            "MCP_GCP_AUTH_METHOD",
            "GCP_PREFER_MCP",
            
            # Authentication (Fallback)
            "GCP_SERVICE_ACCOUNT_KEY_PATH",
            "GCP_SERVICE_ACCOUNT_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            
            # Project Configuration
            "GCP_PROJECTS",
            "GCP_DEFAULT_PROJECT",
            
            # Regional Configuration
            "GCP_REGIONS",
            "GCP_ZONES",
            
            # Performance Tuning
            "GCP_MAX_WORKERS",
            "GCP_REQUEST_TIMEOUT",
            "GCP_RETRY_ATTEMPTS",
            
            # Service-Specific Configuration
            "GCP_ENABLE_BILLING_API",
            "GCP_ENABLE_COMPUTE_API",
            "GCP_ENABLE_CONTAINER_API",
            "GCP_ENABLE_STORAGE_API",
            "GCP_ENABLE_SQLADMIN_API",
            "GCP_ENABLE_CLOUDFUNCTIONS_API",
            "GCP_ENABLE_RUN_API",
            
            # Common
            "LOG_LEVEL",
            "SLACK_WEBHOOK_URL",
        ]
        
        for k in relevant_keys:
            val = os.getenv(k)
            if val:
                env_dict[k] = val

    # -----------------------------------
    # Azure
    # -----------------------------------
    elif platform == "azure":
        # Azure 서비스들에서 공통으로 사용하는 환경변수
        relevant_keys = [
            "AZURE_TENANT_ID",
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "AZURE_SUBSCRIPTIONS",
            "AZURE_LOCATIONS",
            "LOG_LEVEL",
            "SLACK_WEBHOOK_URL",
        ]
        
        for k in relevant_keys:
            val = os.getenv(k)
            if val:
                env_dict[k] = val

    # -----------------------------------
    # 기타 플랫폼이면 pass
    # -----------------------------------
    
    return env_dict

