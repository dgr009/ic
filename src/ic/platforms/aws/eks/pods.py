#!/usr/bin/env python3
import os
import sys
import argparse
import json
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import base64
import tempfile

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box

from common.log import log_info_non_console, log_error
from common.progress_decorator import progress_bar, spinner
from common.utils import (
    get_env_accounts,
    get_profiles,
    DEFINED_REGIONS,
    create_session
)

load_dotenv()
console = Console()

@spinner("Getting EKS cluster information")
def get_eks_cluster_info(session, region_name, cluster_name):
    """EKS 클러스터 정보를 가져옵니다."""
    try:
        eks_client = session.client("eks", region_name=region_name)
        response = eks_client.describe_cluster(name=cluster_name)
        return response['cluster']
    except Exception as e:
        log_error(f"EKS 클러스터 정보 조회 실패: {cluster_name}, Error={e}")
        return None

@spinner("Creating temporary kubeconfig")
def create_kubeconfig(cluster_info, session, region_name):
    """임시 kubeconfig 파일을 생성합니다."""
    try:
        # STS 토큰 생성
        sts_client = session.client('sts', region_name=region_name)
        token_response = sts_client.get_caller_identity()
        
        # kubeconfig 내용 생성
        kubeconfig = {
            'apiVersion': 'v1',
            'kind': 'Config',
            'clusters': [{
                'name': cluster_info['name'],
                'cluster': {
                    'server': cluster_info['endpoint'],
                    'certificate-authority-data': cluster_info['certificateAuthority']['data']
                }
            }],
            'contexts': [{
                'name': cluster_info['name'],
                'context': {
                    'cluster': cluster_info['name'],
                    'user': cluster_info['name']
                }
            }],
            'current-context': cluster_info['name'],
            'users': [{
                'name': cluster_info['name'],
                'user': {
                    'exec': {
                        'apiVersion': 'client.authentication.k8s.io/v1beta1',
                        'command': 'aws',
                        'args': [
                            'eks', 'get-token',
                            '--cluster-name', cluster_info['name'],
                            '--region', region_name
                        ]
                    }
                }
            }]
        }
        
        # 임시 파일에 kubeconfig 저장
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(kubeconfig, temp_file, default_flow_style=False)
        temp_file.close()
        
        return temp_file.name
        
    except Exception as e:
        log_error(f"kubeconfig 생성 실패: {e}")
        return None

@progress_bar("Fetching EKS pod information via kubectl")
def fetch_pods_info(account_id, profile_name, region_name, cluster_name_filter=None, namespace_filter=None):
    """EKS 클러스터의 파드 정보를 수집합니다."""
    log_info_non_console(f"EKS 파드 정보 수집 시작: Account={account_id}, Region={region_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        log_error(f"AWS 세션 생성 실패: Account={account_id}, Region={region_name}")
        return []
    
    try:
        # kubernetes 클라이언트 import (선택적)
        try:
            from kubernetes import client, config
            log_info_non_console("✅ kubernetes 패키지 로드 성공")
        except ImportError as e:
            log_error(f"❌ kubernetes 패키지가 설치되지 않았습니다: {e}")
            log_error("해결 방법: 'pip install kubernetes' 실행 후 다시 시도하세요.")
            return []
        
        eks_client = session.client("eks", region_name=region_name)
        
        # 클러스터 목록 조회
        clusters_response = eks_client.list_clusters()
        cluster_names = clusters_response.get('clusters', [])
        
        if cluster_name_filter:
            cluster_names = [name for name in cluster_names if cluster_name_filter.lower() in name.lower()]
        
        if not cluster_names:
            return []
        
        pods_info_list = []
        
        for cluster_name in cluster_names:
            try:
                log_info_non_console(f"🔍 클러스터 처리 중: {cluster_name}")
                
                # 클러스터 정보 조회
                cluster_info = get_eks_cluster_info(session, region_name, cluster_name)
                if not cluster_info:
                    log_error(f"❌ 클러스터 정보 조회 실패: {cluster_name}")
                    continue
                
                log_info_non_console(f"✅ 클러스터 정보 조회 성공: {cluster_name}")
                
                # kubeconfig 생성
                kubeconfig_path = create_kubeconfig(cluster_info, session, region_name)
                if not kubeconfig_path:
                    log_error(f"❌ kubeconfig 생성 실패: {cluster_name}")
                    continue
                
                log_info_non_console(f"✅ kubeconfig 생성 성공: {cluster_name}")
                
                try:
                    # Kubernetes 클라이언트 설정
                    log_info_non_console(f"🔗 Kubernetes API 연결 시도: {cluster_name}")
                    config.load_kube_config(config_file=kubeconfig_path)
                    v1 = client.CoreV1Api()
                    log_info_non_console(f"✅ Kubernetes API 연결 성공: {cluster_name}")
                    
                    # 파드 목록 조회
                    if namespace_filter:
                        log_info_non_console(f"🔍 네임스페이스 '{namespace_filter}' 파드 조회 중...")
                        pods = v1.list_namespaced_pod(namespace=namespace_filter)
                    else:
                        log_info_non_console(f"🔍 모든 네임스페이스 파드 조회 중...")
                        pods = v1.list_pod_for_all_namespaces()
                    
                    log_info_non_console(f"📊 발견된 파드 수: {len(pods.items)}")
                    
                    for pod in pods.items:
                        pod_data = {
                            'account_id': account_id,
                            'region': region_name,
                            'cluster_name': cluster_name,
                            'pod': {
                                'name': pod.metadata.name,
                                'namespace': pod.metadata.namespace,
                                'phase': pod.status.phase,
                                'node_name': pod.spec.node_name,
                                'created_at': pod.metadata.creation_timestamp,
                                'labels': pod.metadata.labels or {},
                                'annotations': pod.metadata.annotations or {},
                                'containers': [],
                                'conditions': pod.status.conditions or [],
                                'pod_ip': pod.status.pod_ip,
                                'host_ip': pod.status.host_ip,
                                'restart_policy': pod.spec.restart_policy,
                                'service_account': pod.spec.service_account_name
                            }
                        }
                        
                        # 컨테이너 정보
                        if pod.spec.containers:
                            for container in pod.spec.containers:
                                container_info = {
                                    'name': container.name,
                                    'image': container.image,
                                    'resources': {
                                        'requests': container.resources.requests or {} if container.resources else {},
                                        'limits': container.resources.limits or {} if container.resources else {}
                                    }
                                }
                                pod_data['pod']['containers'].append(container_info)
                        
                        # 컨테이너 상태 정보
                        if pod.status.container_statuses:
                            for i, container_status in enumerate(pod.status.container_statuses):
                                if i < len(pod_data['pod']['containers']):
                                    pod_data['pod']['containers'][i].update({
                                        'ready': container_status.ready,
                                        'restart_count': container_status.restart_count,
                                        'state': 'running' if container_status.state.running else 
                                               'waiting' if container_status.state.waiting else 
                                               'terminated' if container_status.state.terminated else 'unknown'
                                    })
                        
                        pods_info_list.append(pod_data)
                
                finally:
                    # 임시 kubeconfig 파일 삭제
                    try:
                        os.unlink(kubeconfig_path)
                    except:
                        pass
                
            except Exception as e:
                log_error(f"❌ 클러스터 {cluster_name} 파드 정보 조회 실패: {e}")
                log_error(f"오류 타입: {type(e).__name__}")
                if "Unauthorized" in str(e) or "Forbidden" in str(e):
                    log_error("🔐 Kubernetes RBAC 권한이 필요합니다!")
                    log_error("해결 방법: kubectl create clusterrolebinding eks-cli-view-binding --clusterrole=view --user=$(aws sts get-caller-identity --query Arn --output text)")
                continue
        
        return pods_info_list
        
    except Exception as e:
        log_error(f"EKS 파드 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(pods_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(pods_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(pods_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(pods_info_list)

def format_table_output(pods_info_list):
    """테이블 형식으로 출력합니다."""
    if not pods_info_list:
        console.print("[yellow]표시할 EKS 파드가 없습니다.[/yellow]")
        return
    
    # 클러스터별로 그룹화
    clusters = {}
    for pod_info in pods_info_list:
        cluster_name = pod_info['cluster_name']
        if cluster_name not in clusters:
            clusters[cluster_name] = []
        clusters[cluster_name].append(pod_info)
    
    for cluster_name, cluster_pods in clusters.items():
        console.print(f"\n[bold blue]🔹 Cluster: {cluster_name}[/bold blue]")
        
        # 파드 요약 테이블
        console.print(f"\n[bold]🚀 Pods Summary ({len(cluster_pods)} pods)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("Namespace", style="cyan")
        summary_table.add_column("Pod Name", style="white")
        summary_table.add_column("Phase", justify="center")
        summary_table.add_column("Node", style="green")
        summary_table.add_column("Containers", justify="center")
        summary_table.add_column("Restarts", justify="center")
        summary_table.add_column("Age", style="dim")
        summary_table.add_column("Pod IP", style="yellow")
        
        for pod_info in cluster_pods:
            pod = pod_info['pod']
            
            # 컨테이너 정보 요약
            containers = pod.get('containers', [])
            container_count = len(containers)
            ready_count = sum(1 for c in containers if c.get('ready', False))
            total_restarts = sum(c.get('restart_count', 0) for c in containers)
            
            summary_table.add_row(
                pod.get('namespace', '-'),
                pod.get('name', '-'),
                format_pod_phase(pod.get('phase', '-')),
                pod.get('node_name', '-') or 'Pending',
                f"{ready_count}/{container_count}",
                str(total_restarts),
                format_age(pod.get('created_at')),
                pod.get('pod_ip', '-') or 'Pending'
            )
        
        console.print(summary_table)
        
        # 네임스페이스별 통계
        namespace_stats = {}
        for pod_info in cluster_pods:
            ns = pod_info['pod'].get('namespace', 'default')
            if ns not in namespace_stats:
                namespace_stats[ns] = {'total': 0, 'running': 0, 'pending': 0, 'failed': 0}
            namespace_stats[ns]['total'] += 1
            phase = pod_info['pod'].get('phase', '').lower()
            if phase == 'running':
                namespace_stats[ns]['running'] += 1
            elif phase == 'pending':
                namespace_stats[ns]['pending'] += 1
            elif phase in ['failed', 'error']:
                namespace_stats[ns]['failed'] += 1
        
        if len(namespace_stats) > 1:
            console.print(f"\n[bold]📊 Namespace Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Namespace", style="cyan")
            stats_table.add_column("Total", justify="center")
            stats_table.add_column("Running", justify="center", style="green")
            stats_table.add_column("Pending", justify="center", style="yellow")
            stats_table.add_column("Failed", justify="center", style="red")
            
            for ns, stats in sorted(namespace_stats.items()):
                stats_table.add_row(
                    ns,
                    str(stats['total']),
                    str(stats['running']),
                    str(stats['pending']),
                    str(stats['failed'])
                )
            
            console.print(stats_table)

def format_pod_phase(phase):
    """파드 상태에 따라 색상을 적용합니다."""
    phase_lower = phase.lower()
    if phase_lower == 'running':
        return f"[bold green]{phase}[/bold green]"
    elif phase_lower == 'pending':
        return f"[bold yellow]{phase}[/bold yellow]"
    elif phase_lower in ['failed', 'error']:
        return f"[bold red]{phase}[/bold red]"
    elif phase_lower == 'succeeded':
        return f"[bold blue]{phase}[/bold blue]"
    else:
        return phase

def format_age(created_at):
    """생성 시간으로부터 경과 시간을 계산합니다."""
    if not created_at:
        return '-'
    
    try:
        if isinstance(created_at, str):
            # ISO 형식 문자열을 datetime으로 변환
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created_dt = created_at
        
        # timezone aware로 만들기
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        age = now - created_dt
        
        days = age.days
        hours, remainder = divmod(age.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d{hours}h"
        elif hours > 0:
            return f"{hours}h{minutes}m"
        else:
            return f"{minutes}m"
            
    except Exception:
        return '-'

@progress_bar("Processing EKS pod discovery across accounts and regions")
def main(args):
    """메인 함수"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    all_pods_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_pods_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.cluster,
                    args.namespace
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_pods_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_pods_info, args.output)
        print(output)
    else:
        format_table_output(all_pods_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-c', '--cluster', help='클러스터 이름 필터 (부분 일치)')
    parser.add_argument('-n', '--namespace', help='네임스페이스 필터 (정확히 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EKS 파드 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)