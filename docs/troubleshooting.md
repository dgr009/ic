# 트러블슈팅 가이드

## 일반적인 문제

### 1. 설정 파일 관련 문제

#### 문제: "Configuration file not found"
```
FileNotFoundError: Configuration file not found
```

**해결방법:**
```bash
# 기본 설정 파일 생성
ic config init

# 또는 기존 .env에서 마이그레이션
ic config migrate
```

#### 문제: "Invalid YAML syntax"
```
yaml.YAMLError: Invalid YAML syntax in config file
```

**해결방법:**
```bash
# 설정 파일 문법 검사
ic config validate

# YAML 문법 확인 (온라인 도구 사용)
# 들여쓰기와 콜론 뒤 공백 확인
```

#### 문제: "Permission denied"
```
PermissionError: Permission denied: 'config/secrets.yaml'
```

**해결방법:**
```bash
# 파일 권한 수정
chmod 600 config/secrets.yaml
chmod 644 config/default.yaml

# 디렉토리 권한 확인
chmod 755 config/
```

### 2. 환경변수 관련 문제

#### 문제: "Environment variable not found"
```
KeyError: Environment variable 'AWS_ACCESS_KEY_ID' not found
```

**해결방법:**
```bash
# 환경변수 설정 확인
env | grep AWS

# 환경변수 설정
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key

# .bashrc 또는 .zshrc에 추가하여 영구 설정
echo 'export AWS_ACCESS_KEY_ID=your-access-key' >> ~/.bashrc
```

#### 문제: 환경변수가 설정에 반영되지 않음

**해결방법:**
```bash
# 캐시 무효화
python -c "
from ic.config.manager import ConfigManager
config_manager = ConfigManager()
config_manager.invalidate_cache()
"

# 또는 애플리케이션 재시작
```

### 3. 마이그레이션 관련 문제

#### 문제: "Migration failed: invalid literal for int()"
```
ValueError: invalid literal for int() with base 10: '70 # comment'
```

**해결방법:**
```bash
# .env 파일에서 주석 제거
sed -i 's/#.*$//' .env

# 또는 수동으로 .env 파일 정리
vim .env
```

#### 문제: "YAML files already exist"
```
Warning: YAML configuration files already exist. Use force=True to overwrite.
```

**해결방법:**
```bash
# 강제 마이그레이션
ic config migrate --force

# 또는 기존 파일 백업 후 마이그레이션
mv config/default.yaml config/default.yaml.bak
ic config migrate
```

### 4. 서비스 연결 문제

#### 문제: AWS 인증 실패
```
ClientError: The security token included in the request is invalid
```

**해결방법:**
```bash
# AWS 자격증명 확인
aws sts get-caller-identity

# 자격증명 재설정
aws configure

# 또는 환경변수로 설정
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
```

#### 문제: GCP 인증 실패
```
DefaultCredentialsError: Could not automatically determine credentials
```

**해결방법:**
```bash
# 서비스 계정 키 파일 경로 확인
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# 또는 gcloud 인증
gcloud auth application-default login
```

#### 문제: Azure 인증 실패
```
ClientAuthenticationError: Authentication failed
```

**해결방법:**
```bash
# Azure CLI 로그인
az login

# 또는 서비스 주체 자격증명 설정
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-client-secret
export AZURE_TENANT_ID=your-tenant-id
```

### 5. SSH 연결 문제

#### 문제: "SSH connection timeout"
```
TimeoutError: SSH connection timeout
```

**해결방법:**
```bash
# SSH 설정 확인
cat ~/.ssh/config

# 타임아웃 값 증가
# config/default.yaml에서:
ssh:
  timeout: 10  # 기본값 5에서 10으로 증가
```

#### 문제: "Private key not found"
```
FileNotFoundError: Private key file not found
```

**해결방법:**
```bash
# 키 파일 경로 확인
ls -la ~/aws-key/

# 설정에서 키 디렉토리 경로 수정
# config/default.yaml:
ssh:
  key_dir: /correct/path/to/keys
```

## 성능 관련 문제

### 1. 느린 설정 로딩

#### 문제: 설정 로딩이 느림

**해결방법:**
```bash
# 성능 최적화 스크립트 실행
python scripts/performance_optimization.py

# 불필요한 외부 설정 로딩 비활성화
# config/default.yaml:
external_config:
  aws_config: false  # ~/.aws/config 로딩 비활성화
  ssh_config: false  # ~/.ssh/config 로딩 비활성화
```

### 2. 메모리 사용량 증가

#### 문제: 메모리 사용량이 계속 증가

**해결방법:**
```bash
# 메모리 누수 검사
python scripts/bug_fix_and_optimization.py

# 캐시 정리
python -c "
from ic.config.manager import ConfigManager
config_manager = ConfigManager()
config_manager.invalidate_cache()
"
```

## 로깅 및 디버깅

### 로그 레벨 설정

```bash
# 디버그 모드 활성화
export LOG_LEVEL=DEBUG

# 특정 모듈만 디버그
export LOG_LEVEL=INFO
export IC_CONFIG_DEBUG=true
```

### 로그 파일 위치

```bash
# 기본 로그 위치
~/.ic/logs/ic.log

# 또는 현재 디렉토리
./logs/ic.log

# 로그 실시간 확인
tail -f ~/.ic/logs/ic.log
```

### 디버그 정보 수집

```bash
# 시스템 정보 수집
python -c "
import sys
import platform
from ic.config.manager import ConfigManager

print(f'Python: {sys.version}')
print(f'Platform: {platform.platform()}')
print(f'IC Config System: v2.0')

try:
    config_manager = ConfigManager()
    config = config_manager.get_config()
    print(f'Config sections: {list(config.keys())}')
except Exception as e:
    print(f'Config error: {e}')
"
```

## 고급 문제 해결

### 1. 설정 충돌 해결

```bash
# 설정 우선순위 확인
python -c "
from ic.config.manager import ConfigManager
config_manager = ConfigManager()
sources = config_manager.get_config_sources()
print('Config sources (priority order):', sources)
"
```

### 2. 캐시 문제 해결

```bash
# 모든 캐시 삭제
rm -rf ~/.ic/cache/
rm -rf /tmp/ic_cache/

# 설정 캐시 무효화
python -c "
from ic.config.manager import ConfigManager
ConfigManager().invalidate_cache()
"
```

### 3. 의존성 문제 해결

```bash
# 의존성 재설치
pip install --force-reinstall -r requirements.txt

# 가상환경 재생성
deactivate
rm -rf venv/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 문제 보고

문제를 보고할 때 다음 정보를 포함해주세요:

### 1. 환경 정보
```bash
# 시스템 정보
uname -a
python --version
pip list | grep -E "(yaml|boto3|google|azure)"
```

### 2. 설정 정보 (민감한 정보 제외)
```bash
# 설정 구조만 확인
ic config show --structure-only
```

### 3. 로그 파일
```bash
# 최근 로그 (민감한 정보 마스킹)
tail -100 ~/.ic/logs/ic.log | sed 's/[A-Za-z0-9+/=]\{20,\}/***MASKED***/g'
```

### 4. 재현 단계
- 문제가 발생한 정확한 명령어
- 예상 결과와 실제 결과
- 문제 발생 빈도

## 추가 도움

- GitHub Issues: [프로젝트 이슈 페이지]
- 문서: `docs/` 디렉토리의 다른 가이드들
- 예제: `examples/` 디렉토리
- 커뮤니티: [Discord/Slack 채널]
