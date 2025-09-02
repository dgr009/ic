# Azure Services Implementation

이 디렉토리는 Azure 클라우드 서비스들의 정보 조회 기능을 구현합니다.

## 구현된 서비스

### 1. Virtual Machines (VM)
- **파일**: `vm/info.py`
- **대응 AWS 서비스**: EC2
- **기능**: VM 인스턴스 정보, 네트워크 인터페이스, 디스크, 전원 상태 조회
- **사용법**: `ic azure vm info [옵션]`

### 2. Virtual Networks (VNet)
- **파일**: `vnet/info.py`
- **대응 AWS 서비스**: VPC
- **기능**: VNet, 서브넷, 피어링, DNS 서버 정보 조회
- **사용법**: `ic azure vnet info [옵션]`

### 3. Azure Kubernetes Service (AKS)
- **파일**: `aks/info.py`
- **대응 AWS 서비스**: EKS
- **기능**: AKS 클러스터, 노드 풀, 네트워크 프로필, 애드온 정보 조회
- **사용법**: `ic azure aks info [옵션]`

### 4. Storage Accounts
- **파일**: `storage/info.py`
- **대응 AWS 서비스**: S3
- **기능**: Storage Account, Blob 컨테이너, 파일 공유, 암호화 설정 조회
- **사용법**: `ic azure storage info [옵션]`

### 5. Network Security Groups (NSG)
- **파일**: `nsg/info.py`
- **대응 AWS 서비스**: Security Groups
- **기능**: NSG 보안 규칙, 연결된 서브넷/NIC 정보 조회
- **사용법**: `ic azure nsg info [옵션]`

### 6. Load Balancers
- **파일**: `lb/info.py`
- **대응 AWS 서비스**: Load Balancer
- **기능**: Load Balancer, Frontend IP, Backend Pool, 규칙, Health Probe 정보 조회
- **사용법**: `ic azure lb info [옵션]`

### 7. Container Instances (ACI)
- **파일**: `aci/info.py`
- **대응 AWS 서비스**: ECS
- **기능**: Container Group, 컨테이너, 볼륨, 네트워크 설정 정보 조회
- **사용법**: `ic azure aci info [옵션]`

## 공통 기능

### 출력 형식
모든 서비스는 다음 출력 형식을 지원합니다:
- `table` (기본값): 테이블 형식
- `json`: JSON 형식
- `yaml`: YAML 형식
- `tree`: 트리 형식

### 필터링 옵션
- `--subscription`: 특정 구독 ID 목록 (쉼표로 구분)
- `--location`: 위치 필터 (부분 일치)
- `--resource-group`: 리소스 그룹 필터 (부분 일치)
- `--name`: 리소스 이름 필터 (부분 일치)

### 병렬 처리
- 여러 구독에 걸쳐 병렬로 정보 수집
- ThreadPoolExecutor를 사용한 고성능 처리

## 인증 설정

### 환경변수 (.env 파일)
```bash
# Service Principal 인증 (권장)
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# 구독 및 위치 설정
AZURE_SUBSCRIPTIONS=subscription-id-1,subscription-id-2
AZURE_LOCATIONS=East US,West US 2,Korea Central,Southeast Asia
```

### 지원하는 인증 방식
1. **Service Principal**: 환경변수 기반 (프로덕션 권장)
2. **Azure CLI**: `az login` 후 사용 (개발 환경)
3. **Managed Identity**: Azure 리소스에서 실행 시

## 사용 예시

```bash
# 기본 사용법
ic azure vm info
ic azure vnet info --output tree
ic azure aks info --location "Korea Central"

# 필터링
ic azure storage info --resource-group "rg-prod" --name "mystorageaccount"
ic azure nsg info --subscription "my-subscription-id"

# 출력 형식 변경
ic azure lb info --output json
ic azure aci info --output yaml

# 여러 서비스 동시 조회
ic azure vm,vnet,aks info --resource-group "rg-prod"
```

## 확장 가능성

현재 구현되지 않은 서비스들도 동일한 패턴으로 쉽게 추가할 수 있습니다:

### 추가 예정 서비스
- **Azure Database** (RDS 대응)
- **Event Hubs** (MSK 대응)
- **NAT Gateway** (NAT Gateway 대응)
- **VPN Gateway** (VPN 대응)
- **DevOps Pipelines** (CodePipeline 대응)
- **Application Gateway** (ALB 대응)
- **Azure Functions** (Lambda 대응)

### 구현 패턴
1. `azure/<service>/info.py` 파일 생성
2. `fetch_<service>_info()` 함수 구현
3. `collect_<service>_details()` 함수 구현
4. 출력 형식 함수들 구현 (`format_table_output`, `format_tree_output`)
5. CLI에 서비스 추가 (`ic/cli.py`)

## 기술적 특징

- **Azure SDK 활용**: 공식 Azure Python SDK 사용
- **에러 처리**: 권한 부족, 네트워크 오류 등 다양한 예외 상황 처리
- **로깅**: 상세한 로그 기록으로 디버깅 지원
- **성능 최적화**: 병렬 처리로 대규모 환경에서도 빠른 응답
- **사용자 친화적**: Rich 라이브러리를 활용한 아름다운 출력