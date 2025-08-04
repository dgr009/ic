# OCI Module for `ic` CLI

이 디렉토리는 `ic` CLI의 `oci` 플랫폼 관련 명령어들의 소스 코드를 포함합니다. 각 하위 디렉토리는 OCI의 특정 서비스를 담당하며, 모듈화된 구조를 가집니다.

---

## 📂 모듈 구조

- `vm/`: `ic oci vm` (인스턴스) 관련 명령어 로직
- `lb/`: `ic oci lb` (로드 밸런서) 관련 명령어 로직
- `nsg/`: `ic oci nsg` (네트워크 보안 그룹) 관련 명령어 로직
- `volume/`: `ic oci volume` (블록/부트 볼륨) 관련 명령어 로직
- `obj/`: `ic oci obj` (오브젝트 스토리지) 관련 명령어 로직
- `policy/`: `ic oci policy` (IAM 정책) 관련 명령어 로직
- `cost/`: `ic oci cost` (비용 및 크레딧) 관련 명령어 로직
- `common/`: OCI 모듈 내에서 공통으로 사용되는 유틸리티 (리전, 컴파트먼트 조회 등)
- `info/`: [Deprecated] 과거의 통합 `ic oci info` 명령어. 현재는 경고 메시지만 출력합니다.

---

## 🛠️ 주요 명령어

모든 명령어는 `ic oci <service> <command>` 형태로 실행됩니다.

| 서비스   | 명령어 | 설명 | 예시 |
|----------|--------|------|------|
| `vm`     | `info` | VM 인스턴스 정보를 병렬로 수집하여 출력 | `ic oci vm info --name "my-vm"` |
| `lb`     | `info` | 로드 밸런서 정보를 수집. 정보량이 많은 테이블이 기본. | `ic oci lb info --output tree` |
| `nsg`    | `info` | NSG Ingress 규칙을 수집. 가독성이 좋은 트리가 기본. | `ic oci nsg info --output table` |
| `volume` | `info` | 부팅 볼륨과 블록 볼륨 정보를 수집 | `ic oci volume info -c "dev-comp"` |
| `obj`    | `info` | Object Storage 버킷 정보를 수집 | `ic oci obj info -c "prod-comp"` |
| `policy` | `info` | IAM 정책 목록과 상세 구문을 분석하여 출력 | `ic oci policy info --name "AdminPolicy"` |
| `policy` | `search` | 사용자/그룹을 기준으로 연관된 IAM 정책을 검색 | `ic oci policy search`|
| `cost`   | `usage`| Usage API를 통해 지정된 기간의 비용 사용량 분석 | `ic oci cost usage --group-by COMPARTMENT_PATH`|
| `cost`   | `credit`| 현재 사용 가능한 크레딧 잔액 및 소진 내역 조회 | `ic oci cost credit` |

> ✅ `~/.oci/config` 에 유효한 프로파일 정보(`tenancy`, `user`, `region`, `key_file` 등)가 필요합니다.

---

## 🔐 IAM 권한 정책 예시

모든 기능을 원활히 사용하려면 다음과 유사한 IAM 정책이 필요할 수 있습니다.

```text
Allow group YourGroup to inspect instances in tenancy
Allow group YourGroup to read load-balancers in tenancy
Allow group YourGroup to read network-security-groups in tenancy
Allow group YourGroup to read volumes in tenancy
Allow group YourGroup to read boot-volumes in tenancy
Allow group YourGroup to read virtual-network-family in tenancy
Allow group YourGroup to read buckets in tenancy
Allow group YourGroup to read usage-reports in tenancy
Allow group YourGroup to inspect compartments in tenancy
```

---

**Author**: sykim

문의 및 개선 제안은 언제든 환영합니다!

