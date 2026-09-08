#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
try:
    from google.cloud import storage
    from google.cloud.storage import Client as StorageClient
    from google.api_core import exceptions as gcp_exceptions
    GCP_STORAGE_AVAILABLE = True
except ImportError:
    GCP_STORAGE_AVAILABLE = False
    storage = None
    StorageClient = None
    gcp_exceptions = None
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule
from rich.tree import Tree

from common.gcp_utils import (
        GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    create_gcp_client, format_gcp_output, get_gcp_resource_labels
    )
from common.log import log_info, log_error, log_exception

console = Console()


def fetch_storage_buckets_direct(project_id: str) -> List[Dict]:
    """
    직접 API를 통해 GCP Cloud Storage 버킷을 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
    
    Returns:
        Cloud Storage 버킷 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        storage_client = StorageClient(credentials=credentials, project=project_id)
        
        all_buckets = []
        
        try:
            # 프로젝트의 모든 버킷 가져오기
            buckets = storage_client.list_buckets()
            
            for bucket in buckets:
                bucket_data = collect_bucket_details(storage_client, bucket)
                if bucket_data:
                    all_buckets.append(bucket_data)
                    
        except gcp_exceptions.Forbidden:
            log_error(f"프로젝트 {project_id}에 대한 Cloud Storage 접근 권한이 없습니다")
            return []
        except Exception as e:
            log_error(f"Cloud Storage 버킷 조회 실패: {project_id}, Error={e}")
            return []
        
        log_info(f"프로젝트 {project_id}에서 {len(all_buckets)}개 Cloud Storage 버킷 발견")
        return all_buckets
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Cloud Storage 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Cloud Storage 버킷 조회 실패: {project_id}, Error={e}")
        return []


def fetch_storage_buckets(project_id: str) -> List[Dict]:
    """
    GCP Cloud Storage 버킷을 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
    
    Returns:
        Cloud Storage 버킷 정보 리스트
    """
    return fetch_storage_buckets_direct(project_id)


def collect_bucket_details(storage_client: StorageClient, bucket) -> Optional[Dict]:
    """
    버킷의 상세 정보를 수집합니다.
    
    Args:
        storage_client: Cloud Storage 클라이언트
        bucket: 버킷 객체
    
    Returns:
        버킷 상세 정보 딕셔너리
    """
    try:
        # 기본 버킷 정보
        bucket_data = {
            'project_id': bucket.project_number,
            'name': bucket.name,
            'location': bucket.location,
            'location_type': bucket.location_type,
            'storage_class': bucket.storage_class,
            'creation_time': bucket.time_created,
            'updated_time': bucket.updated,
            'metageneration': bucket.metageneration,
            'etag': bucket.etag,
            'labels': dict(bucket.labels) if bucket.labels else {},
            'versioning_enabled': False,
            'lifecycle_rules': [],
            'cors_rules': [],
            'website_config': {},
            'encryption_config': {},
            'iam_config': {},
            'retention_policy': {},
            'logging_config': {},
            'object_count': 0,
            'total_size': 0
        }
        
        # 버전 관리 설정
        if hasattr(bucket, 'versioning_enabled') and bucket.versioning_enabled:
            bucket_data['versioning_enabled'] = bucket.versioning_enabled
        
        # 라이프사이클 정책
        if hasattr(bucket, 'lifecycle_rules') and bucket.lifecycle_rules:
            bucket_data['lifecycle_rules'] = [
                {
                    'action': rule.get('action', {}),
                    'condition': rule.get('condition', {})
                }
                for rule in bucket.lifecycle_rules
            ]
        
        # CORS 설정
        if hasattr(bucket, 'cors') and bucket.cors:
            bucket_data['cors_rules'] = [
                {
                    'origin': cors.get('origin', []),
                    'method': cors.get('method', []),
                    'responseHeader': cors.get('responseHeader', []),
                    'maxAgeSeconds': cors.get('maxAgeSeconds')
                }
                for cors in bucket.cors
            ]
        
        # 웹사이트 설정
        if hasattr(bucket, 'website') and bucket.website:
            bucket_data['website_config'] = {
                'main_page_suffix': bucket.website.get('mainPageSuffix'),
                'not_found_page': bucket.website.get('notFoundPage')
            }
        
        # 암호화 설정
        if hasattr(bucket, 'encryption') and bucket.encryption:
            bucket_data['encryption_config'] = {
                'default_kms_key_name': bucket.encryption.get('defaultKmsKeyName')
            }
        
        # IAM 설정
        if hasattr(bucket, 'iam_configuration') and bucket.iam_configuration:
            bucket_data['iam_config'] = {
                'uniform_bucket_level_access': bucket.iam_configuration.get('uniformBucketLevelAccess', {})
            }
        
        # 보존 정책
        if hasattr(bucket, 'retention_policy') and bucket.retention_policy:
            bucket_data['retention_policy'] = {
                'retention_period': bucket.retention_policy.get('retentionPeriod'),
                'effective_time': bucket.retention_policy.get('effectiveTime'),
                'is_locked': bucket.retention_policy.get('isLocked', False)
            }
        
        # 로깅 설정
        if hasattr(bucket, 'logging') and bucket.logging:
            bucket_data['logging_config'] = {
                'log_bucket': bucket.logging.get('logBucket'),
                'log_object_prefix': bucket.logging.get('logObjectPrefix')
            }
        
        # 객체 수와 크기 (선택적으로 수집, 성능상 이유로 제한적으로 사용)
        try:
            blobs = list(bucket.list_blobs(max_results=1000))  # 최대 1000개만 확인
            bucket_data['object_count'] = len(blobs)
            bucket_data['total_size'] = sum(blob.size for blob in blobs if blob.size)
        except Exception as e:
            log_error(f"버킷 {bucket.name} 객체 정보 수집 실패: {e}")
            bucket_data['object_count'] = 'N/A'
            bucket_data['total_size'] = 'N/A'
        
        return bucket_data
        
    except Exception as e:
        log_error(f"버킷 상세 정보 수집 실패: {bucket.name}, Error={e}")
        return None


def get_bucket_iam_policy(storage_client: StorageClient, bucket_name: str) -> Dict:
    """
    버킷의 IAM 정책을 가져옵니다.
    
    Args:
        storage_client: Cloud Storage 클라이언트
        bucket_name: 버킷 이름
    
    Returns:
        IAM 정책 딕셔너리
    """
    try:
        bucket = storage_client.bucket(bucket_name)
        policy = bucket.get_iam_policy()
        
        return {
            'bindings': [
                {
                    'role': binding.role,
                    'members': list(binding.members)
                }
                for binding in policy.bindings
            ],
            'etag': policy.etag,
            'version': policy.version
        }
        
    except Exception as e:
        log_error(f"버킷 {bucket_name} IAM 정책 조회 실패: {e}")
        return {}


def load_mock_data():
    """mock_data.json에서 데이터를 로드합니다."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    mock_file = os.path.join(dir_path, 'mock_data.json')

    try:
        with open(mock_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[bold red]에러: Mock 데이터 파일을 찾을 수 없습니다: {mock_file}[/bold red]")
        return []
    except json.JSONDecodeError:
        console.print(f"[bold red]에러: Mock 데이터 파일의 형식이 올바르지 않습니다: {mock_file}[/bold red]")
        return []


def format_table_output(buckets: List[Dict]) -> None:
    """
    GCP Cloud Storage 버킷 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        buckets: 버킷 정보 리스트
    """
    if not buckets:
        console.print("[yellow]표시할 GCP Cloud Storage 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 이름 순으로 정렬
    buckets.sort(key=lambda x: (str(x.get("project_id", "")), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Bucket Name", style="bold white")
    table.add_column("Location", style="bold cyan")
    table.add_column("Storage Class", style="dim")
    table.add_column("Versioning", justify="center")
    table.add_column("Objects", justify="right", style="blue")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Created", style="dim")
    table.add_column("Labels", style="dim")

    last_project = None
    
    for i, bucket in enumerate(buckets):
        project_changed = str(bucket.get("project_id")) != str(last_project)

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", end_section=True)

        # 버전 관리 상태
        versioning = "✓" if bucket.get('versioning_enabled') else "✗"
        versioning_colored = f"[green]{versioning}[/green]" if bucket.get('versioning_enabled') else f"[red]{versioning}[/red]"
        
        # 객체 수와 크기 포맷팅
        object_count = bucket.get('object_count', 0)
        total_size = bucket.get('total_size', 0)
        
        if object_count == 'N/A':
            object_count_str = "N/A"
            size_str = "N/A"
        else:
            object_count_str = f"{object_count:,}"
            if isinstance(total_size, (int, float)) and total_size > 0:
                if total_size >= 1024**3:  # GB
                    size_str = f"{total_size / (1024**3):.1f} GB"
                elif total_size >= 1024**2:  # MB
                    size_str = f"{total_size / (1024**2):.1f} MB"
                elif total_size >= 1024:  # KB
                    size_str = f"{total_size / 1024:.1f} KB"
                else:
                    size_str = f"{total_size} B"
            else:
                size_str = "0 B"
        
        # 생성 시간 포맷팅
        created_time = bucket.get('creation_time')
        if created_time:
            if hasattr(created_time, 'strftime'):
                created_str = created_time.strftime('%Y-%m-%d')
            else:
                created_str = str(created_time)[:10]  # YYYY-MM-DD 형식으로 자르기
        else:
            created_str = "N/A"
        
        # 라벨 정보 (최대 2개만 표시)
        labels = bucket.get('labels', {})
        if labels:
            label_items = list(labels.items())[:2]
            label_text = ", ".join([f"{k}={v}" for k, v in label_items])
            if len(labels) > 2:
                label_text += f" (+{len(labels)-2})"
        else:
            label_text = "-"
        
        display_values = [
            str(bucket.get("project_id", "")) if project_changed else "",
            bucket.get("name", "N/A"),
            bucket.get("location", "N/A"),
            bucket.get("storage_class", "N/A"),
            versioning_colored,
            object_count_str,
            size_str,
            created_str,
            label_text
        ]
        
        table.add_row(*display_values)

        last_project = bucket.get("project_id")
    
    console.print(table)


def format_tree_output(buckets: List[Dict]) -> None:
    """
    GCP Cloud Storage 버킷 목록을 트리 형식으로 출력합니다 (프로젝트/위치 계층).
    
    Args:
        buckets: 버킷 정보 리스트
    """
    if not buckets:
        console.print("[yellow]표시할 GCP Cloud Storage 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for bucket in buckets:
        project_id = str(bucket.get("project_id", "unknown"))
        location = bucket.get("location", "unknown")
        
        if project_id not in projects:
            projects[project_id] = {}
        if location not in projects[project_id]:
            projects[project_id][location] = []
        
        projects[project_id][location].append(bucket)

    # 트리 구조 생성
    tree = Tree("🪣 [bold blue]GCP Cloud Storage Buckets[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        
        for location in sorted(projects[project_id].keys()):
            location_buckets = projects[project_id][location]
            location_node = project_node.add(
                f"🌍 [bold cyan]{location}[/bold cyan] ({len(location_buckets)} buckets)"
            )
            
            for bucket in sorted(location_buckets, key=lambda x: x.get("name", "")):
                # 버킷 정보
                bucket_name = bucket.get("name", "N/A")
                storage_class = bucket.get("storage_class", "N/A")
                versioning = "✓" if bucket.get('versioning_enabled') else "✗"
                object_count = bucket.get('object_count', 0)
                
                bucket_info = (
                    f"🪣 [bold white]{bucket_name}[/bold white] "
                    f"({storage_class}) - "
                    f"Versioning: {versioning}"
                )
                
                if object_count != 'N/A':
                    bucket_info += f", Objects: {object_count:,}"
                
                bucket_node = location_node.add(bucket_info)
                
                # 추가 세부 정보
                if bucket.get('lifecycle_rules'):
                    rule_count = len(bucket['lifecycle_rules'])
                    bucket_node.add(f"🔄 Lifecycle Rules: {rule_count}")
                
                if bucket.get('labels'):
                    labels_text = ", ".join([f"{k}={v}" for k, v in bucket['labels'].items()])
                    bucket_node.add(f"🏷️  Labels: {labels_text}")
                
                if bucket.get('encryption_config', {}).get('default_kms_key_name'):
                    bucket_node.add(f"🔐 KMS Encrypted")
                
                if bucket.get('retention_policy', {}).get('retention_period'):
                    retention_days = int(bucket['retention_policy']['retention_period']) // 86400
                    bucket_node.add(f"🔒 Retention: {retention_days} days")

    console.print(tree)


def format_output(buckets: List[Dict], output_format: str = 'table') -> str:
    """
    버킷 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        buckets: 버킷 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(buckets)
        return ""
    elif output_format == 'tree':
        format_tree_output(buckets)
        return ""
    elif output_format == 'json':
        return format_gcp_output(buckets, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(buckets, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(buckets)
        return ""


def format_paste_output(buckets: List[Dict]) -> None:
    """버킷 목록을 -p (paste) 모드용 CSV로 출력합니다."""
    for b in buckets:
        row = [
            b.get('project_id', '-'),
            b.get('name', '-'),
            b.get('location', '-'),
            b.get('storage_class', '-'),
            b.get('time_created', '-'),
        ]
        print(",".join(str(c) for c in row))


from ic.core.interfaces import BaseCommand, CommandResult


class GcpStorageInfoCommand(BaseCommand):
    """GCP Cloud Storage 버킷 정보 조회 커맨드"""

    @classmethod
    def add_arguments(cls, parser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            '-p', '--project', 
            help='GCP 프로젝트 ID로 필터링 (예: my-project-123)'
        )
        parser.add_argument(
            '--all-projects',
            action='store_true',
            help='접근 가능한 모든 GCP 프로젝트 조회 (대규모 환경 주의)'
        )
        parser.add_argument(
            '-b', '--bucket', 
            help='버킷 이름으로 필터링 (부분 일치)'
        )
        parser.add_argument(
            '--mock',
            action='store_true',
            help='Mock 데이터를 사용하여 오프라인으로 실행'
        )

    def execute(self, args, config=None) -> CommandResult:
        if getattr(args, 'mock', False):
            buckets = load_mock_data()
            filtered = []
            bucket_filter = getattr(args, 'bucket', None)
            proj_filter = getattr(args, 'project', None)
            for b in buckets:
                if bucket_filter and bucket_filter.lower() not in str(b.get('name', '')).lower():
                    continue
                if proj_filter and proj_filter.lower() not in str(b.get('project_id', '')).lower():
                    continue
                filtered.append(b)
            return CommandResult(
                data=filtered,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )

        if not GCP_STORAGE_AVAILABLE:
            console.print("[red]❌ google-cloud-storage 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   pip install 'ic-cli[gcp]' 또는 pip install google-cloud-storage[/yellow]")
            console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
            return CommandResult(data=[], error="google-cloud-storage is not installed", success=False)

        try:
            log_info("GCP Cloud Storage 버킷 조회 시작")
            auth_manager = GCPAuthManager()
            if not auth_manager.validate_credentials():
                console.print("[bold red]GCP 인증에 실패했습니다. 인증 정보를 확인해주세요.[/bold red]")
                console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
                return CommandResult(data=[], error="GCP authentication failed", success=False)

            project_manager = GCPProjectManager(auth_manager)
            resource_collector = GCPResourceCollector(auth_manager)

            if getattr(args, 'project', None):
                projects = [args.project]
            else:
                projects = project_manager.get_projects(all_projects=getattr(args, 'all_projects', False))

            if not projects:
                console.print("[yellow]⚠️  GCP 프로젝트가 지정되지 않았습니다.[/yellow]")
                console.print("💡 [dim]--project <PROJECT_ID> 옵션을 지정하거나 활성 gcloud 프로필을 설정하세요. (전체 조회를 원하시면 --all-projects 옵션을 사용하세요)[/dim]")
                return CommandResult(data=[], table_renderer=format_table_output, tree_renderer=format_tree_output, paste_renderer=format_paste_output)

            all_buckets = resource_collector.parallel_collect(
                projects, 
                fetch_storage_buckets
            )

            filters = {}
            if getattr(args, 'bucket', None):
                filters['name'] = args.bucket
            if getattr(args, 'project', None):
                filters['project'] = args.project

            filtered_buckets = resource_collector.apply_filters(all_buckets, filters)
            return CommandResult(
                data=filtered_buckets,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )
        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpStorageInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpStorageInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Cloud Storage 버킷 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)