# PyPI 배포 정보

이 문서는 IC 패키지를 PyPI에 배포하기 위해 필요한 모든 정보를 정리합니다.

## 📋 필수 입력 정보

### 1. PyPI 계정 정보

#### 계정 생성
- **PyPI**: https://pypi.org/account/register/
- **TestPyPI**: https://test.pypi.org/account/register/

#### 입력 필요 정보:
```
사용자명: [입력 필요]
이메일: [입력 필요]
비밀번호: [입력 필요]
```

### 2. API 토큰

#### PyPI API 토큰 생성
1. PyPI 로그인 → Account settings → API tokens
2. "Add API token" 클릭
3. Token name: `ic-package-upload`
4. Scope: "Entire account" 또는 "Project: ic" (프로젝트 생성 후)

#### 입력 필요 정보:
```bash
# 환경변수로 설정
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-[여기에-실제-토큰-입력]

# 또는 ~/.pypirc 파일에 설정
[pypi]
username = __token__
password = pypi-[여기에-실제-토큰-입력]
```

### 3. 프로젝트 정보

#### 현재 설정된 정보 (pyproject.toml):
```toml
[project]
name = "ic"
version = "1.0.7"
description = "Multi-cloud infrastructure resource management CLI tool"
authors = [
    {name = "SangYun Kim", email = "cruiser594@gmail.com"}
]
maintainers = [
    {name = "SangYun Kim", email = "cruiser594@gmail.com"}
]
license = {text = "MIT"}
readme = "README.md"
homepage = "https://github.com/dgr009/ic"
repository = "https://github.com/dgr009/ic"
documentation = "https://github.com/dgr009/ic/blob/main/README.md"
```

#### 업데이트 필요한 정보:
```
GitHub 리포지토리 URL: [실제 리포지토리 URL로 업데이트 필요]
이메일 주소: [실제 이메일로 확인/업데이트]
```

## 🔧 설정 파일

### 1. ~/.pypirc 파일 생성

```bash
# 파일 생성
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = [여기에-PyPI-API-토큰-입력]

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = [여기에-TestPyPI-API-토큰-입력]
EOF

# 파일 권한 설정 (보안)
chmod 600 ~/.pypirc
```

### 2. 환경변수 설정 (대안)

```bash
# ~/.bashrc 또는 ~/.zshrc에 추가
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=[여기에-PyPI-API-토큰-입력]
export TWINE_REPOSITORY_URL=https://upload.pypi.org/legacy/

# 테스트용
export TWINE_TEST_REPOSITORY_URL=https://test.pypi.org/legacy/
export TWINE_TEST_PASSWORD=[여기에-TestPyPI-API-토큰-입력]
```

## 🚀 배포 명령어

### 1. 패키지 빌드

```bash
# 이전 빌드 정리
rm -rf dist/ build/ *.egg-info/

# 패키지 빌드
python -m build

# 빌드 결과 확인
ls -la dist/
```

### 2. 테스트 배포

```bash
# TestPyPI에 업로드
python -m twine upload --repository testpypi dist/*

# TestPyPI에서 설치 테스트
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ic
```

### 3. 프로덕션 배포

```bash
# PyPI에 업로드
python -m twine upload dist/*

# 설치 확인
pip install ic
```

## 📝 버전 관리

### 버전 번호 규칙 (Semantic Versioning)

```
MAJOR.MINOR.PATCH

MAJOR: 호환되지 않는 API 변경
MINOR: 하위 호환되는 기능 추가
PATCH: 하위 호환되는 버그 수정
```

### 버전 업데이트 방법

```bash
# pyproject.toml에서 버전 업데이트
sed -i 's/version = "1.0.0"/version = "1.0.1"/' pyproject.toml

# 또는 수동으로 편집
vim pyproject.toml
```

## 🔒 보안 고려사항

### 1. API 토큰 보안

```bash
# 파일 권한 설정
chmod 600 ~/.pypirc

# 환경변수 사용 (권장)
export TWINE_PASSWORD=[토큰]

# Git에 토큰 정보 커밋 금지
echo "*.pypirc" >> .gitignore
echo ".env" >> .gitignore
```

### 2. 패키지 보안

```bash
# 패키지 검증
python -m twine check dist/*

# 보안 스캔 (선택사항)
pip install safety
safety check
```

## 📊 배포 후 확인

### 1. PyPI 페이지 확인
- https://pypi.org/project/ic/
- 패키지 정보, 설명, 다운로드 통계

### 2. 설치 테스트
```bash
# 새 가상환경에서 테스트
python -m venv test-env
source test-env/bin/activate
pip install ic
ic --help
```

### 3. 문서 업데이트
- README.md 설치 명령어 확인
- 버전 정보 업데이트

## 🛠️ 자동화 스크립트

### 간단한 배포 스크립트

```bash
#!/bin/bash
# deploy.sh

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "사용법: $0 <version>"
    echo "예시: $0 1.0.1"
    exit 1
fi

echo "🚀 IC v$VERSION 배포 시작..."

# 버전 업데이트
sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# 빌드
rm -rf dist/ build/ *.egg-info/
python -m build

# 검증
python -m twine check dist/*

# 업로드
echo "TestPyPI에 업로드 중..."
python -m twine upload --repository testpypi dist/*

echo "✅ TestPyPI 업로드 완료!"
echo "테스트: pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ic==$VERSION"

read -p "프로덕션 배포를 진행하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "PyPI에 업로드 중..."
    python -m twine upload dist/*
    echo "✅ 배포 완료!"
    echo "설치: pip install ic==$VERSION"
fi
```

## 📋 체크리스트

배포 전 확인사항:

### 계정 설정
- [ ] PyPI 계정 생성
- [ ] TestPyPI 계정 생성
- [ ] API 토큰 생성 (PyPI)
- [ ] API 토큰 생성 (TestPyPI)
- [ ] ~/.pypirc 파일 설정 또는 환경변수 설정

### 프로젝트 설정
- [ ] pyproject.toml 정보 확인/업데이트
- [ ] README.md 업데이트
- [ ] CHANGELOG.md 업데이트
- [ ] 라이선스 파일 확인
- [ ] .gitignore 설정

### 배포 준비
- [ ] 테스트 실행 및 통과
- [ ] 보안 검사 통과
- [ ] 버전 번호 업데이트
- [ ] 패키지 빌드 성공
- [ ] 패키지 검증 통과

### 배포 실행
- [ ] TestPyPI 업로드
- [ ] TestPyPI에서 설치 테스트
- [ ] PyPI 업로드
- [ ] PyPI에서 설치 테스트

### 배포 후
- [ ] PyPI 페이지 확인
- [ ] 문서 업데이트
- [ ] Git 태그 생성
- [ ] GitHub 릴리스 생성

## 🔗 참고 링크

- [PyPI](https://pypi.org/)
- [TestPyPI](https://test.pypi.org/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)

## 📞 문의

배포 과정에서 문제가 발생하면:
1. 이 문서의 문제 해결 섹션 확인
2. PyPI 공식 문서 참조
3. GitHub Issues에 문의