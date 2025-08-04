# AWS Module for `ic` CLI

이 디렉토리는 `ic` CLI의 `aws` 플랫폼 관련 명령어들의 소스 코드를 포함합니다. 각 하위 디렉토리는 AWS의 특정 서비스를 담당하며, 모듈화된 구조를 가집니다.

---

## 📂 모듈 구조

- `ec2/`: `ic aws ec2` (EC2 인스턴스) 관련 명령어 로직
- `lb/`: `ic aws lb` (로드 밸런서) 관련 명령어 로직
- `rds/`: `ic aws rds` (RDS 데이터베이스) 관련 명령어 로직
- `s3/`: `ic aws s3` (S3 버킷) 관련 명령어 로직
- `vpc/`: `ic aws vpc` (VPC, 서브넷, 라우팅 테이블 등) 관련 명령어 로직
- `vpn/`: `ic aws vpn` (TGW, VGW, VPN 연결, 엔드포인트 등) 관련 명령어 로직

---

## 🛠️ 주요 명령어

모든 명령어는 `ic aws <service> <command>` 형태로 실행됩니다.

| 서비스 | 명령어 | 설명 | 예시 |
|---|---|---|---|
| `ec2` | `info` | EC2 인스턴스 정보를 수집하여 출력합니다. (`-v` 상세 옵션 제공) | `ic aws ec2 info -v --name "my-instance"` |
| `ec2` | `list_tags` | EC2 인스턴스의 태그 정보를 나열합니다. | `ic aws ec2 list_tags` |
| `ec2` | `tag_check` | EC2 인스턴스의 태그 규칙 준수 여부를 검사합니다. | `ic aws ec2 tag_check` |
| `lb` | `info` | 로드 밸런서의 리스너, 타겟 그룹, 헬스 체크 상태를 출력합니다. | `ic aws lb info --name "my-lb"` |
| `lb` | `list_tags` | 로드 밸런서의 태그 정보를 나열합니다. | `ic aws lb list_tags` |
| `lb` | `tag_check` | 로드 밸런서의 태그 규칙 준수 여부를 검사합니다. | `ic aws lb tag_check` |
| `rds` | `info` | RDS 인스턴스 및 클러스터의 상세 정보를 출력합니다. | `ic aws rds info --name "my-db"` |
| `rds` | `list_tags` | RDS의 태그 정보를 나열합니다. | `ic aws rds list_tags` |
| `rds` | `tag_check` | RDS의 태그 규칙 준수 여부를 검사합니다. | `ic aws rds tag_check` |
| `s3` | `info` | S3 버킷의 접근 설정, 스토리지 티어, 용량, 객체 수를 출력합니다. | `ic aws s3 info --name "my-bucket"` |
| `s3` | `list_tags` | S3 버킷의 태그 정보를 나열합니다. | `ic aws s3 list_tags` |
| `s3` | `tag_check` | S3 버킷의 태그 규칙 준수 여부를 검사합니다. | `ic aws s3 tag_check` |
| `vpc` | `info` | VPC, 서브넷, 라우팅 테이블 등 네트워크 구성 정보를 출력합니다. | `ic aws vpc info --name "my-vpc"` |
| `vpc` | `list_tags` | VPC 관련 리소스의 태그 정보를 나열합니다. | `ic aws vpc list_tags` |
| `vpc` | `tag_check` | VPC 관련 리소스의 태그 규칙 준수 여부를 검사합니다. | `ic aws vpc tag_check` |
| `vpn` | `info` | TGW, VGW, VPN 연결, VPC 엔드포인트 정보를 출력합니다. | `ic aws vpn info` |

> ✅ `~/.aws/config` 및 `~/.aws/credentials`에 유효한 프로파일 정보가 필요합니다.
> ✅ 대부분의 명령어는 공통적으로 `-a, --account` 와 `-r, --regions` 옵션을 지원합니다.

---

**Author**: sykim