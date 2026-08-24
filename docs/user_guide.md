# IC (Infrastructure Commander) 사용자 종합 가이드

IC CLI는 **AWS**, **Tencent Cloud**, **GCP**, **OCI**, **Cloudflare**, **SSH** 서버 및 보안 설정을 단일 콘솔에서 통합 관리할 수 있는 멀티 클라우드 인프라 CLI 도구입니다.

---

## ⚡ 빠른 시작

```bash
# 1. 설치
pip install ic-code

# 2. 버전에 대한 정보 확인
ic --version

# 3. 설정 초기화 및 검증
ic config init
ic config show
```

---

## 📦 플랫폼별 주요 명령어

### 1. 🟧 AWS Services
- **EC2 인스턴스 조회**: `ic aws ec2 info`
- **보안 그룹 (Ingress/Egress) 분석**: `ic aws sg info` / `ic aws sg info -o tree`
- **S3 버킷 및 태그 검증**: `ic aws s3 info` / `ic aws s3 tag_check`
- **EKS & ECS 클러스터**: `ic aws eks info` / `ic aws ecs info`
- **Health Dashboard EC2 재부팅 일정 점검**:
  ```bash
  # 로컬 전 계정/프로필 자동 원터치 조회
  ic aws healthdashboard reboot

  # 명시적 전체 계정 조회
  ic aws healthdashboard reboot -A

  # 특정 계정 지정 및 마감(closed) 이력 포함 조회
  ic aws healthdashboard reboot -a prod-account,stage-account --all-status
  ```

### 2. 🟦 Tencent Cloud Services
- **CVM (가상 서버)**: `ic tencent cvm info`
- **Lighthouse (경량 서버)**: `ic tencent lighthouse info`
- **CLB (로드 밸런서/헬스체크)**: `ic tencent clb info`
- **보안 그룹 (시각화 트리)**: `ic tencent sg info -o tree`
- **VPC / NAT / TKE**: `ic tencent vpc info` / `ic tencent nat info` / `ic tencent tke info`
- **자격 증명 확인**: `ic tencent profile info`

### 3. 🟩 GCP Services
- **Compute Engine**: `ic gcp compute info`
- **Cloud Storage**: `ic gcp storage info`
- **VPC & Firewall**: `ic gcp vpc info`
- **GKE & Cloud SQL**: `ic gcp gke info` / `ic gcp sql info`

### 4. 🟥 OCI (Oracle Cloud) Services
- **VM 인스턴스 & VCN**: `ic oci vm info` / `ic oci vcn info`
- **Load Balancer & NSG**: `ic oci lb info` / `ic oci nsg info`
- **IAM 컴파트먼트 & 비용**: `ic oci compartment info` / `ic oci cost usage`

### 5. 🟧 Cloudflare & 🟦 SSH Services
- **Cloudflare Zone & DNS**: `ic cf zone info` / `ic cf dns info`
- **SSH 서버 스캔 & 탐색**: `ic ssh info`

---

## 🛡️ Security & Settings

```bash
# 코드베이스 보안 스캔 (하드코딩 시크릿 탐지)
ic security scan

# Pre-commit 훅 설치
ic security install-hooks

# 설정 검증 및 보기
ic config validate
ic config show
```
