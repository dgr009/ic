# IC (Infra Resource Management CLI)

`IC`는 멀티 클라우드 환경의 인프라 리소스를 통합 관리할 수 있는 Python 기반 CLI 툴입니다. **리소스 수집, 태그 관리, 유효성 검사, 자동화**를 지원하며, 병렬 처리를 통해 빠른 성능을 제공합니다.

**지원 플랫폼:**
- **AWS**: EC2, ECS, EKS, Fargate, MSK, CodePipeline, LB, RDS, S3, VPC, VPN, Security Groups 등
- **OCI**: VM, LB, NSG, VCN, Volume, Object Storage, Policy, Cost 등  
- **Azure**: VM, VNet (Mock 구현)
- **GCP**: Compute Engine, VPC (Mock 구현)
- **Cloudflare**: DNS 레코드 관리
- **SSH**: 서버 상태 점검 및 자동 등록

---

## ⭐️ 주요 기능 요약

| 플랫폼 | 서비스 | 기능 요약 |
|---|---|---|
| **AWS** | EC2, ECS, EKS, Fargate, MSK, CodePipeline, LB, RDS, S3, VPC, VPN, SG, NAT | `info`로 리소스 상세 정보 조회, `list_tags`로 태그 조회, `tag_check`로 정규식 기반 태그 규칙 검사. ECS는 클러스터/서비스/태스크 정보, EKS는 클러스터/노드그룹 정보, Fargate는 프로파일/태스크 정보, MSK는 Kafka 클러스터 정보, CodePipeline은 빌드/배포 상태 조회 |
| **OCI** | VM, LB, NSG, VCN, Volume, Object, Policy, Cost | `info`로 각 서비스의 자원 병렬 수집. `policy search`로 IAM 정책 검색. `cost usage/credit`로 비용 분석 |
| **Azure** | VM, VNet | `info`로 리소스 정보 조회 (Mock 데이터 기반) |
| **GCP** | Compute, VPC | `info`로 리소스 정보 조회 (Mock 데이터 기반) |
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
│   ├── eks/   info.py                          # EKS 클러스터 정보
│   ├── fargate/ info.py                        # Fargate 프로파일/태스크
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
├── azure/                            # Azure 모듈 (Mock)
│   ├── vm/info.py, mock_data.json
│   └── vnet/info.py, mock_data.json
├── gcp/                              # GCP 모듈 (Mock)
│   ├── compute/info.py, mock_data.json
│   └── vpc/info.py, mock_data.json
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
   | `ecs` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | ECS 클러스터 종합 정보 (서비스 수, 태스크 상태별 개수, 컨테이너 인스턴스 수) |
   | `ecs` | `service` | `--cluster`, `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | ECS 서비스 상세 정보 (태스크 정의, 로드 밸런서, 실행 상태) |
   | `ecs` | `task` | `--cluster`, `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | ECS 태스크 상세 정보 (컨테이너 상태, 네트워크 정보, 리소스 할당) |
   | `eks` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | EKS 클러스터 정보 (컨트롤 플레인, 네트워킹, API 서버 접근, 관리형 노드 그룹) |
   | `msk` | `info` | `--name`, `-a`, `--account`, `-r`, `--region`, `--output` | MSK 클러스터 정보 (Kafka 버전, 브로커 수, 암호화 설정, 모니터링 상태) |
   | `msk` | `broker` | `-c`, `--cluster`, `-a`, `--account`, `-r`, `--region`, `--output` | MSK 브로커 엔드포인트 정보 (연결 타입별 엔드포인트, 포트, 인증 방식) |
   | `fargate` | `info` | `--cluster-name`, `--type`, `-a`, `--account`, `-r`, `--region`, `--output` | Fargate 정보 (EKS 프로파일 또는 ECS 태스크) |
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

### 3) Azure (Mock 구현)

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `vm` | `info` | `--name`, `--resource-group` | Azure VM 정보 조회 (Mock) | `ic azure vm info --name "my-vm"` |
| `vnet` | `info` | `--name`, `--resource-group` | Azure VNet 정보 조회 (Mock) | `ic azure vnet info --name "my-vnet"` |

### 4) GCP (Mock 구현)

| Service | Subcommand | 주요 옵션 | 설명 | 예시 |
|---------|------------|-----------|------|------|
| `compute` | `info` | `--name`, `--project`, `--zone` | GCP Compute Engine 정보 조회 (Mock) | `ic gcp compute info --name "my-instance"` |
| `vpc` | `info` | `--name`, `--project` | GCP VPC 정보 조회 (Mock) | `ic gcp vpc info --name "my-vpc"` |

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

## 📊 주요 동작 방식

- **병렬 처리**: `ThreadPoolExecutor`를 사용하여 여러 계정과 리전에 걸쳐 리소스 정보를 병렬로 수집하여 빠른 속도를 보장합니다.
- **출력 형식**: `rich` 라이브러리를 활용하여 가독성 높은 테이블/트리 형식으로 결과를 출력합니다.
- **자격 증명**: 각 플랫폼의 표준 자격 증명 방식을 사용합니다:
  - AWS: `~/.aws/config`, `~/.aws/credentials`
  - OCI: `~/.oci/config`
  - Cloudflare: API Token 환경변수
- **환경 변수**: `.env` 파일을 통해 계정 정보, 기본 리전, 태그 규칙 등 설정을 중앙에서 관리합니다.
- **멀티 서비스**: 쉼표(`,`)로 구분하여 여러 서비스를 동시에 실행할 수 있습니다. (예: `ic oci vm,lb,nsg info`)
- **필터링**: 이름, 계정, 리전, 컴파트먼트 등 다양한 필터 옵션을 제공합니다.

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
- **Mock 모듈**: Azure, GCP는 현재 Mock 데이터 기반으로 동작 (실제 API 연동 예정)

---

## 🚧 확장 가능성

- **태그 관리**: `apply_tags`, `backup_tags`, `excel_to_json` 등의 기능 추가 예정
- **IaC 통합**: Terraform / CloudFormation 태그 통합 지원
- **CI/CD 통합**: GitHub Actions / Jenkins 등과 통합하여 자동 검사 가능
- **실제 API 연동**: Azure, GCP Mock 모듈을 실제 API 연동으로 전환 예정
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
ic aws eks info --name my-cluster --output json

# Fargate 프로파일 조회 (EKS)
ic aws fargate info --cluster-name my-eks-cluster

# Fargate 태스크 조회 (ECS)
ic aws fargate info --type ecs --cluster-name my-ecs-cluster

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

# Azure VM 정보 조회 (Mock)
ic azure vm info --name my-vm --resource-group rg-prod
```

---

## 📅 유지보수 / 문의

- Maintainer: **SangYun Kim** (cruiser594@gmail.com)
- License: MIT

