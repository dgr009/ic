#!/usr/bin/env python3

import time
import json
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import contextmanager

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from common.log import log_info, log_error, log_exception

console = Console()

@dataclass
class GCPAPICall:
    """GCP API 호출 정보를 담는 데이터 클래스"""
    service: str
    operation: str
    project_id: str
    region: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    success: bool
    error_message: Optional[str]
    response_size: Optional[int]
    via_mcp: bool

@dataclass
class GCPPerformanceMetrics:
    """GCP 성능 메트릭을 담는 데이터 클래스"""
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_duration_ms: float
    total_duration_ms: float
    mcp_calls: int
    direct_calls: int
    calls_by_service: Dict[str, int]
    calls_by_project: Dict[str, int]
    errors_by_type: Dict[str, int]

class GCPMonitor:
    """GCP 작업 모니터링 및 성능 메트릭 수집"""
    
    def __init__(self):
        self._api_calls: deque = deque(maxlen=1000)  # 최근 1000개 호출만 유지
        self._lock = threading.Lock()
        self._health_checks: Dict[str, bool] = {}
        self._mcp_connection_status = False
        self._start_time = datetime.now()
    
    def record_api_call(self, service: str, operation: str, project_id: str, 
                       region: Optional[str] = None, via_mcp: bool = False) -> 'APICallContext':
        """API 호출을 기록하는 컨텍스트 매니저를 반환"""
        return APICallContext(self, service, operation, project_id, region, via_mcp)
    
    def _add_api_call(self, api_call: GCPAPICall):
        """API 호출 정보를 내부 저장소에 추가"""
        with self._lock:
            self._api_calls.append(api_call)
    
    def get_performance_metrics(self, time_window_minutes: int = 60) -> GCPPerformanceMetrics:
        """지정된 시간 창 내의 성능 메트릭을 계산"""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        with self._lock:
            recent_calls = [call for call in self._api_calls if call.start_time >= cutoff_time]
        
        if not recent_calls:
            return GCPPerformanceMetrics(
                total_calls=0, successful_calls=0, failed_calls=0,
                average_duration_ms=0.0, total_duration_ms=0.0,
                mcp_calls=0, direct_calls=0,
                calls_by_service={}, calls_by_project={}, errors_by_type={}
            )
        
        total_calls = len(recent_calls)
        successful_calls = sum(1 for call in recent_calls if call.success)
        failed_calls = total_calls - successful_calls
        
        durations = [call.duration_ms for call in recent_calls if call.duration_ms is not None]
        total_duration_ms = sum(durations)
        average_duration_ms = total_duration_ms / len(durations) if durations else 0.0
        
        mcp_calls = sum(1 for call in recent_calls if call.via_mcp)
        direct_calls = total_calls - mcp_calls
        
        calls_by_service = defaultdict(int)
        calls_by_project = defaultdict(int)
        errors_by_type = defaultdict(int)
        
        for call in recent_calls:
            calls_by_service[call.service] += 1
            calls_by_project[call.project_id] += 1
            if not call.success and call.error_message:
                error_type = call.error_message.split(':')[0] if ':' in call.error_message else call.error_message
                errors_by_type[error_type] += 1
        
        return GCPPerformanceMetrics(
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            average_duration_ms=average_duration_ms,
            total_duration_ms=total_duration_ms,
            mcp_calls=mcp_calls,
            direct_calls=direct_calls,
            calls_by_service=dict(calls_by_service),
            calls_by_project=dict(calls_by_project),
            errors_by_type=dict(errors_by_type)
        )
    
    def update_health_check(self, service: str, is_healthy: bool):
        """서비스 헬스 체크 상태 업데이트"""
        with self._lock:
            self._health_checks[service] = is_healthy
    
    def update_mcp_connection_status(self, is_connected: bool):
        """MCP 서버 연결 상태 업데이트"""
        self._mcp_connection_status = is_connected
        if is_connected:
            log_info("MCP server connection established")
        else:
            log_error("MCP server connection lost, falling back to direct API access")
    
    def get_health_status(self) -> Dict[str, Any]:
        """전체 헬스 상태 반환"""
        with self._lock:
            return {
                'mcp_connected': self._mcp_connection_status,
                'service_health': dict(self._health_checks),
                'uptime_minutes': (datetime.now() - self._start_time).total_seconds() / 60,
                'total_api_calls': len(self._api_calls)
            }
    
    def display_performance_report(self, time_window_minutes: int = 60):
        """성능 리포트를 Rich 형식으로 출력"""
        metrics = self.get_performance_metrics(time_window_minutes)
        health_status = self.get_health_status()
        
        # 성능 메트릭 테이블
        perf_table = Table(title=f"GCP Performance Metrics (Last {time_window_minutes} minutes)")
        perf_table.add_column("Metric", style="cyan")
        perf_table.add_column("Value", style="green")
        
        perf_table.add_row("Total API Calls", str(metrics.total_calls))
        perf_table.add_row("Successful Calls", str(metrics.successful_calls))
        perf_table.add_row("Failed Calls", str(metrics.failed_calls))
        perf_table.add_row("Success Rate", f"{(metrics.successful_calls/metrics.total_calls*100):.1f}%" if metrics.total_calls > 0 else "N/A")
        perf_table.add_row("Average Duration", f"{metrics.average_duration_ms:.1f}ms")
        perf_table.add_row("MCP Calls", str(metrics.mcp_calls))
        perf_table.add_row("Direct API Calls", str(metrics.direct_calls))
        
        console.print(perf_table)
        
        # 서비스별 호출 통계
        if metrics.calls_by_service:
            service_table = Table(title="Calls by Service")
            service_table.add_column("Service", style="cyan")
            service_table.add_column("Calls", style="green")
            
            for service, count in sorted(metrics.calls_by_service.items()):
                service_table.add_row(service, str(count))
            
            console.print(service_table)
        
        # 오류 통계
        if metrics.errors_by_type:
            error_table = Table(title="Errors by Type")
            error_table.add_column("Error Type", style="red")
            error_table.add_column("Count", style="yellow")
            
            for error_type, count in sorted(metrics.errors_by_type.items()):
                error_table.add_row(error_type, str(count))
            
            console.print(error_table)
        
        # 헬스 상태
        health_text = f"MCP Connected: {'✓' if health_status['mcp_connected'] else '✗'}\n"
        health_text += f"Uptime: {health_status['uptime_minutes']:.1f} minutes\n"
        
        if health_status['service_health']:
            health_text += "Service Health:\n"
            for service, is_healthy in health_status['service_health'].items():
                status = '✓' if is_healthy else '✗'
                health_text += f"  {service}: {status}\n"
        
        console.print(Panel(
            health_text,
            title="System Health",
            border_style="green" if health_status['mcp_connected'] else "yellow"
        ))
    
    def log_structured_event(self, event_type: str, data: Dict[str, Any]):
        """구조화된 이벤트 로깅"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'data': data
        }
        log_info(f"GCP_EVENT: {json.dumps(event, default=str)}")

class APICallContext:
    """API 호출을 추적하는 컨텍스트 매니저"""
    
    def __init__(self, monitor: GCPMonitor, service: str, operation: str, 
                 project_id: str, region: Optional[str] = None, via_mcp: bool = False):
        self.monitor = monitor
        self.service = service
        self.operation = operation
        self.project_id = project_id
        self.region = region
        self.via_mcp = via_mcp
        self.start_time = None
        self.api_call = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.api_call = GCPAPICall(
            service=self.service,
            operation=self.operation,
            project_id=self.project_id,
            region=self.region,
            start_time=self.start_time,
            end_time=None,
            duration_ms=None,
            success=False,
            error_message=None,
            response_size=None,
            via_mcp=self.via_mcp
        )
        
        # 구조화된 로깅
        self.monitor.log_structured_event('api_call_start', {
            'service': self.service,
            'operation': self.operation,
            'project_id': self.project_id,
            'region': self.region,
            'via_mcp': self.via_mcp
        })
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        duration_ms = (end_time - self.start_time).total_seconds() * 1000
        
        self.api_call.end_time = end_time
        self.api_call.duration_ms = duration_ms
        
        if exc_type is None:
            self.api_call.success = True
            log_info(f"GCP API call completed: {self.service}.{self.operation} "
                    f"({duration_ms:.1f}ms, {'MCP' if self.via_mcp else 'Direct'})")
        else:
            self.api_call.success = False
            self.api_call.error_message = str(exc_val) if exc_val else "Unknown error"
            log_error(f"GCP API call failed: {self.service}.{self.operation} "
                     f"({duration_ms:.1f}ms, {'MCP' if self.via_mcp else 'Direct'}): {exc_val}")
        
        self.monitor._add_api_call(self.api_call)
        
        # 구조화된 로깅
        self.monitor.log_structured_event('api_call_end', {
            'service': self.service,
            'operation': self.operation,
            'project_id': self.project_id,
            'region': self.region,
            'via_mcp': self.via_mcp,
            'duration_ms': duration_ms,
            'success': self.api_call.success,
            'error_message': self.api_call.error_message
        })
    
    def set_response_size(self, size: int):
        """응답 크기 설정"""
        if self.api_call:
            self.api_call.response_size = size

# 전역 모니터 인스턴스
gcp_monitor = GCPMonitor()

@contextmanager
def monitor_gcp_operation(service: str, operation: str, project_id: str, 
                         region: Optional[str] = None, via_mcp: bool = False):
    """GCP 작업을 모니터링하는 컨텍스트 매니저"""
    with gcp_monitor.record_api_call(service, operation, project_id, region, via_mcp) as context:
        yield context

def log_gcp_performance_summary():
    """GCP 성능 요약을 로그에 출력"""
    gcp_monitor.display_performance_report()

def update_gcp_service_health(service: str, is_healthy: bool):
    """GCP 서비스 헬스 상태 업데이트"""
    gcp_monitor.update_health_check(service, is_healthy)

def update_mcp_connection_status(is_connected: bool):
    """MCP 연결 상태 업데이트"""
    gcp_monitor.update_mcp_connection_status(is_connected)

def log_gcp_structured_event(event_type: str, data: Dict[str, Any]):
    """GCP 구조화된 이벤트 로깅"""
    gcp_monitor.log_structured_event(event_type, data)