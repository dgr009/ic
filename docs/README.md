# IC 프로젝트 문서

이 디렉토리는 IC 프로젝트의 모든 문서를 체계적으로 정리한 곳입니다.

## 📁 문서 구조

### AWS 관련 문서 (`aws/`)
- **[AWS CLI 확장 기능 사용법](aws/README.md)** - AWS 모듈 사용 가이드
- **[AWS CLI PRD](aws/aws_cli_prd.md)** - AWS CLI 확장 기능 제품 요구사항 명세서
- **[AWS 구현 요약](aws/AWS_IMPLEMENTATION_SUMMARY.md)** - AWS 기능 구현 완료 보고서

### 개발 관련 문서 (`development/`)
- **[AWS 모듈 테스트](development/test_aws_modules.py)** - AWS 모듈 임포트 테스트 스크립트

## 📖 주요 문서 링크

### 시작하기
- [메인 README](../README.md) - 프로젝트 전체 개요 및 사용법
- [환경 설정 예제](../env.example) - 환경 변수 설정 템플릿

### AWS 기능
- [AWS 서비스 사용법](aws/README.md) - ECS, EKS, Fargate, CodePipeline 등 AWS 서비스 사용 가이드
- [AWS 구현 상세](aws/AWS_IMPLEMENTATION_SUMMARY.md) - 구현된 AWS 기능들의 기술적 세부사항

### 개발 가이드
- [개발 환경 설정](.cursor/rules.md) - 프로젝트 엔지니어링 핸드북 및 AI 협업 규칙

## 🔍 문서 찾기

### 사용법을 알고 싶다면
1. [메인 README](../README.md) - 전체적인 사용법
2. [AWS 사용 가이드](aws/README.md) - AWS 서비스별 상세 사용법

### 구현 세부사항을 알고 싶다면
1. [AWS 구현 요약](aws/AWS_IMPLEMENTATION_SUMMARY.md) - 구현된 기능들의 기술적 세부사항
2. [AWS PRD](aws/aws_cli_prd.md) - 원본 요구사항 명세서

### 개발에 참여하고 싶다면
1. [엔지니어링 핸드북](../.cursor/rules.md) - 코딩 표준 및 협업 규칙
2. [개발 테스트](development/test_aws_modules.py) - 모듈 테스트 방법

## 📝 문서 기여

문서를 수정하거나 추가하고 싶다면:
1. 해당 카테고리의 폴더에 문서 추가
2. 이 README.md 파일에 링크 추가
3. 메인 README.md에 필요시 링크 추가

---

**마지막 업데이트**: 2025-09-01  
**관리자**: SangYun Kim (cruiser594@gmail.com)