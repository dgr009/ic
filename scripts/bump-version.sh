#!/bin/bash
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}📈 IC 버전 업데이트 스크립트${NC}"

# 인수 확인
if [ "$#" -ne 1 ]; then
    echo -e "${RED}사용법: $0 <bump_type>${NC}"
    echo "bump_type: major, minor, patch"
    echo "예시: $0 patch  # 1.0.0 -> 1.0.1"
    echo "예시: $0 minor  # 1.0.0 -> 1.1.0"
    echo "예시: $0 major  # 1.0.0 -> 2.0.0"
    exit 1
fi

BUMP_TYPE=$1

# 현재 디렉토리 확인
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ pyproject.toml 파일을 찾을 수 없습니다. 프로젝트 루트에서 실행하세요.${NC}"
    exit 1
fi

# 현재 버전 추출
CURRENT_VERSION=$(grep -E '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

if [ -z "$CURRENT_VERSION" ]; then
    echo -e "${RED}❌ 현재 버전을 찾을 수 없습니다.${NC}"
    exit 1
fi

echo -e "${BLUE}현재 버전: $CURRENT_VERSION${NC}"

# 버전 파싱
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# 새 버전 계산
case $BUMP_TYPE in
    "major")
        NEW_MAJOR=$((MAJOR + 1))
        NEW_MINOR=0
        NEW_PATCH=0
        ;;
    "minor")
        NEW_MAJOR=$MAJOR
        NEW_MINOR=$((MINOR + 1))
        NEW_PATCH=0
        ;;
    "patch")
        NEW_MAJOR=$MAJOR
        NEW_MINOR=$MINOR
        NEW_PATCH=$((PATCH + 1))
        ;;
    *)
        echo -e "${RED}❌ 잘못된 bump_type: $BUMP_TYPE (major, minor, patch만 가능)${NC}"
        exit 1
        ;;
esac

NEW_VERSION="$NEW_MAJOR.$NEW_MINOR.$NEW_PATCH"

echo -e "${GREEN}새 버전: $NEW_VERSION${NC}"

# 확인
echo -e "${YELLOW}버전을 $CURRENT_VERSION에서 $NEW_VERSION으로 업데이트하시겠습니까? (y/N)${NC}"
read -r response
if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${YELLOW}버전 업데이트가 취소되었습니다.${NC}"
    exit 0
fi

# 버전 업데이트
echo -e "${GREEN}📝 버전 업데이트 중...${NC}"

# pyproject.toml 업데이트
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
else
    # Linux
    sed -i "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
fi

# setup.py가 있다면 업데이트
if [ -f "setup.py" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/version=\"$CURRENT_VERSION\"/version=\"$NEW_VERSION\"/" setup.py
    else
        sed -i "s/version=\"$CURRENT_VERSION\"/version=\"$NEW_VERSION\"/" setup.py
    fi
    echo -e "${GREEN}✅ setup.py 버전 업데이트 완료${NC}"
fi

# __init__.py가 있다면 업데이트
if [ -f "src/ic/__init__.py" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" src/ic/__init__.py
    else
        sed -i "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" src/ic/__init__.py
    fi
    echo -e "${GREEN}✅ __init__.py 버전 업데이트 완료${NC}"
fi

echo -e "${GREEN}✅ pyproject.toml 버전 업데이트 완료${NC}"

# CHANGELOG.md 업데이트
echo -e "${GREEN}📝 CHANGELOG.md 업데이트 중...${NC}"

if [ -f "CHANGELOG.md" ]; then
    # 현재 날짜
    CURRENT_DATE=$(date +"%Y-%m-%d")
    
    # 새 버전 섹션 추가
    NEW_SECTION="## [$NEW_VERSION] - $CURRENT_DATE

### Added
- 

### Changed
- 

### Fixed
- 

### Removed
- 

"

    # CHANGELOG.md 상단에 새 섹션 추가
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "1,/^## \[/{ /^## \[/i\\
$NEW_SECTION
}" CHANGELOG.md
    else
        # Linux
        sed -i "1,/^## \[/{ /^## \[/i\\$NEW_SECTION" CHANGELOG.md
    fi
    
    echo -e "${GREEN}✅ CHANGELOG.md에 새 버전 섹션 추가 완료${NC}"
    echo -e "${YELLOW}💡 CHANGELOG.md를 편집하여 변경사항을 추가하세요.${NC}"
else
    echo -e "${YELLOW}⚠️ CHANGELOG.md 파일을 찾을 수 없습니다.${NC}"
fi

# Git 상태 확인
if git status &> /dev/null; then
    echo -e "${GREEN}📝 Git 커밋 준비 중...${NC}"
    
    # 변경된 파일들 스테이징
    git add pyproject.toml
    [ -f "setup.py" ] && git add setup.py
    [ -f "src/ic/__init__.py" ] && git add src/ic/__init__.py
    [ -f "CHANGELOG.md" ] && git add CHANGELOG.md
    
    echo -e "${YELLOW}다음 명령어로 커밋할 수 있습니다:${NC}"
    echo -e "${BLUE}git commit -m \"Bump version to $NEW_VERSION\"${NC}"
    echo -e "${BLUE}git tag \"v$NEW_VERSION\"${NC}"
    echo -e "${BLUE}git push origin main --tags${NC}"
    
    # 자동 커밋 옵션
    echo -e "${YELLOW}지금 커밋하시겠습니까? (y/N)${NC}"
    read -r commit_response
    if [[ "$commit_response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        git commit -m "Bump version to $NEW_VERSION"
        echo -e "${GREEN}✅ 버전 업데이트 커밋 완료${NC}"
        
        echo -e "${YELLOW}태그도 생성하시겠습니까? (y/N)${NC}"
        read -r tag_response
        if [[ "$tag_response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            git tag "v$NEW_VERSION"
            echo -e "${GREEN}✅ 태그 v$NEW_VERSION 생성 완료${NC}"
            
            echo -e "${YELLOW}원격 저장소에 푸시하시겠습니까? (y/N)${NC}"
            read -r push_response
            if [[ "$push_response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
                git push origin main --tags
                echo -e "${GREEN}✅ 원격 저장소 푸시 완료${NC}"
            fi
        fi
    fi
else
    echo -e "${YELLOW}⚠️ Git 저장소가 아닙니다. 수동으로 커밋하세요.${NC}"
fi

echo -e "${GREEN}🎉 버전 업데이트 완료!${NC}"
echo -e "${BLUE}새 버전: $NEW_VERSION${NC}"

# 다음 단계 안내
echo -e "${BLUE}📋 다음 단계:${NC}"
echo -e "1. CHANGELOG.md 편집하여 변경사항 추가"
echo -e "2. 테스트 실행: python -m pytest tests/"
echo -e "3. 테스트 배포: ./scripts/deploy.sh $NEW_VERSION test"
echo -e "4. 프로덕션 배포: ./scripts/deploy.sh $NEW_VERSION prod"