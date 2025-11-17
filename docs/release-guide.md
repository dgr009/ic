# IC CLI Release Guide

## 릴리스 프로세스

### 1. 버전 업데이트

두 파일의 버전을 동기화해야 합니다:

```bash
# src/ic/__init__.py
__version__ = "1.1.10"

# pyproject.toml
version = "1.1.10"
```

### 2. CHANGELOG 업데이트

`.local-docs/CHANGELOG.md`에 변경사항 추가:

```markdown
## [1.1.10] - 2025-11-17

### Added
- 새로운 기능들...

### Changed
- 변경된 사항들...

### Fixed
- 수정된 버그들...
```

### 3. 로컬 빌드 테스트

```bash
# 빌드 아티팩트 정리
rm -rf dist/ build/ src/ic_code.egg-info/

# 패키지 빌드
python -m build

# 빌드 결과 확인
ls -lh dist/

# 패키지 검증
twine check dist/*
```

### 4. 변경사항 커밋 및 푸시

```bash
# 변경사항 확인
git status

# 커밋
git add src/ic/__init__.py pyproject.toml .local-docs/CHANGELOG.md
git commit -m "Release v1.1.10: Smart CI platform detection and improvements"

# 푸시
git push origin main
```

### 5. GitHub Release 생성

#### 방법 1: GitHub 웹 인터페이스

1. https://github.com/dgr009/ic/releases/new 접속
2. "Choose a tag" → `v1.1.10` 입력 (새 태그 생성)
3. Release title: `v1.1.10`
4. Description: CHANGELOG 내용 복사
5. "Publish release" 클릭

#### 방법 2: Git 태그 + GitHub CLI

```bash
# 태그 생성
git tag -a v1.1.10 -m "Release v1.1.10: Smart CI platform detection"

# 태그 푸시
git push origin v1.1.10

# GitHub CLI로 release 생성 (선택사항)
gh release create v1.1.10 \
  --title "v1.1.10" \
  --notes-file .local-docs/CHANGELOG.md
```

### 6. 자동 배포 확인

GitHub Release가 생성되면 자동으로:

1. `.github/workflows/publish-to-pypi.yml` workflow 실행
2. 패키지 빌드
3. PyPI에 자동 업로드 (Trusted Publishing 사용)

진행 상황 확인:
- https://github.com/dgr009/ic/actions

### 7. PyPI 배포 확인

```bash
# PyPI에서 새 버전 확인
pip index versions ic-code

# 또는 웹에서 확인
# https://pypi.org/project/ic-code/
```

### 8. 설치 테스트

```bash
# 새 가상환경에서 테스트
python -m venv test-env
source test-env/bin/activate

# 최신 버전 설치
pip install --upgrade ic-code

# 버전 확인
ic --version
# 또는
python -c "import ic; print(ic.__version__)"

# 정리
deactivate
rm -rf test-env
```

## 버전 관리 규칙

### Semantic Versioning

`MAJOR.MINOR.PATCH` (예: 1.1.10)

- **MAJOR**: 호환되지 않는 API 변경
- **MINOR**: 하위 호환되는 기능 추가
- **PATCH**: 하위 호환되는 버그 수정

### 버전 증가 가이드

```bash
# 버그 수정만
1.1.9 → 1.1.10

# 새 기능 추가 (하위 호환)
1.1.10 → 1.2.0

# Breaking changes
1.2.0 → 2.0.0
```

## 문제 해결

### PyPI 업로드 실패: "File already exists"

**원인**: 같은 버전을 다시 업로드하려고 시도

**해결**:
```bash
# 버전 증가
# src/ic/__init__.py와 pyproject.toml 모두 업데이트
__version__ = "1.1.11"
version = "1.1.11"

# 커밋 및 새 release 생성
```

### 버전 불일치

**확인**:
```bash
# pyproject.toml 버전
grep "^version" pyproject.toml

# __init__.py 버전
grep "__version__" src/ic/__init__.py
```

**두 파일의 버전이 반드시 일치해야 합니다!**

### GitHub Actions 실패

**확인 사항**:
1. Workflow 로그 확인: https://github.com/dgr009/ic/actions
2. PyPI Trusted Publishing 설정 확인
3. 빌드 에러 확인 (의존성, 문법 등)

### 로컬 빌드 실패

```bash
# 빌드 도구 업데이트
pip install --upgrade build twine setuptools wheel

# 캐시 정리
rm -rf dist/ build/ *.egg-info src/*.egg-info

# 다시 빌드
python -m build
```

## 체크리스트

릴리스 전 확인사항:

- [ ] `src/ic/__init__.py` 버전 업데이트
- [ ] `pyproject.toml` 버전 업데이트
- [ ] 두 파일의 버전이 일치하는지 확인
- [ ] `.local-docs/CHANGELOG.md` 업데이트
- [ ] 로컬 빌드 테스트 성공
- [ ] `twine check` 통과
- [ ] 변경사항 커밋 및 푸시
- [ ] GitHub Release 생성
- [ ] GitHub Actions 성공 확인
- [ ] PyPI에 새 버전 확인
- [ ] 설치 테스트 성공

## 빠른 릴리스 스크립트

```bash
#!/bin/bash
# scripts/quick-release.sh

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: ./scripts/quick-release.sh 1.1.10"
    exit 1
fi

echo "🚀 Releasing version $VERSION"

# 버전 업데이트
sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/ic/__init__.py
sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# 빌드 테스트
rm -rf dist/ build/ *.egg-info
python -m build
twine check dist/*

echo "✅ Build successful!"
echo ""
echo "Next steps:"
echo "1. Update .local-docs/CHANGELOG.md"
echo "2. git add src/ic/__init__.py pyproject.toml .local-docs/CHANGELOG.md"
echo "3. git commit -m 'Release v$VERSION'"
echo "4. git push origin main"
echo "5. git tag -a v$VERSION -m 'Release v$VERSION'"
echo "6. git push origin v$VERSION"
echo "7. Create GitHub Release at https://github.com/dgr009/ic/releases/new"
```

## 참고

- PyPI 프로젝트: https://pypi.org/project/ic-code/
- GitHub 저장소: https://github.com/dgr009/ic
- Trusted Publishing 가이드: https://docs.pypi.org/trusted-publishers/
