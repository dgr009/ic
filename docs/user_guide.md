# IC (Infrastructure Commander) 사용자 가이드

## 개요

IC는 통합 클라우드 인프라 관리 도구로, AWS, GCP, Azure, OCI, CloudFlare 등 다양한 클라우드 서비스를 하나의 도구로 관리할 수 있습니다.

## 새로운 기능 (v2.0)

### YAML 기반 설정 시스템
- 구조화된 설정 관리
- 민감한 정보와 일반 설정 분리
- 환경변수 지원
- 외부 설정 파일 자동 로딩

## 빠른 시작

### 1. 설치

```bash
# 저장소 클론
git clone <repository-url>
cd ic

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt
```

### 2. 설정

#### 새로운 설정 시스템 사용 (권장)

```bash
# 기본 설정 파일 생성
ic config init

# 기존 .env 파일에서 마이그레이션
ic config migrate
```

#### 설정 파일 구조

```
config/
├── default.yaml    # 일반 설정
└── secrets.yaml    # 민감한 정보
```

### 3. 기본 사용법

```bash
# 설정 확인
ic config show

# AWS 서비스
ic aws ec2 list
ic aws s3 list

# GCP 서비스  
ic gcp compute list
ic gcp storage list

# SSH 관리
ic ssh scan
ic ssh connect <hostname>
```

## 설정 관리

### YAML 설정 파일

#### .ic/config/default.yaml

**Note**: IC now uses `.ic/config/` as the preferred configuration directory. The legacy `config/` directory is still supported for backward compatibility.
```yaml
aws:
  region: us-west-2
  profile: default
  
gcp:
  project_id: my-project
  region: us-central1
  
azure:
  subscription_id: your-subscription-id
  resource_group: my-resource-group
```

#### .ic/config/secrets.yaml
```yaml
aws:
  access_key_id: ${AWS_ACCESS_KEY_ID}
  secret_access_key: ${AWS_SECRET_ACCESS_KEY}
  
gcp:
  service_account_key_path: ${GCP_SERVICE_ACCOUNT_KEY_PATH}
  
cloudflare:
  api_token: ${CLOUDFLARE_API_TOKEN}
```

### 환경변수

민감한 정보는 환경변수로 관리하세요:

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json
export CLOUDFLARE_API_TOKEN=your-api-token
```

## 주요 명령어

### 설정 관리
- `ic config init` - 기본 설정 파일 생성
- `ic config show` - 현재 설정 표시
- `ic config validate` - 설정 검증
- `ic config migrate` - .env에서 YAML로 마이그레이션

### AWS 명령어
- `ic aws ec2 list` - EC2 인스턴스 목록
- `ic aws s3 list` - S3 버킷 목록
- `ic aws rds list` - RDS 인스턴스 목록
- `ic aws iam list-users` - IAM 사용자 목록

### GCP 명령어
- `ic gcp compute list` - Compute Engine 인스턴스 목록
- `ic gcp storage list` - Cloud Storage 버킷 목록
- `ic gcp sql list` - Cloud SQL 인스턴스 목록

### Azure 명령어
- `ic azure vm list` - Virtual Machine 목록
- `ic azure storage list` - Storage Account 목록

### SSH 관리
- `ic ssh scan` - SSH 서버 스캔
- `ic ssh connect <host>` - SSH 자동 연결
- `ic ssh list` - 연결 가능한 서버 목록

## 문제 해결

### 일반적인 문제

1. **설정 파일을 찾을 수 없음**
   ```bash
   ic config init  # 기본 설정 파일 생성
   ```

2. **권한 오류**
   ```bash
   chmod 600 .ic/config/secrets.yaml
   # Or for legacy location:
   chmod 600 config/secrets.yaml
   ```

3. **마이그레이션 문제**
   ```bash
   ic config migrate --dry-run  # 미리보기
   ic config migrate --force    # 강제 실행
   ```

### 로그 확인

```bash
# 로그 레벨 설정
export LOG_LEVEL=DEBUG

# 로그 파일 위치
tail -f ~/.ic/logs/ic.log
```

## 고급 사용법

### 프로그래밍 API

```python
from ic.config.manager import ConfigManager

# 설정 로딩
config_manager = ConfigManager()
config = config_manager.get_config()

# 특정 설정 접근
aws_region = config.get('aws', {}).get('region', 'us-west-2')
```

### 외부 설정 로딩

```python
from ic.config.external import ExternalConfigLoader

loader = ExternalConfigLoader()
aws_config = loader.load_aws_config()  # ~/.aws/config 로딩
```

### 시크릿 관리

```python
from ic.config.secrets import SecretsManager

secrets_manager = SecretsManager()
secrets = secrets_manager.load_secrets()
```

## 보안 고려사항

1. **파일 권한**
   ```bash
   chmod 600 .ic/config/secrets.yaml
   chmod 600 config/secrets.yaml  # Legacy location
   chmod 600 .env
   ```

2. **환경변수 사용**
   - 민감한 정보는 항상 환경변수 사용
   - 설정 파일에 하드코딩 금지

3. **Git 관리**
   ```gitignore
   .ic/config/secrets.yaml
   config/secrets.yaml
   .env
   *.log
   ```

## 지원 및 문의

- GitHub Issues: [프로젝트 이슈 페이지]
- 문서: `docs/` 디렉토리
- 예제: `examples/` 디렉토리

## 변경 로그

### v2.0.0
- ✨ YAML 기반 설정 시스템
- ✨ 자동 마이그레이션 도구
- ✨ 보안 강화
- ✨ 성능 최적화
- 🔧 모든 서비스 모듈 업데이트
