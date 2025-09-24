# IC CLI Test Suite

## 📁 테스트 구조 (정리됨 - 2025.09.24)

### 핵심 테스트 디렉토리

#### `platforms/` - 플랫폼별 테스트
```
platforms/
├── aws/           # AWS 서비스 테스트
├── azure/         # Azure 서비스 테스트  
├── gcp/           # GCP 서비스 테스트
├── ncp/           # NCP 서비스 테스트
│   ├── ec2/
│   │   ├── unit/           # 단위 테스트
│   │   ├── integration/    # 통합 테스트
│   │   └── performance/    # 성능 테스트
│   └── s3/
├── ncpgov/        # NCP Government 테스트
└── oci/           # OCI 서비스 테스트
```

#### `validation/` - 검증 테스트 (최신)
- `end_to_end_cli_validation.py` - CLI 전체 검증
- `ci_cd_pipeline_validation.py` - CI/CD 파이프라인 검증
- `security_performance_validation.py` - 보안 및 성능 검증
- `run_all_validations.py` - 모든 검증 실행

#### `security/` - 보안 테스트
- `test_basic_security.py` - 기본 보안 테스트
- `test_configuration_security.py` - 설정 보안 테스트
- `test_credential_handling.py` - 자격증명 처리 테스트
- `test_git_security_hooks.py` - Git 보안 훅 테스트
- `test_sensitive_data_masking.py` - 민감 데이터 마스킹 테스트

#### `integration/` - 통합 테스트 (정리됨)
- `test_basic_integration.py` - 기본 통합 테스트
- `test_cli_integration.py` - CLI 통합 테스트
- `test_config_migration.py` - 설정 마이그레이션 테스트
- `test_ncp_service_integration.py` - NCP 서비스 통합 테스트
- `test_security_cli_integration.py` - 보안 CLI 통합 테스트

#### `unit/` - 단위 테스트 (정리됨)
- `test_config_manager.py` - 설정 관리자 테스트
- `test_ncp_client.py` - NCP 클라이언트 테스트
- `test_ncpgov_client.py` - NCP Gov 클라이언트 테스트
- `test_security_manager.py` - 보안 관리자 테스트
- `test_ic_logger.py` - 로거 테스트

#### `ci/` - CI/CD 테스트
- `run_ci_tests.py` - CI 테스트 실행기
- `environment.py` - CI 환경 설정
- `mock_configs.py` - 모의 설정
- `fallback_configs.py` - 대체 설정

#### `performance/` - 성능 테스트
- `test_ncp_performance.py` - NCP 성능 테스트
- `test_gcp_performance.py` - GCP 성능 테스트
- `benchmark_runner.py` - 벤치마크 실행기

### 핵심 실행 파일들

#### `comprehensive_test_runner.py`
모든 테스트를 종합적으로 실행하는 메인 테스트 러너

#### `platform_test_runner.py`
플랫폼별 테스트를 실행하는 고급 테스트 러너

#### `Makefile`
테스트 빌드 및 실행을 위한 Make 파일

## 🚀 테스트 실행 방법

### 전체 검증 실행
```bash
python tests/validation/run_all_validations.py
```

### 플랫폼별 테스트 실행
```bash
python tests/platform_test_runner.py --platforms ncp --test-types unit
```

### CI 테스트 실행
```bash
python tests/ci/run_ci_tests.py --platform ncp --test-type unit
```

### Make를 사용한 테스트 실행
```bash
# 모든 테스트
make test-all

# 플랫폼별 테스트
make test-ncp
make test-aws

# 테스트 타입별
make test-unit
make test-integration
```

## 📊 테스트 결과

### 최근 검증 결과 (2025.09.24)
- ✅ End-to-End CLI Validation: 100% (63/63 tests)
- ✅ CI/CD Pipeline Validation: 100% (23/23 tests)
- ✅ Security & Performance Validation: 100% (10/10 tests)

**총 성공률: 100% (96/96 tests)**

## 🗂️ 백업된 파일들

정리 과정에서 중복되거나 오래된 파일들은 `backup/project_cleanup_20250924_183633/`에 백업되었습니다:

- 오래된 테스트 파일들
- 중복된 실행 스크립트들
- 과거 검증 리포트들
- 임시 설정 파일들

## 📝 테스트 작성 가이드

### 새로운 플랫폼 테스트 추가
1. `tests/platforms/{platform}/` 디렉토리 생성
2. `unit/`, `integration/`, `performance/` 하위 디렉토리 생성
3. 테스트 파일은 `test_*.py` 형식으로 명명

### 테스트 카테고리
- **Unit**: 개별 함수/클래스 테스트
- **Integration**: 컴포넌트 간 통합 테스트  
- **Performance**: 성능 및 부하 테스트
- **Security**: 보안 관련 테스트
- **Validation**: 전체 시스템 검증

## 🔧 유지보수

### 정기 정리 작업
- 중복된 테스트 파일 확인
- 오래된 검증 리포트 정리
- 캐시 파일 정리 (`__pycache__` 디렉토리)
- 사용하지 않는 모의 데이터 정리

### 백업 정책
- 정리 작업 시 항상 백업 생성
- 백업 폴더는 `backup/project_cleanup_{timestamp}/` 형식
- 백업 매니페스트 파일로 변경사항 추적