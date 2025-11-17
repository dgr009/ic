# IC CLI - Smart CI Workflow Guide

## 개요

IC CLI의 CI workflow는 커밋 메시지와 변경된 파일을 기반으로 자동으로 테스트할 플랫폼을 감지합니다.

## 사용 방법

### 1. 커밋 메시지 태그 사용 (권장)

특정 플랫폼만 테스트하려면 커밋 메시지에 플랫폼 태그를 추가하세요:

```bash
# NCP만 테스트
git commit -m "[ncp] EC2 인스턴스 목록 조회 수정"

# OCI만 테스트  
git commit -m "[oci] Compartment 처리 업데이트"

# 여러 플랫폼 테스트
git commit -m "[ncp][oci] 인증 플로우 개선"

# 모든 플랫폼 테스트
git commit -m "[all] 핵심 설정 시스템 리팩토링"
```

### 2. 자동 감지

커밋 메시지에 태그가 없으면 변경된 파일을 기반으로 자동 감지:

```bash
# src/ic/platforms/ncp/ 파일 변경 → NCP 테스트
# tests/platforms/oci/ 파일 변경 → OCI 테스트
```

### 3. 기본 동작

플랫폼이 감지되지 않으면 기본 플랫폼 테스트:
- NCP (Naver Cloud Platform)
- NCPGov (Naver Cloud Platform Government)

## 지원 플랫폼 태그

| 태그 | 플랫폼 | 테스트 상태 |
|------|--------|------------|
| `[ncp]` | Naver Cloud Platform | ✅ 완전 지원 |
| `[ncpgov]` | NCP Government | ✅ 완전 지원 |
| `[oci]` | Oracle Cloud Infrastructure | ⚠️ 테스트 개발 중 |
| `[azure]` | Microsoft Azure | ⚠️ 테스트 개발 중 |
| `[aws]` | Amazon Web Services | ⚠️ 테스트 개발 중 |
| `[gcp]` | Google Cloud Platform | ⚠️ 테스트 개발 중 |
| `[ssh]` | SSH Server Management | ⚠️ 테스트 개발 중 |
| `[cf]` | CloudFlare | ⚠️ 테스트 개발 중 |

## 태그 형식

다음 형식 모두 지원:

```bash
[platform]    # 대괄호
(platform)    # 소괄호  
platform:     # 콜론
```

대소문자 구분 없음:
```bash
[ncp] = [NCP] = [Ncp]
```

## 실전 예제

### 예제 1: NCP EC2 기능 개발

```bash
# 1. NCP EC2 코드 수정
vim src/ic/platforms/ncp/ec2/info.py

# 2. 커밋 (NCP 태그 포함)
git commit -m "[ncp] GPU 인스턴스 지원 추가"

# 3. Push
git push

# 결과: NCP 테스트만 실행 (unit, integration, performance)
```

### 예제 2: 다중 플랫폼 업데이트

```bash
# 1. 인증 코드 수정
vim src/ic/core/auth.py

# 2. 커밋 (여러 플랫폼 태그)
git commit -m "[ncp][oci][aws] 인증 에러 처리 표준화"

# 3. Push
git push

# 결과: NCP, OCI, AWS 테스트 실행
```

### 예제 3: 전체 시스템 변경

```bash
# 1. 설정 시스템 수정
vim src/ic/config/manager.py

# 2. 커밋 (all 태그)
git commit -m "[all] 설정 로딩 시스템 리팩토링"

# 3. Push
git push

# 결과: 모든 플랫폼 테스트 실행
```

### 예제 4: 자동 감지

```bash
# 1. OCI 코드 수정 (태그 없이)
vim src/ic/platforms/oci/vm/info.py

# 2. 커밋 (플랫폼 태그 없음)
git commit -m "VM 인스턴스 필터링 수정"

# 3. Push
git push

# 결과: OCI 테스트 자동 실행 (변경된 파일에서 감지)
```

## 테스트 타입

각 플랫폼에 대해 3가지 테스트 실행:

1. **Unit Tests**: 빠른 단위 테스트 (모킹된 의존성)
2. **Integration Tests**: 통합 테스트 (CI에서는 모킹)
3. **Performance Tests**: 성능 벤치마크

## Python 버전

각 플랫폼은 다음 Python 버전에서 테스트:
- Python 3.11
- Python 3.12

## CI 최적화

- ✅ 영향받은 플랫폼만 테스트
- ✅ 병렬 실행 (Python 버전별)
- ✅ 테스트 파일이 없는 플랫폼 자동 스킵
- ✅ 의존성 캐싱

## 수동 실행

GitHub Actions에서 수동으로 실행:

1. Actions → "IC CLI CI Tests" 선택
2. "Run workflow" 클릭
3. 플랫폼과 테스트 타입 선택
4. "Run workflow" 클릭

## CI 스킵

CI를 완전히 스킵하려면:

```bash
git commit -m "[skip ci] 문서 업데이트"
# 또는
git commit -m "[ci skip] README 수정"
```

## 로컬 테스트

CI 감지 로직을 로컬에서 테스트:

```bash
./scripts/test-ci-detection.sh
```

## 새 플랫폼 테스트 추가

새 플랫폼에 대한 테스트를 추가하려면:

```bash
# 1. 테스트 디렉토리 생성
mkdir -p tests/platforms/{platform}/{service}/{unit,integration,performance}

# 2. 테스트 파일 추가
# tests/platforms/{platform}/{service}/unit/test_{feature}.py

# 3. 자동으로 CI에서 실행됨
```

## 문제 해결

### 내 플랫폼 테스트가 실행되지 않음

확인 사항:
1. `tests/platforms/{platform}/` 디렉토리가 있나요?
2. `test_*.py` 파일이 있나요?
3. 커밋 메시지에 플랫폼 태그를 포함했나요?
4. 변경된 파일이 `src/ic/platforms/{platform}/`에 있나요?

### 하나만 변경했는데 모든 플랫폼이 테스트됨

확인 사항:
1. `[all]` 또는 `[test-all]` 태그를 사용했나요?
2. 모든 플랫폼에 영향을 주는 핵심 파일을 변경했나요?

### 현재 테스트 상태 확인

```bash
# 플랫폼별 테스트 파일 수 확인
./scripts/test-ci-detection.sh
```

## 참고

- 전체 workflow 설정: `.github/workflows/ci-tests.yml`
- 상세 가이드: `.github/workflows/README.md`
- 테스트 감지 스크립트: `scripts/test-ci-detection.sh`
