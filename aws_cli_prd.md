ic CLI AWS 확장 기능 제품 요구사항 명세서 (PRD)


1.0 서론 및 핵심 원칙

본 문서는 ic 커맨드 라인 인터페이스(CLI) 내에 새로운 AWS 모듈을 추가하기 위한 기술적 요구사항을 정의합니다. 이 기능의 목표는 DevOps 엔지니어 및 클라우드 개발자에게 AWS 인프라에 대한 빠르고, 집약적이며, 맥락에 맞는 정보를 제공하여 AWS 관리 콘솔 방문이나 여러 AWS CLI 명령어를 실행하는 번거로움을 줄이는 것입니다.

1.1 문서의 목적 및 범위

본 제품 요구사항 명세서(PRD)는 ic 툴에 추가될 AWS EKS, Fargate, CodePipeline 정보 조회 기능의 기능적 요구사항을 상세히 기술합니다. 이 문서는 개발팀이 기능을 구현하는 데 필요한 유일한 기술적 참조 자료(single source of truth) 역할을 합니다.

1.2 ic 프로젝트 접근 불가 상황에 대한 고려사항

ic 프로젝트의 공식 GitHub 리포지토리(https://github.com/dgr009/ic)에 접근할 수 없는 상태임이 확인되었습니다.1 이로 인해 기존 코드베이스, 프로그래밍 언어, 라이브러리, 아키텍처 패턴 등을 분석하는 것이 불가능합니다.
따라서 본 문서에 정의된 요구사항은 외부 의존성 없이 자체적으로 완결성을 가집니다. 개발팀은 내부적으로 접근 가능한 기존 ic 프레임워크에 이 기능을 통합하거나, 본 명세서에 정의된 인터페이스를 준수하는 새로운 프레임워크 내에서 이 명령어를 구현해야 합니다. 본 문서는 명령어 파싱, 플래그 처리, 포맷팅된 출력 생성이 가능한 기본 CLI 프레임워크가 존재한다고 가정합니다.

1.3 핵심 기능 원칙 (모든 명령어에 적용)

새롭게 추가될 모든 AWS 관련 명령어는 다음의 핵심 원칙을 일관되게 준수해야 합니다.

1.3.1 인증 및 구성

툴은 반드시 표준 AWS SDK 자격 증명 체인(credential chain)을 활용해야 합니다. 이는 환경 변수(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN), 공유 자격 증명 파일(~/.aws/credentials), 그리고 EC2 인스턴스 또는 EKS 파드를 위한 IAM 역할(IRSA) 순서의 우선순위를 따릅니다.
툴은 AWS_REGION 및 AWS_PROFILE 환경 변수를 인식하여 사용자가 의도한 정확한 AWS 환경을 대상으로 명령을 실행해야 합니다.

1.3.2 출력 형식

모든 명령어는 글로벌 플래그인 --output을 통해 최소 세 가지 출력 형식을 지원해야 합니다. (예: ic aws eks info my-cluster --output json)
table (기본값): 사람이 쉽게 읽을 수 있도록 잘 정돈된 ASCII 테이블 형식입니다. 대화형 사용을 위한 기본 출력입니다.
json: 표준 JSON 형식입니다. 다른 툴과의 연동이나 스크립팅을 위해 제공됩니다. JSON의 구조는 내부적으로 집계된 데이터 구조를 충실히 반영해야 합니다.
yaml: 표준 YAML 형식입니다. 스크립팅 환경에서 JSON보다 가독성이 높은 대안으로 제공됩니다.

1.3.3 오류 처리 및 상세 로깅

툴은 명확하고 사용자 친화적인 오류 메시지를 제공해야 합니다. AWS SDK에서 발생하는 예외(예: AccessDeniedException, ResourceNotFoundException)는 적절히 포착하여 사용자가 이해하기 쉬운 형태로 변환 후 출력해야 합니다.
글로벌 --debug 플래그를 구현해야 합니다. 이 플래그가 활성화되면, 문제 해결을 돕기 위해 실행된 특정 AWS API 호출, 원본 응답(raw response) 등 상세한 로그를 표준 출력으로 표시해야 합니다.

2.0 기능 명세: EKS 클러스터 정보 (ic aws eks info)

이 기능은 사용자가 지정한 Amazon EKS 클러스터에 대한 핵심 정보를 종합하여 한눈에 파악할 수 있는 통합 뷰를 제공합니다. 이는 일반적으로 여러 번의 AWS CLI 호출을 통해 얻을 수 있는 정보를 단일 명령어로 집계하여 보여주는 것을 목표로 합니다.

2.1 명령어 구문 및 인수

구문: ic aws eks info

2.2 핵심 로직 및 데이터 집계

유용한 EKS 정보 요약은 단일 API 호출의 결과를 그대로 출력하는 것이 아닙니다. 컨트롤 플레인과 데이터 플레인(워커 노드)의 상태를 종합적으로 보여주기 위해 여러 API 호출 결과를 통합하는 과정이 필수적이며, 이것이 이 명령어의 핵심 가치입니다.
이러한 통합 정보를 생성하기 위한 논리적 흐름은 다음과 같습니다.
먼저, 클러스터의 핵심 정보를 가져오기 위해 EKS DescribeCluster API를 호출합니다. 이는 aws eks describe-cluster 명령어에 해당하며, 컨트롤 플레인의 상태, 버전, VPC 구성 등의 정보를 제공합니다.
다음으로, 클러스터에 연결된 워커 노드 정보를 수집하기 위해 클러스터 이름을 인수로 사용하여 ListNodegroups API(aws eks list-nodegroups)를 호출합니다. 이 호출은 해당 클러스터에 속한 모든 관리형 노드 그룹의 이름 목록을 반환합니다.
반환된 노드 그룹 이름 목록을 순회하며, 각 이름에 대해 DescribeNodegroup API(aws eks describe-nodegroup)를 호출하여 개별 노드 그룹의 상세 정보를 가져옵니다.
이러한 DescribeCluster → ListNodegroups → DescribeNodegroup 반복 호출의 순차적 실행을 통해 수집된 모든 데이터를 하나의 일관된 출력으로 통합하여 사용자에게 제공합니다.
옵션으로 -r(리전) -a(어카운트) --name 등을 활용하여 필터링을 할수 있도록해

2.3 데이터 표현 및 출력 구조

출력은 정보의 명확성을 위해 다음과 같은 논리적 섹션으로 구성되어야 합니다.

2.3.1 섹션: Cluster Overview

EKS 컨트롤 플레인에 대한 기본적인 정보를 표시합니다.
필드: Cluster Name, Status, Kubernetes Version, Version, Endpoint, Created At

2.3.2 섹션: Networking & Security

클러스터와 연관된 VPC 구성 정보를 표시합니다.
필드: VPC ID, Subnet IDs (목록 형식), Cluster Security Group ID

2.3.3 섹션: API Server Access

API 서버 엔드포인트 접근 제어 설정을 표시합니다.
필드: Public Access (Enabled/Disabled), Public Access CIDRs, Private Access (Enabled/Disabled)

2.3.4 섹션: Managed Node Groups

클러스터에 연결된 모든 관리형 노드 그룹의 요약 정보를 테이블 형식으로 표시합니다. 만약 관리형 노드 그룹이 없다면, "No managed node groups found." 메시지를 출력해야 합니다.
테이블 컬럼: Node Group Name, Status, Instance Type(s), Scaling (Min/Max/Desired), Kubernetes Version, AMI Release Version

2.4 테이블 정의: EKS 클러스터 정보 필드 매핑

다음 표는 출력에 표시될 각 필드와 해당 데이터를 가져오기 위한 AWS API 호출 및 응답 내 키(Key)를 명확하게 매핑합니다. 이는 개발 과정에서의 모호성을 제거하고 정확한 구현을 보장하기 위한 가이드입니다.
표시 필드
AWS API 호출
응답 내 JMESPath/키
설명
Cluster Overview






Cluster Name
DescribeCluster
cluster.name
EKS 클러스터의 이름
ARN
DescribeCluster
cluster.arn
클러스터의 Amazon Resource Name
Status
DescribeCluster
cluster.status
현재 상태 (예: ACTIVE, CREATING)
Kubernetes Version
DescribeCluster
cluster.version
컨트롤 플레인의 쿠버네티스 버전
Platform Version
DescribeCluster
cluster.platformVersion
EKS 클러스터의 플랫폼 버전
Endpoint URL
DescribeCluster
cluster.endpoint
클러스터의 API 서버 엔드포인트
Created At
DescribeCluster
cluster.createdAt
클러스터 생성 타임스탬프
Networking & Security






VPC ID
DescribeCluster
cluster.resourcesVpcConfig.vpcId
클러스터 리소스가 사용하는 VPC ID
Subnet IDs
DescribeCluster
cluster.resourcesVpcConfig.subnetIds
클러스터가 사용하는 서브넷 목록
Cluster Security Group ID
DescribeCluster
cluster.resourcesVpcConfig.clusterSecurityGroupId
컨트롤 플레인을 위한 기본 보안 그룹
API Server Access






Public Access
DescribeCluster
cluster.resourcesVpcConfig.endpointPublicAccess
퍼블릭 엔드포인트 활성화 여부 (boolean)
Public Access CIDRs
DescribeCluster
cluster.resourcesVpcConfig.publicAccessCidrs
퍼블릭 엔드포인트에 접근 가능한 CIDR 목록
Private Access
DescribeCluster
cluster.resourcesVpcConfig.endpointPrivateAccess
프라이빗 엔드포인트 활성화 여부 (boolean)
Managed Node Groups






Node Group Name
DescribeNodegroup
nodegroup.nodegroupName
관리형 노드 그룹의 이름
Status
DescribeNodegroup
nodegroup.status
노드 그룹의 현재 상태
Instance Type(s)
DescribeNodegroup
nodegroup.instanceTypes
노드 그룹에서 사용하는 인스턴스 타입 목록
Scaling
DescribeNodegroup
nodegroup.scalingConfig
minSize, maxSize, desiredSize의 조합
Kubernetes Version
DescribeNodegroup
nodegroup.version
노드의 쿠버네티스 버전
AMI Release Version
DescribeNodegroup
nodegroup.releaseVersion
EKS 최적화 AMI 버전


3.0 기능 명세: Fargate 정보 (ic aws fargate info)

이 기능은 "Fargate 정보" 조회라는 사용자의 요구사항을 해결합니다. Fargate는 EKS와 ECS 모두를 위한 서버리스 컴퓨팅 엔진이므로, 명령어는 이 두 가지 컨텍스트를 명확하게 구분하여 처리할 수 있도록 설계되어야 합니다.

3.1 설계 방향: 모호성 해결

ic aws fargate info라는 명령어는 그 자체로 모호성을 내포합니다. Fargate는 독립적인 서비스가 아니라 EKS와 ECS에서 컨테이너를 실행하는 '실행 유형(launch type)'이기 때문입니다.7 EKS 컨텍스트에서는
Fargate 프로파일에 대한 정보를 의미하고 9, ECS 컨텍스트에서는
Fargate 실행 유형으로 실행 중인 태스크에 대한 정보를 의미합니다.10
견고한 CLI 툴은 사용자에게 이러한 컨텍스트를 명확하게 지정할 수 있는 직관적인 방법을 제공해야 합니다. 이를 위해 표준 CLI 관례인 --type 플래그를 도입하여 두 컨텍스트를 구분합니다. 기본 동작은 본 PRD의 다른 기능들과의 일관성을 위해 EKS 컨텍스트로 설정하되, --type ecs 플래그를 통해 ECS 컨텍스트로 쉽게 전환할 수 있도록 합니다.

3.2 주 명령어: EKS Fargate 프로파일 조회


3.2.1 명령어 구문 및 인수

구문: ic aws fargate info --cluster-name <eks-cluster-name>
--cluster-name (필수): Fargate 프로파일을 조회할 EKS 클러스터의 이름입니다.

3.2.2 핵심 로직

툴은 주어진 클러스터 이름에 대해 ListFargateProfiles API(aws eks list-fargate-profiles)를 호출하여 해당 클러스터에 속한 모든 Fargate 프로파일의 이름 목록을 가져옵니다.11
이 목록을 순회하며 각 프로파일 이름에 대해 DescribeFargateProfile API(aws eks describe-fargate-profile)를 호출하여 상세 정보를 수집합니다.12

3.2.3 데이터 표현

출력은 Fargate 프로파일들을 요약하는 테이블 형식이어야 합니다.
테이블 컬럼: Profile Name, Status, Pod Execution Role ARN, Subnets, Selectors (Namespace/Labels)

3.3 명령어 변형: ECS Fargate 태스크 조회


3.3.1 명령어 구문 및 인수

구문: ic aws fargate info --type ecs --cluster-name <ecs-cluster-name>
--type ecs (필수): 이 플래그는 명령어의 컨텍스트를 ECS로 전환합니다.
--cluster-name (필수): 태스크를 조회할 ECS 클러스터의 이름입니다.

3.3.2 핵심 로직

툴은 ListTasks API(aws ecs list-tasks)를 호출하되, --launch-type FARGATE 필터와 --cluster 필터를 함께 사용하여 지정된 ECS 클러스터에서 실행 중인 Fargate 태스크의 ARN 목록을 가져옵니다.10
태스크가 발견되면, 반환된 태스크 ARN 목록을 가지고 DescribeTasks API(aws ecs describe-tasks)를 호출하여 각 태스크의 상세 정보를 조회합니다.15

3.3.3 데이터 표현

출력은 실행 중인 Fargate 태스크들을 요약하는 테이블 형식이어야 합니다.
테이블 컬럼: Task ARN, Task Definition, Last Status, Desired Status, CPU, Memory, Created At

4.0 기능 명세: CodePipeline 상태 (ic aws code...)

이 기능은 사용자가 전체 파이프라인 상태를 직접 파싱할 필요 없이 CI/CD의 핵심 단계(Build, Deploy) 상태를 신속하게 확인할 수 있는 방법을 제공합니다.

4.1 명령어 구문 및 인수

ic aws code build <pipeline-name>
ic aws code deploy <pipeline-name>
<pipeline-name> (필수): 상태를 조회할 CodePipeline의 이름입니다.

4.2 설계 방향: 의미 기반 스테이지 매칭

사용자가 입력한 build나 deploy와 같은 명령어는 CodePipeline API에 내재된 개념이 아닌, 의미론적 의도를 담고 있습니다. 이 기능의 핵심 가치는 파이프라인 구조를 지능적으로 분석하여 일반적인 명명 규칙에 기반해 사용자가 관심 있는 스테이지를 찾아내는 능력에 있습니다.
이러한 기능 구현을 위한 논리적 단계는 다음과 같습니다.
GetPipelineState API(aws codepipeline get-pipeline-state)는 파이프라인의 모든 스테이지에 대한 상태 정보를 반환합니다.16
사용자는 전체 상태가 아닌, '빌드 스테이지'와 같이 특정 의미를 가진 스테이지의 상태를 원합니다.
파이프라인의 스테이지 이름은 사용자가 정의하며, API에는 '빌드 타입' 스테이지만 필터링하는 기능이 없습니다.
따라서, 툴은 클라이언트 측에서 휴리스틱(heuristic) 기반의 필터링을 구현해야 합니다. API 응답으로 받은 각 스테이지의 stageName 필드를 스캔하여, build 명령어의 경우 'build'라는 문자열(대소문자 구분 없음)을 포함하는 스테이지를, deploy 명령어의 경우 'deploy' 또는 'deployment'를 포함하는 스테이지를 찾습니다.
이러한 휴리스틱 기반 매칭 로직은 사용자의 의도를 실제 API 데이터에 대한 구체적인 쿼리로 변환하는 핵심적인 역할을 합니다. 본 명세서는 일치하는 스테이지가 없을 때(오류 메시지)와 여러 스테이지가 일치할 때(모두 표시)의 동작을 명확히 정의해야 합니다.

4.3 핵심 로직

두 명령어 모두 먼저 지정된 파이프라인 이름으로 GetPipelineState API를 호출합니다.16
그 후, 아래에 정의된 스테이지 이름 매칭 휴리스틱에 따라 API 응답의 stageStates 배열을 필터링합니다.
스테이지 이름 매칭 휴리스틱:
ic aws code build: stageName에 "build" 문자열을 포함하는 스테이지를 필터링합니다 (대소문자 미구분).
ic aws code deploy: stageName에 "deploy" 또는 "deployment" 문자열을 포함하는 스테이지를 필터링합니다 (대소문자 미구분).
일치하는 스테이지가 없으면, "Error: No stage matching '[build|deploy]' found in pipeline ''." 형식의 메시지를 출력하고 종료합니다.
하나 이상의 스테이지가 일치하면, 각 스테이지의 상세 정보를 아래 형식에 맞춰 출력합니다.

4.4 데이터 표현

AWS 콘솔은 색상을 사용하여 상태를 한눈에 전달하는 방식을 채택하고 있습니다.18 현대적인 CLI 툴은 이러한 모범 사례를 따라 사용자 경험을 향상시켜야 합니다. 출력은 심볼과 색상을 함께 사용하여 상태를 즉각적으로 인지할 수 있도록 해야 합니다.
일치하는 각 스테이지의 출력은 다음과 같은 간결한 요약 정보를 포함해야 합니다.
Status: 색상으로 구분된 심볼과 텍스트 (예: ✓ Succeeded, ✗ Failed, → InProgress)
Pipeline Name: 파이프라인의 이름
Stage Name: 매칭된 스테이지의 이름
Last Status Change: 해당 스테이지의 마지막 액션 상태가 변경된 시점의 타임스탬프
Source Revision: 실행을 트리거한 소스 아티팩트의 커밋 ID 또는 식별자. 이는 소스 스테이지 상태의 currentRevision.revisionId와 같은 필드에서 추출됩니다.
Execution ID: 파이프라인 실행의 고유 ID

4.5 테이블 정의: CodePipeline 상태 시각적 매핑

다음 표는 API에서 반환되는 각 상태 문자열에 대한 심볼, 색상, 설명을 정의하여 일관되고 직관적인 사용자 인터페이스를 보장합니다.
API 상태 문자열
심볼
색상
설명
Succeeded
✓
Green
스테이지가 성공적으로 완료되었습니다.
Failed
✗
Red
스테이지가 실패했습니다.
InProgress
→
Blue
스테이지가 현재 실행 중입니다.
Stopped
⏹
Yellow
스테이지가 수동으로 중지되었습니다.
Stopping
⏹
Yellow
스테이지가 중지되는 과정에 있습니다.
Superseded
≫
Gray
더 새로운 실행이 시작되어 현재 실행이 대체되었습니다.
Cancelled
∅
Gray
스테이지가 취소되었습니다.

