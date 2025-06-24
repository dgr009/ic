# IC (Infra Resource Management CLI)

`IC`는 AWS, OCI, Cloudflare, SSH 기반 인프라 리소스를 대상으로 **태그 관리, 리소스 수집, 유효성 검사, 자동화**를 수행할 수 있는 Python 기반 CLI 툴입니다.

- AWS 리소스 태그 확인/검사 (EC2, LB, RDS, S3, VPC, NAT 등)
- Cloudflare DNS 레코드 수집
- OCI 자원 및 비용 병렬 수집
- SSH 서버 상태 및 자동 등록 지원

---

## ⭐️ 주요 기능 요약

| 플랫폼      | 서비스 | 기능 요약 |
|-------------|--------|-----------|
| **AWS**     | EC2, LB, VPC, NAT, RDS, S3 | 리소스 정보·태그 조회 + 정규식 기반 검사 |
| **Cloudflare** | DNS | DNS 레코드 정보 수집 |
| **OCI**     | Instance, LB, NSG, Volume, Object, Cost, Policy Search | 병렬 수집 + 크레딧/비용 분석 + IAM 정책 검색 |
| **SSH**     | SSH config | 병렬 접속 상태 검사 + 서버 정보 수집 |

---

## 📂 프로젝트 구조

```
ic/
├── cli.py                         # CLI 진입점
├── common/                        # 공통 유틸 및 로깅
│   ├── log.py
│   ├── utils.py
│   ├── slack.py
│   └── gather_env.py
├── aws/
│   ├── ec2/ list_tags.py, tag_check.py, list_info.py
│   ├── lb/  list_tags.py, tag_check.py
│   ├── nat/  list_tags.py, tag_check.py
│   ├── rds/ list_tags.py, tag_check.py
│   ├── s3/  list_tags.py, tag_check.py
│   └── vpc/ list_tags.py, tag_check.py
├── cf/
│   └── dns/ list_info.py
├── oci_module/
│   ├── info/oci_info.py           # 병렬 OCI 리소스 + 비용/크레딧 수집
│   └── search/policy_search.py    # OCI IAM 정책 검색
├── ssh/
│   ├── server_info.py            # 병렬 상태 수집
│   └── auto_ssh.py               # SSH 자동 등록
├── scripts/                      # 개별 자동화 스크립트
│   ├── cf_edge_nsg_make/         # Cloudflare Edge NSG 생성기
│   │   └── cf_edge_nsg_make.py
│   └── oracle-policy/            # OCI 사용자/그룹 정책 조회 TUI
│       └── user_policy.py
└── .env / .env.example           # 환경변수 설정
```

---

## 🚀 설치 및 실행

### 1. 설치
```bash
pip install -r requirements.txt
```

### 2. CLI 설치
```bash
pip install .
# 또는 개발용
pip install -e .
```

### 3. .env 설정
`.env.example` 파일을 참고해 `.env` 작성:
```ini
# -------  COMMON ENV ----------
LOG_LEVEL=DEBUG  # Log level setting
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/

# --------- AWS ENV ------------
REGIONS=ap-northeast-1         # aws regions. ex) ap-northeast-1,ap-northeast-2
AWS_ACCOUNTS=22222222222         # aws Account. ex) 229930918337,229930918337

# --------- TAG ENV ------------
REQUIRED_TAGS=User,CreateBy,Team,TeamName,Name,Service,Application,Role,Environment
OPTIONAL_TAGS=Env
RULE_USER=^.+$
RULE_TEAM=^\d+$
RULE_NAME=^[a-zA-Z0-9_.\-/+() ]+$
RULE_ROLE=^[a-zA-Z0-9_\-+, ]+$
RULE_ENVIRONMENT=^(PROD|STG|DEV|TEST|QA)$


# --------- CloudFlare ------------
CLOUDFLARE_EMAIL=cruiser594@gmail.com     # Account Login Email
CLOUDFLARE_API_TOKEN=tokentokentoken        # Account Token(Account Level)
CLOUDFLARE_ACCOUNTS=account_name       # Account (NAME)
CLOUDFLARE_ZONES=zone_name             # HOSTZONE (NAME)


# --------- OCI ------------
OCI_CONFIG_PATH=~/.oci/config               # OCI config 파일 경로
OCI_TENANCY_OCID=ocid1.tenancy.oc1..xxxxx   # OCI Tenancy OCID
OCI_USER_OCID=ocid1.user.oc1..xxxxx         # OCI User OCID
OCI_KEY_FILE=~/.oci/oci_api_key.pem         # OCI API 서명용 private key 파일
OCI_FINGERPRINT=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx  # Key fingerprint
OCI_REGION=ap-seoul-1                       # OCI 기본 리전
SHOW_EMPTY_COMPARTMENTS=false               # 빈 컴파트먼트 표시 여부


# --------- SSH ------------
SSH_KEY_DIR=~/aws-key               # 기본 키파일 디렉토리
SSH_CONFIG_FILE=~/.ssh/config       # ~/.ssh/config 경로 (커스텀일 수 있음)
SSH_MAX_WORKER=70                   # 병렬 스캔 스레드 수
PORT_OPEN_TIMEOUT=0.5               # 포트스캔 timeout
SSH_TIMEOUT=5                      # SSH 접속 timeout
```

---

## 🔧 초기 설정 가이드 (Credentials & Config)

아래 내용은 각 플랫폼별 *필수 선행 설정*을 정리한 것입니다. CLI 실행 전 한 번만 준비해두면 이후 모든 명령이 원활히 동작합니다.

### 1) AWS

1. **AWS CLI 설치**  
   macOS(hombrew): `brew install awscli`

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

### 2) OCI

1. **OCI CLI 설치**  
   `brew install oci-cli` *또는* `pip install oci`

2. **`~/.oci/config` 예시**
   ```ini
   [DEFAULT]
   user=ocid1.user.oc1..aaaaa
   tenancy=ocid1.tenancy.oc1..bbbbb
   region=ap-seoul-1
   fingerprint=aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99
   key_file=~/.oci/oci_api_key.pem
   ```
   `oci setup keys` 명령으로 API Key를 만들 수 있으며, 공개키를 콘솔에 등록해야 합니다.

3. **필수 정책** (비용·Usage API 사용 시)
   ```text
   allow group FinOps to read usage-reports in tenancy
   allow group FinOps to inspect compartments in tenancy
   ```

4. **환경변수 요약**
   | 변수 | 설명 | 예시 |
   |------|------|------|
   | `OCI_CONFIG_PATH` | 커스텀 config 경로 | `/opt/oci/config` |
   | `SHOW_EMPTY_COMPARTMENTS` | 빈 컴파트먼트도 출력 | `true` |

### 3) Cloudflare

1. **API Token 생성**  
   *My Profile → API Tokens → Create Token* 에서 `Zone DNS Read` (또는 Account 단위) 권한 토큰을 발급합니다.

2. **`.env` 설정**
   ```env
   CLOUDFLARE_EMAIL=you@example.com
   CLOUDFLARE_API_TOKEN=cf_token_xxxxxxxxxxxxxxxxx
   CLOUDFLARE_ACCOUNTS=myaccount1,myaccount2   # 대소문자 구분 없이 이름 값
   CLOUDFLARE_ZONES=example.com,api.example.com
   ```

### 4) SSH

1. **`~/.ssh/config` 예시**
   ```ssh
   Host web-prod-1
       HostName 10.0.10.15
       User ec2-user
       IdentityFile ~/.ssh/prod.pem

   Host db-dev-1
       HostName 10.0.20.12
       User ubuntu
       IdentityFile ~/.ssh/dev.pem
   ```

2. **관련 환경변수**
   | 변수 | 설명 | 기본값 |
   |------|------|--------|
   | `SSH_CONFIG_FILE` | SSH config 위치 | `~/.ssh/config` |
   | `SSH_KEY_DIR` | 개인 키 디렉토리 | `~/aws-key` |
   | `SSH_MAX_WORKER` | 동시 스레드 수 | `70` |
   | `PORT_OPEN_TIMEOUT` | 포트 스캔 타임아웃(초) | `0.5` |
   | `SSH_TIMEOUT` | SSH 접속 타임아웃(초) | `5` |

### 5) Slack Webhook (선택)

Slack *Incoming Webhook* URL 을 발급한 뒤 `.env` 의 `SLACK_WEBHOOK_URL` 변수에 그대로 기입하면, 태그 검사 등의 결과 테이블이 Slack 으로 전송됩니다.

---

## ⚖️ 명령어 · 옵션 총정리

> 기본적으로 **모든 옵션을 생략**하면 `.env` 값이 사용됩니다.  
> 커맨드 라인 옵션으로 입력 시 `.env` 값을 **덮어쓰며**, 쉼표(,) 로 다중 입력이 가능합니다.

### 1) AWS

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| ec2 | `list_tags` | `-a` Account IDs, `-r` Regions | EC2 태그 목록 조회 | `ic aws ec2 list_tags -a 111111111111 -r ap-northeast-1` |
| ec2 | `tag_check` | `-a`, `-r` | EC2 태그 필수값·정규식 검사 | `ic aws ec2 tag_check` |
| ec2 | `list_info` | `-a`, `-r` | 인스턴스 상세(Subnet·SG·vCPU 등) 조회 | `ic aws ec2 list_info -r ap-northeast-2` |
| lb  | `list_tags` | `-a`, `-r` | ELB/ALB 태그 목록 | `ic aws lb list_tags` |
| lb  | `tag_check` | `-a`, `-r` | ELB/ALB 태그 검사 | `ic aws lb tag_check -a 222222222222` |
| vpc | `list_tags` | `-a`, `-r` | VPC / IGW / VGW 태그 목록 | `ic aws vpc list_tags` |
| vpc | `tag_check` | `-a`, `-r` | VPC / Gateway 태그 검사 | `ic aws vpc tag_check` |
| nat | `list_tags` | `-a`, `-r` | NAT Gateway 태그 목록 | `ic aws nat list_tags -r ap-northeast-1` |
| nat | `tag_check` | `-a`, `-r` | NAT Gateway 태그 검사 + Slack 알림 | `ic aws nat tag_check` |
| rds | `list_tags` | `-a`, `-r` | RDS 태그 목록 | `ic aws rds list_tags` |
| rds | `tag_check` | `-a`, `-r` | RDS 태그 검사 | `ic aws rds tag_check` |
| s3  | `list_tags` | `-a`, `-r` | S3 버킷 태그 목록 | `ic aws s3 list_tags` |
| s3  | `tag_check` | `-a`, `-r` | S3 태그 검사 | `ic aws s3 tag_check -r us-east-1` |

공통 옵션

| 옵션 | 전체형 | 기본값 | 설명 |
|------|--------|--------|------|
| `-a` | `--account` | `.env: AWS_ACCOUNTS` | AWS 계정 ID(,) |
| `-r` | `--regions` | `.env: REGIONS` | 조회 리전(,) |

### 2) Cloudflare

| Service | Subcommand | 옵션 | 설명 | 예시 |
|---------|------------|------|------|------|
| dns | `list_info` | `-a` Account 필터, `-z` Zone 필터 | DNS 레코드 조회 | `ic cf dns list_info -a supercycl -z example.com` |

| 옵션 | 전체형 | 기본값 | 설명 |
|------|--------|--------|------|
| `-a` | `--account` | `.env: CLOUDFLARE_ACCOUNTS` | Account 이름 부분 일치 |
| `-z` | `--zone` | `.env: CLOUDFLARE_ZONES` | Zone 이름 부분 일치 |

### 3) OCI

| Service | 옵션 세트 | 설명 | 예시 |
|---------|-----------|------|------|
| `oci info` | `--instance` `--lb` `--nsg` `--volume` `--object` | 리소스 종류별 출력 토글 | `ic oci info --instance --nsg` |
|          | `--cost --cost-start YYYY-MM-DD --cost-end YYYY-MM-DD` | Usage API 비용 | `ic oci info --cost --cost-start 2024-01-01 --cost-end 2024-01-31` |
|          | `--credit --credit-year 2024 --credit-initial 3000` | 크레딧 소진 현황 | `ic oci info --credit --credit-year 2024 --credit-initial 5000` |
|          | `-n` / `--name` | 이름 부분 일치 필터 | `ic oci info --instance -n prod` |
|          | `-c` / `--compartment` | 컴파트먼트 이름 필터 | `ic oci info --lb -c network` |
|          | `--regions` | 리전 목록(,) | `ic oci info --volume --regions ap-seoul-1,us-ashburn-1` |
| `oci search` | `-p / --policy` | IAM Policy 검색 모드 활성 | `ic oci search -p` |
|              | `--show-empty` | 빈 컴파트먼트도 출력 | `ic oci search -p --show-empty` |

기본적으로 `OCI_CONFIG_PATH`, `OCI_REGION` 등의 값은 `.env` 또는 `~/.oci/config` 에서 불러옵니다.

### 4) SSH

| Service | Subcommand | 옵션 | 설명 | 예시 |
|---------|------------|------|------|------|
| ssh | `info` | *(없음)* | 등록된 서버 병렬 접속·리소스 수집 | `ic ssh info` |

SSH 관련 타임아웃·스레드 설정은 `.env` (`SSH_MAX_WORKER` 등) 로 조정 가능합니다.

---

## 📊 주요 동작 방식

- `.env` 기반으로 계정/리전 설정 → `common.utils.get_profiles()`로 프로파일 매핑
- `ThreadPoolExecutor`로 병렬 수집 (계정 x 리전 조합)
- 결과는 Rich Table 로 출력 + 필요한 경우 Slack Webhook 전송
- `tag_check`는 정규식 기반 유효성 검사 수행

---

## 💬 Slack 알림 (선택)

- `.env`에 `SLACK_WEBHOOK_URL` 정의 시 사용
- 슬랙 함수:
  - `send_slack_message()`
  - `send_slack_blocks_table()` / `..._with_color()`
- 메시지 크기 초과(too_many_attachments) 방지 처리 포함

---

## ⚠️ 유의 사항

- S3는 리전 간 API 제한 이슈 있음 → `IllegalLocationConstraintException` 처리 필요
- Slack 413 Payload Too Large → 전송 건수 제한 필요
- `RULE_XXX` 정규식은 `.env` 기반 + 코드 내부 정의와 병합되어 동작
- SSH는 기본적으로 `~/.ssh/config` 기반으로 등록된 서버들 조회
- AWS 는 기본적으로 AWS-Vault, .aws/config, .aws/credential 바탕으로 동작하며 관련 설정 필요

---

## 🚧 확장 가능성

- `apply_tags`, `backup_tags`, `excel_to_json` 등의 기능 추가 예정
- Terraform / CloudFormation 태그 통합도 가능
- GitHub Actions / Jenkins 등과 통합하여 자동 검사 가능

---

## 📅 유지보수 / 문의

- Maintainer: **SY KIM** (cruiser594@gmail.com.com)
- License: MIT

