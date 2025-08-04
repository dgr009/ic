# IC (Infra Resource Management CLI)

`IC`는 AWS, OCI, Cloudflare, SSH 기반 인프라 리소스를 대상으로 **리소스 수집, 태그 관리, 유효성 검사, 자동화**를 수행할 수 있는 Python 기반 CLI 툴입니다.

- AWS 리소스 정보·태그 조회 및 검사 (EC2, LB, RDS, S3, VPC, VPN 등)
- OCI 자원 및 비용 병렬 수집 및 IAM 정책 검색
- Cloudflare DNS 레코드 수집
- SSH 서버 상태 점검 및 자동 등록 지원

---

## ⭐️ 주요 기능 요약

| 플랫폼 | 서비스 | 기능 요약 |
|---|---|---|
| **AWS** | EC2, LB, RDS, S3, VPC, VPN | `info`로 리소스 상세 정보 조회, `list_tags`로 태그 조회, `tag_check`로 정규식 기반 태그 규칙 검사 |
| **OCI** | vm, lb, nsg, vcn, volume, policy, cost | `info`로 각 서비스의 자원 병렬 수집. `policy search`로 IAM 정책 검색. `cost usage/credit`로 비용 분석 |
| **Cloudflare** | DNS | `list_info`로 DNS 레코드 정보 수집 |
| **SSH** | SSH config | `info`로 병렬 접속 상태 검사 및 서버 정보 수집, `reg`으로 신규 서버 등록 |

---

## 📂 프로젝트 구조

```
ic/
├── ic/cli.py                         # CLI 진입점
├── common/                           # 공통 유틸, 로깅, Slack 연동
├── aws/                              # AWS 모듈
│   ├── ec2/ info.py, list_tags.py, tag_check.py
│   ├── lb/  info.py, list_tags.py, tag_check.py
│   ├── rds/ info.py, list_tags.py, tag_check.py
│   ├── s3/  info.py, list_tags.py, tag_check.py
│   ├── vpc/ info.py, list_tags.py, tag_check.py
│   └── vpn/ info.py
├── oci_module/                       # OCI 모듈
│   ├── vm/info.py
│   ├── lb/info.py
│   ├── nsg/info.py
│   ├── vcn/info.py
│   └── ... (기타 서비스)
├── cf/                               # Cloudflare 모듈
│   └── dns/ list_info.py
├── ssh/                              # SSH 모듈
│   ├── server_info.py
│   └── auto_ssh.py
└── .env.example                      # 환경변수 설정 예시
```

---

## 🚀 설치 및 실행

### 1. 의존성 설치
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
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 각 플랫폼에 맞는 환경변수를 설정합니다.

---

## 🔧 명령어 · 옵션 총정리

> 모든 옵션을 생략하면 `.env` 파일의 기본값이 사용됩니다.  
> 커맨드 라인 옵션으로 입력 시 `.env` 값을 덮어쓸 수 있으며, 쉼표(`,`)로 다중 입력이 가능합니다.

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

4. **명령어 요약**

   | Service | Subcommand | 주요 옵션 | 설명 |
   |---|---|---|---|
   | `ec2` | `info` | `-v`, `--name`, `-a`, `--account`, `-r`, `--region` | EC2 인스턴스 정보 조회 (상세 옵션 제공) |
   | `lb` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`| 로드 밸런서 상세 정보 조회 |
   | `rds` | `info` | `--name`, `-a`, `--account`, `-r`, `--region` | RDS 인스턴스 및 클러스터 정보 조회 |
   | `s3` | `info` | `--name` | S3 버킷 상세 정보 조회 |
   | `vpc` | `info` | `--name` | VPC, 서브넷, 라우팅 테이블 정보 조회 |
   | `vpn` | `info` | | TGW, VGW, VPN 연결, 엔드포인트 정보 조회 |
   | `*` | `list_tags`| | 각 서비스의 태그 정보 조회 |
   | `*` | `tag_check`| | 각 서비스의 태그 규칙 준수 여부 검사 |

### 2) OCI
| Service | Subcommand | 주요 옵션 | 설명 |
|---|---|---|---|
| `vm` | `info` | `-v`, `--name`, `--compartment` | VM 인스턴스 정보 조회 (상세 옵션 제공) |
| `lb` | `info` | `--name`, `--output` | 로드 밸런서 정보 조회 (테이블/트리) |
| `nsg`| `info` | `--name`, `--output` | NSG 정보 조회 (테이블/트리) |
| `vcn`| `info` | `--name` | VCN, 서브넷, 라우팅 정보 조회 |
| `policy`| `search` | | 사용자/그룹 기준 IAM 정책 검색 |
| `cost`| `usage`, `credit` | | 비용 및 크레딧 사용량 조회 |
| `*` | `info` | | 기타 서비스(volume, obj 등) 정보 조회 |

### 3) Cloudflare

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `dns` | `list_info`| `--name`, `--content` | DNS 레코드 조회 | `ic cf dns list_info --name "example.com"` |

### 4) SSH

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `info` | `(none)` | `--key`, `--host` | `~/.ssh/config` 서버 상태 스캔 | `ic ssh info --host "my-server"` |
| `reg`  | `(none)` | | 서버 스캔 후 SSH config 등록 | `ic ssh reg` |

---

## 📊 주요 동작 방식

- **병렬 처리**: `ThreadPoolExecutor`를 사용하여 여러 계정과 리전에 걸쳐 리소스 정보를 병렬로 수집하여 빠른 속도를 보장합니다.
- **출력 형식**: `rich` 라이브러리를 활용하여 가독성 높은 테이블 형식으로 결과를 출력합니다.
- **자격 증명**: `~/.aws/config`, `~/.oci/config` 등 각 플랫폼의 표준 자격 증명 방식을 사용합니다.
- **환경 변수**: `.env` 파일을 통해 계정 정보, 기본 리전, 태그 규칙 등 설정을 중앙에서 관리합니다.

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

- Maintainer: **SangYun Kim** (cruiser594@gmail.com)
- License: MIT
