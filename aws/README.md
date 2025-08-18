# AWS CLI 확장 기능

이 문서는 ic CLI 도구에 새롭게 추가된 AWS 기능들에 대한 사용법을 설명합니다.

## 새로 추가된 기능

### 1. EKS 클러스터 정보 조회 (`ic aws eks info`)

Amazon EKS 클러스터의 종합적인 정보를 조회합니다.

#### 사용법
```bash
# 기본 사용법
ic aws eks info

# 특정 계정과 리전 지정
ic aws eks info -a 123456789012 -r ap-northeast-2

# 클러스터 이름 필터링
ic aws eks info -n my-cluster

# JSON 형식으로 출력
ic aws eks info --output json

# YAML 형식으로 출력
ic aws eks info --output yaml
```

#### 출력 정보
- **Cluster Overview**: 클러스터 이름, 상태, 버전, 엔드포인트 등
- **Networking & Security**: VPC, 서브넷, 보안 그룹 정보
- **API Server Access**: 퍼블릭/프라이빗 엔드포인트 설정
- **Managed Node Groups**: 관리형 노드 그룹 상세 정보

### 2. Fargate 정보 조회 (`ic aws fargate info`)

EKS 또는 ECS Fargate 관련 정보를 조회합니다.

#### 사용법
```bash
# EKS Fargate 프로파일 조회 (기본값)
ic aws fargate info --cluster-name my-eks-cluster

# ECS Fargate 태스크 조회
ic aws fargate info --type ecs --cluster-name my-ecs-cluster

# 특정 계정과 리전 지정
ic aws fargate info --cluster-name my-cluster -a 123456789012 -r ap-northeast-2

# JSON 형식으로 출력
ic aws fargate info --cluster-name my-cluster --output json
```

#### 출력 정보
**EKS 모드 (기본값)**:
- Fargate 프로파일 이름, 상태
- Pod 실행 역할 ARN
- 서브넷 정보
- 네임스페이스/라벨 셀렉터

**ECS 모드**:
- 실행 중인 Fargate 태스크 목록
- 태스크 정의, 상태, CPU/메모리 정보
- 생성 시간

### 3. CodePipeline 상태 조회 (`ic aws code build/deploy`)

CodePipeline의 빌드 또는 배포 스테이지 상태를 조회합니다.

#### 사용법
```bash
# 빌드 스테이지 상태 조회
ic aws code build my-pipeline

# 배포 스테이지 상태 조회
ic aws code deploy my-pipeline

# 특정 계정과 리전 지정
ic aws code build my-pipeline -a 123456789012 -r us-east-1

# JSON 형식으로 출력
ic aws code build my-pipeline --output json
```

#### 출력 정보
- 파이프라인 이름 및 스테이지 정보
- 액션별 상태 (성공/실패/진행중 등)
- 마지막 상태 변경 시간
- 실행 ID 및 소스 리비전 정보
- 상태별 색상 및 심볼 표시

## 공통 옵션

모든 새로운 AWS 명령어는 다음 공통 옵션을 지원합니다:

### 인증 및 구성
- `-a, --account`: AWS 계정 ID (쉼표로 구분된 목록)
- `-r, --regions`: AWS 리전 (쉼표로 구분된 목록)
- 환경 변수 `AWS_PROFILE`, `AWS_REGION` 지원
- 표준 AWS 자격 증명 체인 사용

### 출력 형식
- `--output table`: 테이블 형식 (기본값)
- `--output json`: JSON 형식
- `--output yaml`: YAML 형식

### 디버깅
- `--debug`: 상세한 디버그 정보 출력

## 환경 설정

### 필수 환경 변수
```bash
# .env 파일에 설정
AWS_ACCOUNTS=123456789012,987654321098
REGIONS=ap-northeast-2,us-east-1
```

### AWS 프로파일 설정
`~/.aws/config` 파일에 프로파일을 설정해야 합니다:

```ini
[profile my-profile]
role_arn = arn:aws:iam::123456789012:role/MyRole
source_profile = default
region = ap-northeast-2
```

## 예제 사용 시나리오

### 1. EKS 클러스터 전체 현황 파악
```bash
# 모든 계정의 EKS 클러스터 정보 조회
ic aws eks info

# 특정 클러스터만 조회
ic aws eks info -n production
```

### 2. Fargate 리소스 모니터링
```bash
# EKS Fargate 프로파일 확인
ic aws fargate info --cluster-name my-eks-cluster

# ECS Fargate 태스크 상태 확인
ic aws fargate info --type ecs --cluster-name my-ecs-cluster
```

### 3. CI/CD 파이프라인 상태 확인
```bash
# 빌드 상태 확인
ic aws code build my-app-pipeline

# 배포 상태 확인
ic aws code deploy my-app-pipeline
```

## 오류 처리

### 일반적인 오류 및 해결 방법

1. **프로파일을 찾을 수 없음**
   ```
   Account 123456789012에 대한 프로파일을 찾을 수 없습니다.
   ```
   → `~/.aws/config`에 해당 계정의 프로파일을 추가하세요.

2. **권한 부족**
   ```
   AccessDeniedException: User is not authorized to perform...
   ```
   → IAM 역할에 필요한 권한을 추가하세요.

3. **리소스를 찾을 수 없음**
   ```
   Error: No stage matching 'build' found in pipeline 'my-pipeline'.
   ```
   → 파이프라인 이름을 확인하거나 스테이지 이름에 'build' 문자열이 포함되어 있는지 확인하세요.

### 필요한 IAM 권한

각 기능별로 필요한 최소 IAM 권한:

**EKS 정보 조회**:
- `eks:ListClusters`
- `eks:DescribeCluster`
- `eks:ListNodegroups`
- `eks:DescribeNodegroup`
- `eks:ListFargateProfiles`
- `eks:DescribeFargateProfile`

**ECS Fargate 조회**:
- `ecs:ListTasks`
- `ecs:DescribeTasks`

**CodePipeline 조회**:
- `codepipeline:GetPipelineState`

## 문제 해결

디버그 모드를 사용하여 상세한 로그를 확인할 수 있습니다:

```bash
ic aws eks info --debug
ic aws fargate info --cluster-name my-cluster --debug
ic aws code build my-pipeline --debug
```

로그 파일은 `logs/` 디렉토리에 저장됩니다.