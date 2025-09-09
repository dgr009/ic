# 설정 시스템 마이그레이션 가이드

## 개요

IC v2.0에서는 기존의 .env 파일 기반 설정에서 YAML 기반 설정 시스템으로 변경되었습니다. 이 가이드는 기존 사용자가 새로운 설정 시스템으로 마이그레이션하는 방법을 설명합니다.

## 마이그레이션이 필요한 이유

### 기존 시스템의 한계
- 평면적인 키-값 구조로 복잡한 설정 표현 어려움
- 민감한 정보와 일반 설정의 구분 없음
- 설정 검증 및 타입 체크 부족
- 주석 및 문서화 제한

### 새로운 시스템의 장점
- 계층적 구조로 복잡한 설정 표현 가능
- 민감한 정보와 일반 설정 분리
- 스키마 검증 및 타입 체크
- 주석 및 문서화 지원
- 외부 설정 파일 자동 로딩

## 자동 마이그레이션

### 1. 기본 마이그레이션

```bash
# 현재 .env 파일을 YAML로 마이그레이션
ic config migrate

# 마이그레이션 미리보기 (실제 변경 없음)
ic config migrate --dry-run

# 기존 YAML 파일이 있어도 강제 실행
ic config migrate --force
```

### 2. 백업 생성

```bash
# 백업과 함께 마이그레이션
ic config migrate --backup
```

마이그레이션 시 다음 파일들이 자동으로 백업됩니다:
- `.env` → `backup/.env_YYYYMMDD_HHMMSS`
- `config/default.yaml` → `backup/default_YYYYMMDD_HHMMSS.yaml`
- `config/secrets.yaml` → `backup/secrets_YYYYMMDD_HHMMSS.yaml`

## 수동 마이그레이션

### 1. 기존 .env 파일 분석

```bash
# .env 파일 내용 확인
cat .env | grep -E "^[A-Z_]+="
```

### 2. YAML 파일 생성

#### .ic/config/default.yaml 생성

**Note**: IC now uses `.ic/config/` as the preferred configuration directory.
```yaml
# 일반 설정
aws:
  region: us-west-2
  profile: default
  accounts: ["123456789012"]
  
gcp:
  project_id: my-project
  region: us-central1
  
azure:
  subscription_id: your-subscription-id
  resource_group: my-resource-group
  
ssh:
  config_file: ~/.ssh/config
  key_dir: ~/aws-key
  max_workers: 70
  timeout: 5
```

#### .ic/config/secrets.yaml 생성
```yaml
# 민감한 정보 (환경변수 참조 권장)
aws:
  access_key_id: ${AWS_ACCESS_KEY_ID}
  secret_access_key: ${AWS_SECRET_ACCESS_KEY}
  
gcp:
  service_account_key_path: ${GCP_SERVICE_ACCOUNT_KEY_PATH}
  
cloudflare:
  email: ${CLOUDFLARE_EMAIL}
  api_token: ${CLOUDFLARE_API_TOKEN}
  
slack:
  webhook_url: ${SLACK_WEBHOOK_URL}
```

### 3. 환경변수 설정

```bash
# AWS
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key

# GCP
export GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json

# CloudFlare
export CLOUDFLARE_EMAIL=your-email@example.com
export CLOUDFLARE_API_TOKEN=your-api-token

# Slack
export SLACK_WEBHOOK_URL=your-webhook-url
```

## 설정 매핑 가이드

### AWS 설정
```bash
# .env
AWS_REGION=us-west-2
AWS_PROFILE=default
AWS_ACCOUNTS=123456789012,987654321098

# YAML
aws:
  region: us-west-2
  profile: default
  accounts: ["123456789012", "987654321098"]
```

### GCP 설정
```bash
# .env
GCP_PROJECT_ID=my-project
GCP_REGION=us-central1
GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/key.json

# YAML
gcp:
  project_id: my-project
  region: us-central1
  service_account_key_path: ${GCP_SERVICE_ACCOUNT_KEY_PATH}
```

### SSH 설정
```bash
# .env
SSH_CONFIG_FILE=~/.ssh/config
SSH_KEY_DIR=~/aws-key
SSH_MAX_WORKER=70
SSH_TIMEOUT=5

# YAML
ssh:
  config_file: ~/.ssh/config
  key_dir: ~/aws-key
  max_workers: 70
  timeout: 5
```

## 마이그레이션 검증

### 1. 설정 검증
```bash
# 설정 파일 문법 검사
ic config validate

# 현재 설정 확인
ic config show
```

### 2. 기능 테스트
```bash
# 각 서비스별 기본 명령어 테스트
ic aws ec2 list
ic gcp compute list
ic azure vm list
```

### 3. 통합 테스트
```bash
# 전체 시스템 통합 테스트
python scripts/integration_test.py
```

## 문제 해결

### 일반적인 문제

1. **YAML 문법 오류**
   ```bash
   # 문법 검사
   ic config validate
   
   # 오류 메시지 확인 후 수정
   ```

2. **환경변수 누락**
   ```bash
   # 필요한 환경변수 확인
   ic config show --missing-env
   
   # 환경변수 설정
   export MISSING_VAR=value
   ```

3. **권한 문제**
   ```bash
   # 파일 권한 설정
   chmod 600 config/secrets.yaml
   chmod 644 config/default.yaml
   ```

4. **백업 파일 복원**
   ```bash
   # 최신 백업에서 복원
   cp backup/.env_YYYYMMDD_HHMMSS .env
   rm -rf config/
   ```

### 디버깅

```bash
# 디버그 모드로 실행
export LOG_LEVEL=DEBUG
ic config show

# 설정 로딩 과정 확인
python -c "
from ic.config.manager import ConfigManager
import logging
logging.basicConfig(level=logging.DEBUG)
config = ConfigManager().get_config()
print(config)
"
```

## 롤백 방법

마이그레이션 후 문제가 발생한 경우:

### 1. 자동 롤백
```bash
# 백업에서 자동 복원
ic config rollback
```

### 2. 수동 롤백
```bash
# 1. 백업된 .env 파일 복원
cp backup/.env_YYYYMMDD_HHMMSS .env

# 2. YAML 설정 파일 제거
rm -rf config/

# 3. 애플리케이션 재시작
```

## 마이그레이션 체크리스트

- [ ] 기존 .env 파일 백업
- [ ] 자동 마이그레이션 실행
- [ ] YAML 파일 생성 확인
- [ ] 환경변수 설정
- [ ] 파일 권한 설정
- [ ] 설정 검증 실행
- [ ] 기능 테스트 실행
- [ ] 통합 테스트 실행
- [ ] 문서 업데이트
- [ ] 팀원들에게 변경사항 공유

## 추가 리소스

- [사용자 가이드](user_guide.md)
- [설정 시스템 가이드](configuration.md)
- [트러블슈팅 가이드](troubleshooting.md)
- [API 문서](api_documentation.md)

## 지원

마이그레이션 과정에서 문제가 발생하면:
1. [트러블슈팅 가이드](troubleshooting.md) 확인
2. GitHub Issues에 문제 보고
3. 로그 파일과 함께 상세한 오류 정보 제공
