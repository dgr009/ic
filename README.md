# IC (Infra Resource Management CLI)

`IC`는 멀티 클라우드 환경의 인프라 리소스를 통합 관리할 수 있는 Python 기반 CLI 툴입니다. **리소스 수집, 태그 관리, 유효성 검사, 자동화**를 지원하며, 병렬 처리를 통해 빠른 성능을 제공합니다.

**지원 플랫폼:**
- **AWS**: EC2, ECS, EKS, Fargate, MSK, CodePipeline, LB, RDS, S3, VPC, VPN, Security Groups 등
- **OCI**: VM, LB, NSG, VCN, Volume, Object Storage, Policy, Cost 등  
- **Azure**: VM, VNet, AKS, Storage Account, NSG, Load Balancer, Container Instances
- **GCP**: Compute Engine, VPC Networks, GKE, Cloud Storage, Cloud SQL, Cloud Functions, Cloud Run, Load Balancing, Firewall Rules, Billing & Cost
- **Cloudflare**: DNS 레코드 관리
- **SSH**: 서버 상태 점검 및 자동 등록

---

## ⭐️ 주요 기능 요약

| 플랫폼 | 서비스 | 기능 요약 |
|---|---|---|
| **AWS** | EC2, ECS, EKS, Fargate, MSK, CodePipeline, LB, RDS, S3, VPC, VPN, SG, NAT | `info`로 리소스 상세 정보 조회, `list_tags`로 태그 조회, `tag_check`로 정규식 기반 태그 규칙 검사. ECS는 클러스터/서비스/태스크 정보, EKS는 클러스터/노드/파드/Fargate/애드온 정보, MSK는 Kafka 클러스터 정보, CodePipeline은 빌드/배포 상태 조회 |
| **OCI** | VM, LB, NSG, VCN, Volume, Object, Policy, Cost | `info`로 각 서비스의 자원 병렬 수집. `policy search`로 IAM 정책 검색. `cost usage/credit`로 비용 분석 |
| **Azure** | VM, VNet, AKS, Storage, NSG, LB, ACI | `info`로 리소스 정보 조회. JSON, YAML, Table, Tree 출력 형식 지원. 구독별 병렬 처리 |
| **GCP** | Compute Engine, VPC Networks, GKE, Cloud Storage, Cloud SQL, Cloud Functions, Cloud Run, Load Balancing, Firewall Rules, Billing | `info`로 리소스 정보 조회. MCP 서버 통합 지원으로 중앙화된 인증 및 데이터 처리. JSON, YAML, Table, Tree 출력 형식 지원. 프로젝트별 병렬 처리 |
| **Cloudflare** | DNS | `list_info`로 DNS 레코드 정보 수집 |
| **SSH** | Server Management | `info`로 병렬 접속 상태 검사 및 서버 정보 수집, `reg`으로 신규 서버 등록 |

---

## 📂 프로젝트 구조

```
ic/
├── ic/cli.py                         # CLI 진입점
├── common/                           # 공통 유틸, 로깅, Slack 연동
│   ├── utils.py                      # AWS 공통 유틸리티
│   ├── log.py                        # 로깅 시스템
│   ├── slack.py                      # Slack 연동
│   └── gather_env.py                 # 환경변수 수집
├── aws/                              # AWS 모듈
│   ├── ec2/   info.py, list_tags.py, tag_check.py
│   ├── ecs/   info.py, service.py, task.py    # ECS 클러스터/서비스/태스크
│   ├── eks/   info.py, nodes.py, pods.py, fargate.py, addons.py, update_config.py  # EKS 클러스터/노드/파드/Fargate/애드온/kubeconfig
│   ├── fargate/ info.py                        # [DEPRECATED] Fargate 프로파일/태스크
│   ├── msk/   info.py, broker.py              # MSK 클러스터/브로커 정보
│   ├── codepipeline/ build.py, deploy.py      # CodePipeline 상태
│   ├── lb/    info.py, list_tags.py, tag_check.py
│   ├── rds/   info.py, list_tags.py, tag_check.py
│   ├── s3/    info.py, list_tags.py, tag_check.py
│   ├── vpc/   info.py, list_tags.py, tag_check.py
│   ├── vpn/   info.py
│   ├── sg/    info.py                # Security Groups
│   └── nat/   list_tags.py, tag_check.py
├── oci_module/                       # OCI 모듈
│   ├── common/utils.py               # OCI 공통 유틸리티
│   ├── vm/info.py                    # VM 인스턴스
│   ├── lb/info.py                    # Load Balancer
│   ├── nsg/info.py                   # Network Security Groups
│   ├── vcn/info.py                   # Virtual Cloud Network
│   ├── volume/info.py                # Block/Boot Volume
│   ├── obj/info.py                   # Object Storage
│   ├── policy/info.py, search.py    # IAM Policy
│   └── cost/usage.py, credit.py     # 비용 분석
├── azure/                            # Azure 모듈
│   ├── vm/info.py                    # Virtual Machines
│   ├── vnet/info.py                  # Virtual Networks
│   ├── aks/info.py                   # Azure Kubernetes Service
│   ├── storage/info.py               # Storage Accounts
│   ├── nsg/info.py                   # Network Security Groups
│   ├── lb/info.py                    # Load Balancers
│   └── aci/info.py                   # Container Instances
├── gcp/                              # GCP 모듈
│   ├── compute/info.py               # Compute Engine 인스턴스
│   ├── vpc/info.py                   # VPC Networks 및 서브넷
│   ├── gke/info.py                   # Google Kubernetes Engine 클러스터
│   ├── storage/info.py               # Cloud Storage 버킷
│   ├── sql/info.py                   # Cloud SQL 인스턴스
│   ├── functions/info.py             # Cloud Functions
│   ├── run/info.py                   # Cloud Run 서비스
│   ├── lb/info.py                    # Load Balancing
│   ├── firewall/info.py              # Firewall Rules
│   └── billing/info.py               # Billing & Cost 정보
├── cf/                               # Cloudflare 모듈
│   └── dns/list_info.py
├── ssh/                              # SSH 모듈
│   ├── server_info.py                # 서버 상태 점검
│   └── auto_ssh.py                   # 자동 서버 등록
├── scripts/                          # 유틸리티 스크립트
└── logs/                             # 로그 파일 저장소
```

---

## 🚀 설치 및 실행

### 1. PyPI에서 설치 (권장)
```bash
# 기본 설치
pip install ic

# 개발 도구 포함 설치
pip install ic[dev]

# 보안 도구 포함 설치
pip install ic[security]

# 모든 옵션 포함 설치
pip install ic[dev,security,test]
```

### 2. 소스에서 설치 (개발용)
```bash
git clone https://github.com/dgr009/ic.git
cd ic
pip install -e .[dev]
```

### 3. 🔒 보안 설정 (중요!)

#### 초기 설정
```bash
# 보안 설정 초기화
ic config init

# 설정 검증
ic config validate
```

#### 환경변수 설정 (민감한 정보는 환경변수로만!)
```bash
# AWS 설정
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Azure 설정
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"

# GCP 설정
export GCP_SERVICE_ACCOUNT_KEY_PATH="/path/to/service-account.json"

# OCI 설정 (기본적으로 ~/.oci/config 사용)
export OCI_CONFIG_FILE="~/.oci/config"

# CloudFlare 설정
export CLOUDFLARE_EMAIL="your-email@example.com"
export CLOUDFLARE_API_TOKEN="your-api-token"
```

#### 설정 파일 (config.yaml) - 민감한 정보 제외
```yaml
# config.yaml - 민감한 정보는 포함하지 않음!
version: "1.0"
aws:
  accounts: ["123456789012", "987654321098"]
  regions: ["ap-northeast-2", "us-east-1"]
azure:
  subscriptions: ["your-subscription-id"]
  locations: ["Korea Central"]
gcp:
  projects: ["your-project-id"]
  regions: ["asia-northeast3"]
```

### 4. 🔐 보안 기능

#### 자동 보안 기능
- **민감한 데이터 마스킹**: 로그와 콘솔 출력에서 자동으로 민감한 정보 숨김
- **설정 파일 검증**: 민감한 정보가 설정 파일에 포함된 경우 경고
- **Git 보안 검사**: pre-commit 훅으로 민감한 정보 커밋 방지
- **환경변수 기반 인증**: 모든 민감한 정보는 환경변수로만 관리

#### 보안 명령어
```bash
# 설정 보안 검사
ic config security-check

# 민감한 데이터 마스킹된 설정 보기
ic config show --mask-sensitive

# .env에서 YAML로 안전하게 마이그레이션
ic config migrate
```

### 5. MCP 서버 설정 (GCP 권장)
GCP 서비스의 경우 MCP (Model Context Protocol) 서버를 통한 중앙화된 관리를 권장합니다:

```bash
# MCP 서버 활성화
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp

# MCP 서버 인증 방식
MCP_GCP_AUTH_METHOD=service_account  # 또는 adc, gcloud
```

**MCP 서버 장점:**
- 중앙화된 인증 및 자격 증명 관리
- 표준화된 데이터 변환 및 캐싱
- 향상된 보안성과 접근 제어
- 통합된 오류 처리 및 재시도 로직
- 크로스 플랫폼 일관성

### ⚠️ 보안 주의사항

#### 절대 하지 말아야 할 것들:
- ❌ 설정 파일에 API 키, 패스워드, 토큰 저장
- ❌ Git에 실제 설정 파일 (config.yaml) 커밋
- ❌ 로그 파일을 공개 저장소에 업로드
- ❌ 민감한 정보를 명령행 인수로 전달

#### 반드시 해야 할 것들:
- ✅ 모든 민감한 정보는 환경변수로 관리
- ✅ 설정 파일 권한을 600으로 설정 (`chmod 600 config.yaml`)
- ✅ .gitignore에 민감한 파일 패턴 추가
- ✅ 정기적으로 보안 업데이트 적용

---

## 🔧 명령어 · 옵션 총정리

> 모든 옵션을 생략하면 `.env` 파일의 기본값이 사용됩니다.  
> 커맨드 라인 옵션으로 입력 시 `.env` 값을 덮어쓸 수 있으며, 쉼표(`,`)로 다중 입력이 가능합니다.

### 1) AWS

1. **AWS CLI, IAM-Auth 설치**  
   macOS(hombrew): `brew install awscli` , `brew install aws-iam-authenticator`

2. **자격 증명 파일 구성**  
   - `~/.aws/credentials`
     ```ini
     [dev]
     aws_access_key_id = AKIAxxxxxxxxxxxxxxxx
     aws_secret_access_key = yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy

     [prod]
     aws_access_key_id = AKIAzzzzzzzzzzzzzzzz
     aws_secret_access_key = wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww
     ```
   - `~/.aws/config`
     ```ini
     [profile dev]
     region = ap-northeast-2
     output = json

     [profile prod]
     region = ap-northeast-1
     output = json
     ```
   - **AssumeRole(OrganizationAccountAccessRole) 예시**
     ```ini
     [profile finops-master]
     region = ap-northeast-2
     output = json

     [profile prod]
     role_arn = arn:aws:iam::222222222222:role/OrganizationAccountAccessRole
     source_profile = finops-master
     region = ap-northeast-1
     output = json
     ```
     `common.utils.get_profiles()` 함수는 `role_arn` 을 읽어 `222222222222 → prod` 로 매핑하므로, 계정 ID 만 `.env` 의 `AWS_ACCOUNTS` 에 넣어두면 자동으로 해당 프로파일이 사용됩니다.

3. **추가 환경변수 요약**
   | 변수 | 설명 | 예시 |
   |------|------|------|
   | `REGIONS` | 기본 조회 리전(콤마) | `ap-northeast-1,ap-northeast-2` |
   | `REQUIRED_TAGS` / `OPTIONAL_TAGS` | 태그 필수·선택 항목 | `User,Team,Environment` |
   | `RULE_*` | 태그 별 정규식 | `RULE_ENVIRONMENT=^(PROD|STG|DEV)$` |

4. **명령어 요약**

   | Service | Subcommand | 주요 옵션 | 설명 |
   |---|---|---|---|
   | `ec2` | `info` | `-v`, `--name`, `-a`, `--account`, `-r`, `--region` | EC2 인스턴스 정보 조회 (상세 옵션 제공) |
   | `ecs` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | ECS 클러스터 종합 정보 (서비스 수, 태스크 상태별 개수, 컨테이너 인스턴스 수) |
   | `ecs` | `service` | `--cluster`, `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | ECS 서비스 상세 정보 (태스크 정의, 로드 밸런서, 실행 상태) |
   | `ecs` | `task` | `--cluster`, `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | ECS 태스크 상세 정보 (컨테이너 상태, 네트워크 정보, 리소스 할당) |
   | `eks` | `info` | `-c`, `--cluster`, `-a`, `--account`, `-r`, `--region`, `--output` | EKS 클러스터 정보 (컨트롤 플레인, 네트워킹, API 서버 접근, 관리형 노드 그룹) |
   | `eks` | `nodes` | `-c`, `--cluster`, `-a`, `--account`, `-r`, `--region`, `--output` | EKS 노드 정보 (노드그룹 상태, 인스턴스 타입, 스케일링 설정, EC2 인스턴스 상세) |
   | `eks` | `pods` | `-c`, `--cluster`, `-n`, `--namespace`, `-a`, `--account`, `-r`, `--region`, `--output` | EKS 파드 정보 (파드 상태, 컨테이너 정보, 리소스 사용량, 네임스페이스별 통계) |
   | `eks` | `fargate` | `-c`, `--cluster`, `-a`, `--account`, `-r`, `--region`, `--output` | EKS Fargate 프로파일 정보 (Pod 실행 역할, 서브넷, 셀렉터 규칙) |
   | `eks` | `addons` | `-c`, `--cluster`, `-a`, `--account`, `-r`, `--region`, `--output` | EKS 애드온 정보 (VPC CNI, CoreDNS, kube-proxy 등 상태 및 버전) |
   | `eks` | `update-config` | `-n`, `--name`, `-a`, `--account`, `--region` | EKS kubeconfig 업데이트 (클러스터 검색 및 선택, 로컬 kubectl 설정) |
   | `msk` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | MSK 클러스터 정보 (Kafka 버전, 브로커 수, 암호화 설정, 모니터링 상태) |
   | `msk` | `broker` | `-c`, `--cluster`, `-a`, `--account`, `-r`, `--region`, `--output` | MSK 브로커 엔드포인트 정보 (연결 타입별 엔드포인트, 포트, 인증 방식) |
   | `fargate` | `info` | `--cluster-name`, `--type`, `-a`, `--account`, `-r`, `--region`, `--output` | [DEPRECATED] Fargate 정보 - `ic aws eks fargate` 또는 `ic aws eks pods` 사용 권장 |
   | `code` | `build` | `pipeline_name`, `-a`, `--account`, `-r`, `--region`, `--output` | CodePipeline 빌드 스테이지 상태 조회 |
   | `code` | `deploy` | `pipeline_name`, `-a`, `--account`, `-r`, `--region`, `--output` | CodePipeline 배포 스테이지 상태 조회 |
   | `lb` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`| 로드 밸런서 상세 정보 조회 |
   | `rds` | `info` | `--name`, `-a`, `--account`, `-r`, `--region` | RDS 인스턴스 및 클러스터 정보 조회 |
   | `s3` | `info` | `--name` | S3 버킷 상세 정보 조회 |
   | `vpc` | `info` | `--name` | VPC, 서브넷, 라우팅 테이블 정보 조회 |
   | `vpn` | `info` | | TGW, VGW, VPN 연결, 엔드포인트 정보 조회 |
   | `sg` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | Security Group 인바운드 규칙 조회 (테이블/트리) |
   | `nat` | `list_tags`, `tag_check` | | NAT Gateway 태그 관리 |
   | `*` | `list_tags`| | 각 서비스의 태그 정보 조회 |
   | `*` | `tag_check`| | 각 서비스의 태그 규칙 준수 여부 검사 |

### 2) OCI
| Service | Subcommand | 주요 옵션 | 설명 |
|---|---|---|---|
| `vm` | `info` | `-v`, `--name`, `--compartment`, `--regions`, `--output` | VM 인스턴스 정보 조회 (상세 옵션 제공) |
| `lb` | `info` | `--name`, `--compartment`, `--regions`, `--output` | 로드 밸런서 정보 조회 (테이블/트리) |
| `nsg`| `info` | `--name`, `--compartment`, `--regions`, `--output` | NSG 인바운드 규칙 조회 (테이블/트리) |
| `vcn`| `info` | `--name`, `--compartment`, `--regions` | VCN, 서브넷, 라우팅 정보 조회 |
| `volume`| `info` | `--name`, `--compartment`, `--regions`, `--output` | Block/Boot Volume 정보 조회 |
| `obj`| `info` | `--name`, `--compartment`, `--regions`, `--output` | Object Storage 버킷 정보 조회 |
| `policy`| `info` | `--name`, `--compartment` | IAM 정책 목록 조회 |
| `policy`| `search` | `--user`, `--group` | 사용자/그룹 기준 IAM 정책 검색 |
| `cost`| `usage` | `--start-date`, `--end-date` | 비용 사용량 조회 |
| `cost`| `credit` | `--start-date`, `--end-date` | 크레딧 사용량 조회 |

### 3) Azure

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `vm` | `info` | `--subscription`, `--location`, `--resource-group`, `--name`, `--output` | Azure VM 정보 조회 | `ic azure vm info --name "my-vm" --output json` |
| `vnet` | `info` | `--subscription`, `--location`, `--resource-group`, `--name`, `--output` | Azure VNet 정보 조회 | `ic azure vnet info --resource-group "my-rg" --output tree` |
| `aks` | `info` | `--subscription`, `--location`, `--resource-group`, `--name`, `--output` | Azure AKS 클러스터 정보 조회 | `ic azure aks info --location "Korea Central"` |
| `storage` | `info` | `--subscription`, `--location`, `--resource-group`, `--name`, `--output` | Azure Storage Account 정보 조회 | `ic azure storage info --output yaml` |
| `nsg` | `info` | `--subscription`, `--location`, `--resource-group`, `--name`, `--output` | Azure NSG 정보 조회 | `ic azure nsg info --name "my-nsg"` |
| `lb` | `info` | `--subscription`, `--location`, `--resource-group`, `--name`, `--output` | Azure Load Balancer 정보 조회 | `ic azure lb info --resource-group "my-rg"` |
| `aci` | `info` | `--subscription`, `--location`, `--resource-group`, `--name`, `--output` | Azure Container Instances 정보 조회 | `ic azure aci info --output tree` |

### 4) GCP

**인증 설정:**
1. **Service Account Key**: `GCP_SERVICE_ACCOUNT_KEY` 또는 `GCP_SERVICE_ACCOUNT_KEY_PATH` 환경변수 설정
2. **Application Default Credentials**: `gcloud auth application-default login` 실행
3. **gcloud CLI**: `gcloud auth login` 실행 (개발용)
4. **MCP 서버**: 중앙화된 인증 관리 (권장)

**환경변수 설정:**
```bash
# 프로젝트 설정
GCP_PROJECTS=project-1,project-2,project-3
GCP_DEFAULT_PROJECT=my-default-project

# 지역 설정
GCP_REGIONS=us-central1,us-east1,asia-northeast1
GCP_ZONES=us-central1-a,us-central1-b

# MCP 서버 설정 (권장)
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp
```

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `compute` | `info` | `--name`, `--project`, `--zone`, `--output` | Compute Engine 인스턴스 정보 조회 | `ic gcp compute info --name "my-instance" --zone us-central1-a` |
| `vpc` | `info` | `--name`, `--project`, `--region`, `--output` | VPC Networks 및 서브넷 정보 조회 | `ic gcp vpc info --name "my-vpc" --region us-central1` |
| `gke` | `info` | `--cluster`, `--project`, `--location`, `--output` | Google Kubernetes Engine 클러스터 정보 조회 | `ic gcp gke info --cluster "prod-cluster" --location us-central1-a` |
| `storage` | `info` | `--bucket`, `--project`, `--output` | Cloud Storage 버킷 정보 조회 | `ic gcp storage info --bucket "my-bucket"` |
| `sql` | `info` | `--instance`, `--project`, `--output` | Cloud SQL 인스턴스 정보 조회 | `ic gcp sql info --instance "prod-db"` |
| `functions` | `info` | `--function`, `--project`, `--region`, `--output` | Cloud Functions 정보 조회 | `ic gcp functions info --function "my-function" --region us-central1` |
| `run` | `info` | `--service`, `--project`, `--region`, `--output` | Cloud Run 서비스 정보 조회 | `ic gcp run info --service "my-service" --region us-central1` |
| `lb` | `info` | `--lb-name`, `--project`, `--output` | Load Balancer 정보 조회 | `ic gcp lb info --lb-name "my-lb"` |
| `firewall` | `info` | `--rule-name`, `--project`, `--output` | Firewall Rules 정보 조회 | `ic gcp firewall info --rule-name "allow-http"` |
| `billing` | `info` | `--project`, `--start-date`, `--end-date`, `--output` | Billing 및 Cost 정보 조회 | `ic gcp billing info --start-date 2024-01-01 --end-date 2024-01-31` |

### 5) Cloudflare

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `dns` | `list_info`| `--name`, `--content` | DNS 레코드 조회 | `ic cf dns list_info --name "example.com"` |

### 6) SSH

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `info` | `(none)` | `--key`, `--host` | `~/.ssh/config` 서버 상태 스캔 | `ic ssh info --host "my-server"` |
| `reg`  | `(none)` | | 서버 스캔 후 SSH config 등록 | `ic ssh reg` |

---

## 🆕 새로 추가된 주요 기능

### AWS 컨테이너 및 스트리밍 서비스 통합 관리
- **ECS 종합 모니터링**: 클러스터별 서비스 수, 태스크 상태별 개수, 컨테이너 인스턴스 현황을 한눈에 파악
- **EKS 클러스터 관리**: 컨트롤 플레인, 네트워킹, API 서버 접근 설정, 관리형 노드 그룹 정보 통합 조회
- **Fargate 리소스 추적**: EKS Fargate 프로파일과 ECS Fargate 태스크를 구분하여 상세 정보 제공
- **MSK 클러스터 모니터링**: Apache Kafka 클러스터 상태, 브로커 수, Kafka 버전, 암호화 설정, Prometheus 모니터링 상태 통합 조회
- **MSK 브로커 엔드포인트 관리**: 연결 타입별 브로커 엔드포인트 조회 (PLAINTEXT, TLS, SASL/SCRAM, SASL/IAM, Public, VPC Connectivity)
- **CI/CD 파이프라인 모니터링**: CodePipeline의 빌드/배포 스테이지별 상태를 색상 코딩과 심볼로 직관적 표시

### 고급 필터링 및 출력 옵션
- **다중 형식 출력**: 테이블(기본), JSON, YAML 형식 지원으로 스크립팅 및 자동화 친화적
- **지능형 필터링**: 클러스터명, 서비스명, 태스크명 등 다양한 필터 옵션으로 원하는 정보만 선별 조회
- **병렬 처리**: 다중 계정/리전에 걸친 대규모 인프라도 빠른 속도로 정보 수집

---

## 🔒 보안 및 설정 관리

### 새로운 보안 중심 설정 시스템

IC 1.0.0부터는 보안을 최우선으로 하는 새로운 설정 시스템을 도입했습니다:

#### 주요 보안 기능
- **민감한 데이터 자동 마스킹**: 로그, 콘솔 출력에서 API 키, 패스워드 등 자동 숨김
- **설정 파일 보안 검증**: 민감한 정보가 설정 파일에 포함되면 경고
- **Git 보안 훅**: pre-commit 시 민감한 정보 커밋 방지
- **환경변수 기반 인증**: 모든 자격 증명은 환경변수로만 관리

#### 설정 시스템 개선
- **.env → YAML 전환**: 구조화된 설정 관리 (기존 .env 파일 호환성 유지)
- **설정 계층화**: 기본값 → 사용자 → 프로젝트 → 환경변수 순서로 적용
- **스키마 검증**: 설정 값의 타입과 형식 자동 검증
- **마이그레이션 도구**: 기존 .env 설정을 안전하게 YAML로 변환

#### 로깅 시스템 개선
- **이중 레벨 로깅**: 콘솔은 ERROR만, 파일은 전체 로그 기록
- **민감한 데이터 마스킹**: 모든 로그 출력에서 자동으로 민감한 정보 숨김
- **자동 로그 순환**: 날짜별 로그 파일 분할 및 자동 정리

### 마이그레이션 가이드

기존 .env 사용자를 위한 마이그레이션:

```bash
# 1. 기존 설정 백업
cp .env .env.backup

# 2. 새 설정 시스템으로 마이그레이션
ic config migrate

# 3. 마이그레이션 결과 확인
ic config validate

# 4. 보안 검사
ic config security-check
```

---

## 📊 주요 동작 방식

- **병렬 처리**: `ThreadPoolExecutor`를 사용하여 여러 계정과 리전에 걸쳐 리소스 정보를 병렬로 수집하여 빠른 속도를 보장합니다.
- **출력 형식**: `rich` 라이브러리를 활용하여 가독성 높은 테이블/트리 형식으로 결과를 출력합니다.
- **자격 증명**: 각 플랫폼의 표준 자격 증명 방식을 사용합니다:
  - AWS: `~/.aws/config`, `~/.aws/credentials`
  - OCI: `~/.oci/config`
  - GCP: Service Account Key, Application Default Credentials, gcloud CLI, MCP 서버 (권장)
  - Cloudflare: API Token 환경변수
- **환경 변수**: `.env` 파일을 통해 계정 정보, 기본 리전, 태그 규칙 등 설정을 중앙에서 관리합니다.
- **MCP 서버 통합**: Model Context Protocol 서버를 통한 중앙화된 인증 및 데이터 처리로 보안성과 일관성을 향상시킵니다.
- **멀티 서비스**: 쉼표(`,`)로 구분하여 여러 서비스를 동시에 실행할 수 있습니다. (예: `ic gcp compute,vpc,gke info`)
- **필터링**: 이름, 계정, 리전, 프로젝트, 존 등 다양한 필터 옵션을 제공합니다.

---

## 💬 Slack 알림 (선택)

- `.env`에 `SLACK_WEBHOOK_URL` 정의 시 사용
- 슬랙 함수:
  - `send_slack_message()`
  - `send_slack_blocks_table()` / `..._with_color()`
- 메시지 크기 초과(too_many_attachments) 방지 처리 포함
- `.env`에 `SLACK_WEBHOOK_URL`을 설정하면 `tag_check` 등의 검사 결과를 지정된 채널로 전송할 수 있습니다.
- 메시지 크기 제한을 초과할 경우, 요약 정보만 보내는 기능이 포함되어 있습니다.
---

## ⚠️ 유의 사항

- **AWS**: S3는 리전 간 API 제한 이슈 있음 → `IllegalLocationConstraintException` 처리 필요
- **OCI**: 구독된 리전만 조회 가능하며, 컴파트먼트 권한 확인 필요
- **Slack**: 413 Payload Too Large → 전송 건수 제한 필요
- **태그 규칙**: `RULE_XXX` 정규식은 `.env` 기반 + 코드 내부 정의와 병합되어 동작
- **SSH**: 기본적으로 `~/.ssh/config` 기반으로 등록된 서버들 조회
- **자격 증명**: 각 플랫폼별 CLI 도구 및 설정 파일이 사전에 구성되어 있어야 함
- **GCP MCP 통합**: GCP 서비스는 MCP 서버를 통한 중앙화된 관리를 우선 사용하며, 직접 API 접근을 대체 수단으로 지원

---

## 🚧 확장 가능성

- **태그 관리**: `apply_tags`, `backup_tags`, `excel_to_json` 등의 기능 추가 예정
- **IaC 통합**: Terraform / CloudFormation 태그 통합 지원
- **CI/CD 통합**: GitHub Actions / Jenkins 등과 통합하여 자동 검사 가능
- **Azure API 연동**: Azure Mock 모듈을 실제 API 연동으로 전환 예정
- **추가 서비스**: 각 플랫폼별 더 많은 서비스 지원 (Lambda, Functions, Storage 등)
- **리포팅**: Excel, CSV, JSON 등 다양한 형식의 리포트 생성 기능
- **모니터링**: 리소스 변경 사항 추적 및 알림 기능
- **컨테이너 오케스트레이션**: ECS/EKS 클러스터 자동 스케일링 및 배포 관리
- **CI/CD 통합**: CodePipeline, GitHub Actions, Jenkins 등과의 깊은 통합

---

## � 사용 예시/

### AWS 리소스 조회
```bash
# EC2 인스턴스 정보 조회
ic aws ec2 info

# ECS 클러스터 종합 현황
ic aws ecs info

# 특정 ECS 클러스터의 서비스 조회
ic aws ecs service --cluster production-cluster

# ECS 태스크 상세 정보 조회
ic aws ecs task --cluster production-cluster --name web-service

# MSK 클러스터 정보 조회
ic aws msk info

# 특정 MSK 클러스터 필터링
ic aws msk info --name kafka-prod

# MSK 브로커 엔드포인트 정보 조회
ic aws msk broker

# 특정 클러스터의 브로커 엔드포인트 조회
ic aws msk broker --cluster kafka-prod

# EKS 클러스터 정보 조회
ic aws eks info

# EKS 노드 정보 조회
ic aws eks nodes

# EKS 파드 정보 조회 (실시간 워크로드 상태)
ic aws eks pods

# 특정 클러스터의 파드 정보
ic aws eks pods --cluster production

# 특정 네임스페이스의 파드 정보
ic aws eks pods --namespace kube-system

# EKS Fargate 프로파일 조회
ic aws eks fargate

# EKS 애드온 정보 조회
ic aws eks addons

# EKS kubeconfig 업데이트 (클러스터 검색 및 선택)
ic aws eks update-config --name production

# 다른 리전의 클러스터 검색
ic aws eks update-config --name dev --region us-west-2

# [DEPRECATED] 기존 Fargate 명령어 (EKS로 이전됨)
# ic aws fargate info --cluster-name my-eks-cluster

# CodePipeline 빌드/배포 상태 확인
ic aws code build my-app-pipeline
ic aws code deploy my-app-pipeline

# 특정 계정의 Security Group 조회 (트리 형식)
ic aws sg info --account 123456789012 --output tree

# 여러 서비스 동시 조회
ic aws ec2,lb,rds info --regions ap-northeast-2

# 태그 규칙 검사
ic aws ec2 tag_check --account prod
```

### OCI 리소스 조회
```bash
# VM 인스턴스 정보 조회 (상세 모드)
ic oci vm info -v --compartment production

# NSG 규칙 조회 (트리 형식)
ic oci nsg info --output tree --regions ap-seoul-1

# 여러 서비스 동시 조회
ic oci vm,lb,nsg,volume info --compartment dev

# 비용 분석
ic oci cost usage --start-date 2024-01-01 --end-date 2024-01-31
```

### 기타 플랫폼
```bash
# SSH 서버 상태 점검
ic ssh info --host production

# Cloudflare DNS 레코드 조회
ic cf dns list_info --name example.com

# Azure 리소스 조회
ic azure vm info --name my-vm --resource-group rg-prod --output table
ic azure vnet info --location "Korea Central" --output tree
ic azure aks info --subscription my-subscription --output json
ic azure storage info --resource-group rg-storage --output yaml
ic azure nsg info --name my-nsg --output tree
ic azure lb info --location "East US" --output table
ic azure aci info --resource-group rg-containers --output tree

# 여러 Azure 서비스 동시 조회
ic azure vm,vnet,aks,storage info --resource-group rg-prod

# GCP 리소스 조회
# Compute Engine 인스턴스 조회
ic gcp compute info

# 특정 프로젝트의 인스턴스 조회
ic gcp compute info --project my-project

# 특정 존의 인스턴스 필터링
ic gcp compute info --zone us-central1-a --name web-server

# VPC Networks 및 서브넷 조회
ic gcp vpc info

# 특정 리전의 VPC 조회
ic gcp vpc info --region us-central1 --name production-vpc

# GKE 클러스터 정보 조회
ic gcp gke info

# 특정 클러스터 상세 정보
ic gcp gke info --cluster production --location us-central1-a

# Cloud Storage 버킷 조회
ic gcp storage info

# 특정 버킷 정보
ic gcp storage info --bucket my-data-bucket

# Cloud SQL 인스턴스 조회
ic gcp sql info

# 특정 인스턴스 상세 정보
ic gcp sql info --instance prod-database

# Cloud Functions 조회
ic gcp functions info

# 특정 리전의 함수 조회
ic gcp functions info --region us-central1 --function my-function

# Cloud Run 서비스 조회
ic gcp run info

# 특정 서비스 상세 정보
ic gcp run info --service my-api --region us-central1

# Load Balancer 조회
ic gcp lb info

# 특정 로드밸런서 정보
ic gcp lb info --lb-name production-lb

# Firewall Rules 조회
ic gcp firewall info

# 특정 규칙 조회
ic gcp firewall info --rule-name allow-https

# Billing 정보 조회
ic gcp billing info

# 특정 기간 비용 조회
ic gcp billing info --start-date 2024-01-01 --end-date 2024-01-31

# 여러 GCP 서비스 동시 조회
ic gcp compute,vpc,gke info --project production

# 다양한 출력 형식 사용
ic gcp compute info --output json
ic gcp vpc info --output yaml
ic gcp gke info --output tree
ic gcp storage info --output table

# 다중 프로젝트 조회
ic gcp compute info --project project-1,project-2,project-3

# MCP 서버를 통한 중앙화된 조회 (자동 감지)
ic gcp compute,vpc,gke,storage,sql info --output tree
```

---

## 📅 유지보수 / 문의

- Maintainer: **SangYun Kim** (cruiser594@gmail.com)
- License: MIT

