# IC (Infrastructure Commander) 사용자 가이드

## 개요

IC는 통합 클라우드 인프라 관리 CLI 도구로, **AWS**, **GCP**, **OCI**, **CloudFlare**, **SSH** 등 다양한 멀티 클라우드 및 서버 리소스를 단일 CLI 환경에서 손쉽게 조회하고 관리할 수 있습니다.

## 주요 특징 (v1.2.6+)

- **YAML 기반 보안 설정 시스템**: 민감한 자격 증명(`secrets.yaml`)과 일반 설정(`default.yaml`)의 명확한 분리
- **실시간 프로그레스 바**: 리전 및 계정별 리소스 수집 진행 상황 시각화
- **보안 중심 탐색**: AWS Security Group Ingress/Egress 규칙 분석 및 Tree 형식 지원 (`-o tree`)
- **다중 플랫폼 완벽 지원**: AWS, GCP (Compute, Storage, VPC, GKE, SQL), OCI, CloudFlare, SSH

## 빠른 시작

### 1. 설치

```bash
# PyPI를 통한 설치 (권장)
pip install ic-code

# 버전에 대한 설치 확인
ic --version
ic --help
```

### 2. 설정 초기화

```bash
# 기본 설정 생성
ic config init

# 설정 검증 및 현재 설정 확인
ic config validate
ic config show
```

### 3. 설정 파일 구조 (`~/.ic/config/`)

```
~/.ic/config/
├── default.yaml    # 콘솔/파일 로그 레벨 등 기본 옵션
└── secrets.yaml    # AWS 프로필, GCP 자격 증명 경로, OCI 설정 경로, CloudFlare 토큰 등
```

#### `.ic/config/secrets.yaml` 예시
```yaml
aws:
  accounts:
    - "123456789012"
  profiles:
    default: "my-aws-profile"
  regions:
    - "ap-northeast-2"
    - "us-east-1"

gcp:
  project_id: "my-gcp-project-id"
  credentials_file: "~/.config/gcloud/application_default_credentials.json"
  regions:
    - "asia-northeast3"

oci:
  config_file: "~/.oci/config"
  profile: "DEFAULT"

cloudflare:
  api_token: "your-cloudflare-api-token"

ssh:
  key_dir: "~/.ssh"
  skip_prefixes:
    - "bastion"
```

## 주요 명령어 안내

### 설정 및 보안
- `ic config init` - 기본 설정 파일 가이드 생성
- `ic config show` - 현재 설정 표시 (민감 정보 자동 마스킹)
- `ic config validate` - 설정 파일 무결성 및 경로 검증
- `ic security scan` - 프로젝트 코드 내 하드코딩된 시크릿 탐지
- `ic security install-hooks` - Git Pre-commit 보안 훅 설치

### AWS 서비스
- `ic aws ec2 info` - EC2 인스턴스 정보 조회
- `ic aws sg info` - Security Group 인바운드/아웃바운드 룰 조회
  - `--ingress` (`-i`): 인바운드 규칙만 출력
  - `--egress` (`-e`): 아웃바운드 규칙만 출력
  - `-o tree`: 방향 화살표(`←`, `→`)가 포함된 시각적 트리 구조 출력
- `ic aws s3 info` / `ic aws s3 tag_check` - S3 버킷 및 태깅 준수 검사
- `ic aws rds info` - RDS 인스턴스 및 클러스터 정보
- `ic aws vpc info` / `ic aws lb info` - VPC 네트워크 및 로드밸런서
- `ic aws eks info` / `ic aws ecs info` - Kubernetes 및 컨테이너 서비스

### GCP 서비스
- `ic gcp compute info` - Compute Engine VM 인스턴스 정보
- `ic gcp storage info` - Cloud Storage 버킷 정보
- `ic gcp vpc info` - VPC 네트워크 및 서브넷 정보
- `ic gcp gke info` - GKE 클러스터 구성 정보
- `ic gcp sql info` - Cloud SQL 인스턴스 정보

### OCI 서비스
- `ic oci vm info` - Compute VM 인스턴스
- `ic oci vcn info` - Virtual Cloud Network
- `ic oci lb info` / `ic oci nsg info` - 로드밸런서 및 NSG 보안 그룹
- `ic oci volume info` / `ic oci obj info` - 스토리지 볼륨 및 버킷
- `ic oci cost usage` - 비용 분석 및 크레딧 잔액

### CloudFlare & SSH
- `ic cf zone info` - DNS 존 및 도메인 정보
- `ic cf dns info` - DNS 레코드 상세 정보
- `ic ssh info` - SSH 서버 스캔 및 정보 수집
