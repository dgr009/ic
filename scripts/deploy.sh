#!/bin/bash
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# 현재 디렉토리 확인
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ pyproject.toml 파일을 찾을 수 없습니다. 프로젝트 루트에서 실행하세요.${NC}"
    exit 1
fi

# 필수 도구 확인
echo -e "${BLUE}🔧 필수 도구 확인 중...${NC}"
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python이 설치되지 않았습니다.${NC}"
    exit 1
fi

if ! python -m pip show build &> /dev/null; then
    echo -e "${YELLOW}⚠️ build 패키지가 설치되지 않았습니다. 설치 중...${NC}"
    python -m pip install build
fi

if ! python -m pip show twine &> /dev/null; then
    echo -e "${YELLOW}⚠️ twine 패키지가 설치되지 않았습니다. 설치 중...${NC}"
    python -m pip install twine
fi

# 버전 업데이트
echo -e "${GREEN}📝 버전 업데이트 중...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
else
    # Linux
    sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
fi

echo -e "${GREEN}✅ 버전이 $VERSION으로 업데이트되었습니다.${NC}"

# 테스트 실행
echo -e "${GREEN}🧪 테스트 실행 중...${NC}"
if [ -d "tests" ]; then
    if python -m pytest tests/ -v --tb=short; then
        echo -e "${GREEN}✅ 모든 테스트가 통과했습니다.${NC}"
    else
        echo -e "${RED}❌ 테스트 실패. 배포를 중단합니다.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️ tests 디렉토리를 찾을 수 없습니다. 테스트를 건너뜁니다.${NC}"
fi

# 보안 검사
echo -e "${GREEN}🔒 보안 검사 중...${NC}"
if python -c "
try:
    from src.ic.config.security import SecurityManager
    from src.ic.config.manager import ConfigManager
    config_manager = ConfigManager()
    config_manager.load_config()
    security = SecurityManager(config_manager.get_config())
    warnings = security.validate_config_security(config_manager.get_config())
    critical_warnings = [w for w in warnings if 'secret' in w.lower() and 'found in config' in w]
    if critical_warnings:
        print('❌ 중요한 보안 경고가 발견되었습니다:')
        for warning in critical_warnings:
            print(f'  - {warning}')
        exit(1)
    print('✅ 보안 검사 통과')
except Exception as e:
    print(f'⚠️ 보안 검사 중 오류: {e}')
    print('보안 검사를 건너뜁니다.')
"; then
    echo -e "${GREEN}✅ 보안 검사 통과${NC}"
else
    echo -e "${RED}❌ 보안 검사 실패. 배포를 중단합니다.${NC}"
    exit 1
fi

# 이전 빌드 정리
echo -e "${GREEN}🧹 이전 빌드 정리 중...${NC}"
rm -rf dist/ build/ *.egg-info/ src/*.egg-info/

# 패키지 빌드
echo -e "${GREEN}🏗️ 패키지 빌드 중...${NC}"
if python -m build; then
    echo -e "${GREEN}✅ 패키지 빌드 완료${NC}"
else
    echo -e "${RED}❌ 패키지 빌드 실패${NC}"
    exit 1
fi

# 빌드 결과 확인
echo -e "${BLUE}📦 빌드 결과:${NC}"
ls -la dist/

# 패키지 검증
echo -e "${GREEN}✅ 패키지 검증 중...${NC}"
if python -m twine check dist/*; then
    echo -e "${GREEN}✅ 패키지 검증 통과${NC}"
else
    echo -e "${RED}❌ 패키지 검증 실패${NC}"
    exit 1
fi

# 배포
if [ "$ENVIRONMENT" = "test" ]; then
    echo -e "${GREEN}📦 TestPyPI에 업로드 중...${NC}"
    if python -m twine upload --repository testpypi dist/*; then
        echo -e "${GREEN}✅ TestPyPI 업로드 완료!${NC}"
        echo -e "${YELLOW}테스트 설치 명령어:${NC}"
        echo -e "${BLUE}pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ic==$VERSION${NC}"
        echo -e "${YELLOW}TestPyPI 페이지: https://test.pypi.org/project/ic/$VERSION/${NC}"
    else
        echo -e "${RED}❌ TestPyPI 업로드 실패${NC}"
        exit 1
    fi
elif [ "$ENVIRONMENT" = "prod" ]; then
    echo -e "${YELLOW}⚠️ 프로덕션 배포를 진행하시겠습니까?${NC}"
    echo -e "${YELLOW}이 작업은 되돌릴 수 없습니다. (y/N)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo -e "${GREEN}📦 PyPI에 업로드 중...${NC}"
        if python -m twine upload dist/*; then
            echo -e "${GREEN}✅ PyPI 업로드 완료!${NC}"
            echo -e "${YELLOW}설치 명령어:${NC}"
            echo -e "${BLUE}pip install ic==$VERSION${NC}"
            echo -e "${YELLOW}PyPI 페이지: https://pypi.org/project/ic/$VERSION/${NC}"
            
            # Git 태그 생성
            echo -e "${GREEN}🏷️ Git 태그 생성 중...${NC}"
            if git tag "v$VERSION" && git push origin "v$VERSION"; then
                echo -e "${GREEN}✅ Git 태그 v$VERSION 생성 완료${NC}"
            else
                echo -e "${YELLOW}⚠️ Git 태그 생성 실패 (선택사항)${NC}"
            fi
        else
            echo -e "${RED}❌ PyPI 업로드 실패${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}배포가 취소되었습니다.${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ 잘못된 환경: $ENVIRONMENT (test 또는 prod만 가능)${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 배포 완료!${NC}"

# 배포 후 확인사항 안내
echo -e "${BLUE}📋 배포 후 확인사항:${NC}"
echo -e "1. PyPI 페이지에서 패키지 정보 확인"
echo -e "2. 새 환경에서 설치 테스트"
echo -e "3. 기본 명령어 동작 확인"
echo -e "4. 문서 업데이트 (README.md, CHANGELOG.md)"
echo -e "5. GitHub 릴리스 생성 (선택사항)"