# PyPI 배포 가이드

이 문서는 IC 패키지를 PyPI에 배포하는 방법을 설명합니다.

## 📋 배포 준비사항

### 1. 필수 도구 설치

```bash
# 빌드 도구 설치
pip install build twine

# 개발 의존성 설치
pip install -e .[dev]
```

### 2. PyPI 계정 설정

#### PyPI 계정 생성
1. [PyPI](https://pypi.org/account/register/) 계정 생성
2. [TestPyPI](https://test.pypi.org/account/register/) 계정 생성 (테스트용)

#### API 토큰 생성
1. PyPI 계정 설정에서 API 토큰 생성
2. 토큰 권한을 프로젝트별로 제한 (권장)

#### 인증 설정

**방법 1: ~/.pypirc 파일 사용**
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-api-token-here
```

**방법 2: 환경변수 사용 (권장)**
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your-api-token-here
export TWINE_REPOSITORY_URL=https://upload.pypi.org/legacy/
```

## 🏗️ 패키지 빌드

### 1. 버전 업데이트

`pyproject.toml`에서 버전을 업데이트합니다:

```toml
[project]
version = "1.0.1"  # 새 버전으로 업데이트
```

### 2. 변경사항 문서화

`CHANGELOG.md`를 업데이트합니다:

```markdown
## [1.0.1] - 2024-01-15

### Added
- 새로운 기능 추가

### Fixed
- 버그 수정

### Changed
- 기존 기능 개선
```

### 3. 패키지 빌드

```bash
# 이전 빌드 파일 정리
rm -rf dist/ build/ *.egg-info/

# 새 패키지 빌드
python -m build

# 빌드 결과 확인
ls -la dist/
# ic-1.0.1-py3-none-any.whl
# ic-1.0.1.tar.gz
```

## 🧪 테스트 배포

### 1. TestPyPI에 업로드

```bash
# TestPyPI에 업로드
python -m twine upload --repository testpypi dist/*

# 또는 URL 직접 지정
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

### 2. TestPyPI에서 설치 테스트

```bash
# 새 가상환경 생성
python -m venv test-env
source test-env/bin/activate  # Linux/Mac
# test-env\Scripts\activate  # Windows

# TestPyPI에서 설치
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ic

# 설치 확인
ic --help
ic config --help
```

### 3. 기능 테스트

```bash
# 기본 명령어 테스트
ic config init
ic config validate

# AWS 명령어 테스트 (설정이 있는 경우)
ic aws ec2 info --help

# 패키지 정보 확인
pip show ic
```

## 🚀 프로덕션 배포

### 1. 최종 검증

```bash
# 테스트 실행
python -m pytest tests/

# 보안 검사
ic config security-check

# 패키지 검증
python -m twine check dist/*
```

### 2. PyPI에 업로드

```bash
# 프로덕션 PyPI에 업로드
python -m twine upload dist/*

# 업로드 확인
# https://pypi.org/project/ic/ 에서 확인
```

### 3. 설치 테스트

```bash
# 새 환경에서 설치 테스트
pip install ic

# 버전 확인
ic --version
```

## 🔄 자동화 스크립트

### 배포 스크립트 생성

`scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 IC 패키지 배포 스크립트${NC}"

# 인수 확인
if [ "$#" -ne 2 ]; then
    echo -e "${RED}사용법: $0 <version> <environment>${NC}"
    echo "예시: $0 1.0.1 test"
    echo "예시: $0 1.0.1 prod"
    exit 1
fi

VERSION=$1
ENVIRONMENT=$2

echo -e "${YELLOW}버전: $VERSION${NC}"
echo -e "${YELLOW}환경: $ENVIRONMENT${NC}"

# 버전 업데이트
echo -e "${GREEN}📝 버전 업데이트 중...${NC}"
sed -i.bak "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# 테스트 실행
echo -e "${GREEN}🧪 테스트 실행 중...${NC}"
python -m pytest tests/ -v

# 보안 검사
echo -e "${GREEN}🔒 보안 검사 중...${NC}"
python -c "
from src.ic.config.security import SecurityManager
from src.ic.config.manager import ConfigManager
config = ConfigManager()
security = SecurityManager(config.get_config())
warnings = security.validate_config_security(config.get_all())
if warnings:
    print('보안 경고:', warnings)
    exit(1)
print('보안 검사 통과')
"

# 이전 빌드 정리
echo -e "${GREEN}🧹 이전 빌드 정리 중...${NC}"
rm -rf dist/ build/ *.egg-info/

# 패키지 빌드
echo -e "${GREEN}🏗️ 패키지 빌드 중...${NC}"
python -m build

# 패키지 검증
echo -e "${GREEN}✅ 패키지 검증 중...${NC}"
python -m twine check dist/*

# 배포
if [ "$ENVIRONMENT" = "test" ]; then
    echo -e "${GREEN}📦 TestPyPI에 업로드 중...${NC}"
    python -m twine upload --repository testpypi dist/*
    echo -e "${GREEN}✅ TestPyPI 업로드 완료!${NC}"
    echo -e "${YELLOW}테스트 설치: pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ic==$VERSION${NC}"
elif [ "$ENVIRONMENT" = "prod" ]; then
    echo -e "${YELLOW}⚠️ 프로덕션 배포를 진행하시겠습니까? (y/N)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo -e "${GREEN}📦 PyPI에 업로드 중...${NC}"
        python -m twine upload dist/*
        echo -e "${GREEN}✅ PyPI 업로드 완료!${NC}"
        echo -e "${YELLOW}설치: pip install ic==$VERSION${NC}"
    else
        echo -e "${YELLOW}배포가 취소되었습니다.${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ 잘못된 환경: $ENVIRONMENT (test 또는 prod만 가능)${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 배포 완료!${NC}"
```

### 스크립트 실행 권한 부여

```bash
chmod +x scripts/deploy.sh
```

### 사용 예시

```bash
# 테스트 배포
./scripts/deploy.sh 1.0.1 test

# 프로덕션 배포
./scripts/deploy.sh 1.0.1 prod
```

## 📊 배포 후 확인사항

### 1. PyPI 페이지 확인
- https://pypi.org/project/ic/
- 패키지 정보, 설명, 의존성 확인

### 2. 설치 테스트
```bash
# 새 환경에서 설치
pip install ic

# 기능 테스트
ic --help
ic config init
```

### 3. 문서 업데이트
- README.md의 설치 명령어 확인
- 버전 정보 업데이트

## 🔧 문제 해결

### 일반적인 오류

**1. 인증 오류**
```
HTTP Error 403: Invalid or non-existent authentication information
```
- API 토큰 확인
- ~/.pypirc 파일 권한 확인 (600)

**2. 패키지 이름 충돌**
```
HTTP Error 403: The user 'username' isn't allowed to upload to project 'ic'
```
- 패키지 이름이 이미 존재하는 경우
- pyproject.toml에서 name 변경 필요

**3. 버전 충돌**
```
HTTP Error 400: File already exists
```
- 동일한 버전이 이미 업로드된 경우
- 버전 번호 증가 필요

### 디버깅 명령어

```bash
# 상세 로그와 함께 업로드
python -m twine upload --verbose dist/*

# 특정 파일만 업로드
python -m twine upload dist/ic-1.0.1-py3-none-any.whl

# 업로드 전 검증
python -m twine check dist/*
```

## 📋 체크리스트

배포 전 확인사항:

- [ ] 버전 번호 업데이트
- [ ] CHANGELOG.md 업데이트
- [ ] 테스트 통과 확인
- [ ] 보안 검사 통과
- [ ] 패키지 빌드 성공
- [ ] TestPyPI 테스트 완료
- [ ] 문서 업데이트
- [ ] Git 태그 생성 (`git tag v1.0.1`)
- [ ] GitHub 릴리스 생성

## 🔗 유용한 링크

- [PyPI](https://pypi.org/)
- [TestPyPI](https://test.pypi.org/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)