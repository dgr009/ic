# IC (Infra Resource Management CLI)

`IC`는 AWS, OCI, Cloudflare, SSH 기반 인프라 리소스를 대상으로 **태그 관리, 리소스 수집, 유효성 검사, 자동화**를 수행할 수 있는 Python 기반 CLI 툴입니다.

- AWS 리소스 태그 확인/검사 (EC2, LB, RDS, S3, VPC 등)
- Cloudflare DNS 레코드 수집
- OCI 자원 및 비용 병렬 수집
- SSH 서버 상태 및 자동 등록 지원

---

## ⭐️ 주요 기능 요약

| 플랫폼      | 서비스 | 기능 요약 |
|-------------|--------|-----------|
| **AWS**     | EC2, LB, VPC, RDS, S3 | 리소스 정보 조회 + 태그 조회 및 정규식 기반 검사 |
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
│   ├── rds/ list_tags.py, tag_check.py
│   ├── s3/  list_tags.py, tag_check.py
│   └── vpc/ list_tags.py, tag_check.py
├── cf/
│   └── dns/ list_info.py
├── oci_module/
│   ├── info.py                   # 병렬 OCI 리소스 수집
│   └── search/
│       └── policy_search.py     # OCI IAM 정책 검색
├── ssh/
│   ├── server_info.py            # 병렬 상태 수집
│   └── auto_ssh.py               # SSH 자동 등록
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
AWS_ACCOUNTS=229930918337         # aws Account. ex) account_number

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
CLOUDFLARE_ACCOUNTS=account       # Account (NAME)
CLOUDFLARE_ZONES=zone             # HOSTZONE (NAME)


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
...
```

---

## ⚖️ 명령어 사용 예시

```bash
ic aws ec2 list_tags --account 123456789012 --regions ap-northeast-2
ic aws ec2 tag_check
ic aws rds list_tags
ic cf dns list_info
ic oci info --instance --cost
ic oci search -p
ic ssh info
```

### AWS 지원 서비스
- `ec2`, `lb`, `vpc`, `rds`, `s3`
- 명령어: `list_tags`, `tag_check`, `list_info`

### Cloudflare
- `cf dns list_info` : DNS 레코드 조회

### OCI
- `oci info --instance`, `--lb`, `--nsg`, `--volume`, `--object`, `--cost`, `--credit`
- `oci search -p` : IAM 정책 검색 (사용자/그룹별)

### SSH
- `ssh info`: 등록된 서버 병렬 접속 상태 및 디스크/CPU/메모리 수집

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

- Maintainer: **cruiser594** (cruiser594@gmail.com)
- License: MIT

