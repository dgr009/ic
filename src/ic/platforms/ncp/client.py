"""
NCP API Client

This module provides the core NCP API client with HMAC-SHA256 signature authentication.
It supports both Classic and VPC platforms with automatic endpoint routing.
Includes performance optimizations, timeout handling, and retry logic.
"""

import hashlib
import hmac
import base64
import time
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

# Import security utilities
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from common.ncp_security_utils import ncp_data_masker, ncp_security_monitor

logger = logging.getLogger(__name__)


class NCPAPIError(Exception):
    """NCP API 관련 오류"""
    def __init__(self, message: str, error_code: str = None, status_code: int = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class NCPClient:
    """
    NCP API 클라이언트
    
    HMAC-SHA256 서명을 사용한 NCP REST API 호출을 제공합니다.
    Classic과 VPC 플랫폼을 모두 지원합니다.
    성능 최적화, 타임아웃 처리, 재시도 로직을 포함합니다.
    """
    
    def __init__(self, access_key: str, secret_key: str, region: str = 'KR', platform: str = 'VPC',
                 timeout: int = 30, max_retries: int = 3, backoff_factor: float = 0.3):
        """
        NCP 클라이언트 초기화
        
        Args:
            access_key: NCP Access Key
            secret_key: NCP Secret Key  
            region: 리전 (KR, US, JP)
            platform: 플랫폼 (Classic, VPC)
            timeout: 요청 타임아웃 (초)
            max_retries: 최대 재시도 횟수
            backoff_factor: 재시도 간격 계수
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region.upper()
        self.platform = platform.upper()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        
        # 플랫폼별 엔드포인트 설정
        self.endpoints = self._get_platform_endpoints()
        
        # 기본 헤더 설정
        self.base_headers = {
            'Content-Type': 'application/json',
            'x-ncp-iam-access-key': self.access_key
        }
        
        # HTTP 세션 설정 (연결 재사용 및 재시도 로직)
        self.session = self._create_session()
        
        # Monitor credential usage
        ncp_security_monitor.monitor_credential_usage('ncp_access_key', True)
        
        logger.debug(f"NCP Client initialized - Region: {self.region}, Platform: {self.platform}, Timeout: {self.timeout}s")
    
    def _create_session(self) -> requests.Session:
        """
        HTTP 세션 생성 (연결 재사용 및 재시도 로직 포함)
        
        Returns:
            설정된 requests.Session 객체
        """
        session = requests.Session()
        
        # 재시도 전략 설정
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],  # 재시도할 HTTP 상태 코드
            allowed_methods=["HEAD", "GET", "OPTIONS"],  # 재시도할 HTTP 메서드
            backoff_factor=self.backoff_factor,
            raise_on_status=False
        )
        
        # HTTP 어댑터 설정
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_platform_endpoints(self) -> Dict[str, str]:
        """플랫폼별 API 엔드포인트 반환"""
        base_url = "https://ncloud.apigw.ntruss.com"
        
        if self.platform == "CLASSIC":
            return {
                "server": f"{base_url}/server/v2",
                "storage": f"{base_url}/storage/v2", 
                "loadbalancer": f"{base_url}/loadbalancer/v2",
                "clouddb": f"{base_url}/clouddb/v2",
                "vpc": None,  # Classic에서는 VPC 미지원
                "vserver": None,
                "vloadbalancer": None
            }
        elif self.platform == "VPC":
            return {
                "vserver": f"{base_url}/vserver/v2",
                "vpc": f"{base_url}/vpc/v2",
                "vloadbalancer": f"{base_url}/vloadbalancer/v2",
                "clouddb": f"{base_url}/clouddb/v2",
                "server": f"{base_url}/server/v2",  # 호환성을 위해 유지
                "storage": f"{base_url}/storage/v2",
                "loadbalancer": f"{base_url}/loadbalancer/v2"
            }
        else:
            raise ValueError(f"지원하지 않는 플랫폼: {self.platform}")
    
    def _make_signature(self, method: str, uri: str, timestamp: str) -> str:
        """
        HMAC-SHA256 서명 생성
        
        Args:
            method: HTTP 메서드 (GET, POST 등)
            uri: API URI
            timestamp: 타임스탬프
            
        Returns:
            Base64 인코딩된 서명
        """
        # 서명 문자열 생성
        message = f"{method} {uri}\n{timestamp}\n{self.access_key}"
        
        # HMAC-SHA256 서명 생성
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Base64 인코딩
        return base64.b64encode(signature).decode('utf-8')
    
    def _make_request(self, method: str, service: str, action: str, params: Dict = None) -> Dict[str, Any]:
        """
        NCP API 요청 실행
        
        Args:
            method: HTTP 메서드
            service: 서비스 이름 (server, vpc 등)
            action: API 액션
            params: 요청 파라미터
            
        Returns:
            API 응답 데이터
        """
        # 엔드포인트 확인
        if service not in self.endpoints or self.endpoints[service] is None:
            raise NCPAPIError(f"서비스 '{service}'는 {self.platform} 플랫폼에서 지원되지 않습니다.")
        
        base_url = self.endpoints[service]
        
        # 파라미터 설정
        if params is None:
            params = {}
        
        params['action'] = action
        params['responseFormatType'] = 'json'
        
        # URI 구성 (NCP API 스펙에 맞게)
        uri = f"/{service}/v2"
        if params:
            query_string = urlencode(sorted(params.items()))
            uri += f"?{query_string}"
        
        # 타임스탬프 생성
        timestamp = str(int(time.time() * 1000))
        
        # 서명 생성
        signature = self._make_signature(method, uri, timestamp)
        
        # 헤더 설정
        headers = self.base_headers.copy()
        headers.update({
            'x-ncp-apigw-timestamp': timestamp,
            'x-ncp-apigw-signature-v2': signature
        })
        
        # 요청 URL 구성
        url = f"{base_url}{uri}"
        
        try:
            logger.debug(f"NCP API 요청: {method} {url}")
            
            # 요청 시작 시간 기록 (성능 모니터링)
            start_time = time.time()
            
            # HTTP 요청 실행 (세션 사용으로 연결 재사용)
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.timeout
            )
            
            # 요청 완료 시간 기록
            elapsed_time = time.time() - start_time
            logger.debug(f"NCP API 요청 완료: {elapsed_time:.2f}초")
            
            # 응답 상태 확인
            if response.status_code != 200:
                error_msg = f"NCP API 오류: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'responseError' in error_data:
                        error_info = error_data['responseError']
                        error_msg = f"{error_info.get('returnMessage', error_msg)} (코드: {error_info.get('returnCode', 'N/A')})"
                except:
                    pass
                
                # Monitor API error
                ncp_security_monitor.log_security_event(
                    'api_error',
                    {'service': service, 'action': action, 'status_code': response.status_code},
                    'ERROR'
                )
                
                raise NCPAPIError(error_msg, status_code=response.status_code)
            
            # JSON 응답 파싱
            response_data = response.json()
            logger.debug(f"NCP API 응답 수신: {action}")
            
            # Monitor successful API call
            ncp_security_monitor.monitor_api_call(service, action, params, response_data)
            
            # Mask sensitive data in response for logging
            masked_response = ncp_data_masker.mask_ncp_data(response_data)
            logger.debug(f"NCP API 응답 (마스킹됨): {masked_response}")
            
            return response_data
            
        except requests.exceptions.Timeout as e:
            logger.error(f"NCP API 타임아웃: {e}")
            raise NCPAPIError(f"요청 타임아웃 ({self.timeout}초): {str(e)}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"NCP API 연결 오류: {e}")
            raise NCPAPIError(f"연결 오류: {str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"NCP API 요청 실패: {e}")
            raise NCPAPIError(f"네트워크 오류: {str(e)}")
        except Exception as e:
            logger.error(f"NCP API 처리 중 오류: {e}")
            raise NCPAPIError(f"API 처리 오류: {str(e)}")
    
    def get_server_instances(self, server_instance_no_list: List[str] = None) -> List[Dict]:
        """
        서버 인스턴스 목록 조회
        
        Args:
            server_instance_no_list: 조회할 서버 인스턴스 번호 목록
            
        Returns:
            서버 인스턴스 정보 목록
        """
        params = {}
        if server_instance_no_list:
            for i, instance_no in enumerate(server_instance_no_list):
                params[f'serverInstanceNoList.{i+1}'] = instance_no
        
        # 플랫폼에 따른 서비스 선택
        service = "vserver" if self.platform == "VPC" else "server"
        
        try:
            response = self._make_request('GET', service, 'getServerInstanceList', params)
            
            # 응답에서 인스턴스 목록 추출
            if 'getServerInstanceListResponse' in response:
                instances = response['getServerInstanceListResponse'].get('serverInstanceList', [])
                logger.debug(f"조회된 서버 인스턴스 수: {len(instances)}")
                return instances
            
            logger.warning("응답에서 서버 인스턴스 목록을 찾을 수 없습니다.")
            return []
            
        except NCPAPIError as e:
            logger.error(f"서버 인스턴스 조회 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"서버 인스턴스 조회 중 예상치 못한 오류: {e}")
            raise NCPAPIError(f"서버 인스턴스 조회 실패: {str(e)}")
    
    def get_object_storage_buckets(self) -> List[Dict]:
        """
        오브젝트 스토리지 버킷 목록 조회
        
        Returns:
            버킷 정보 목록
        """
        try:
            # Object Storage는 별도 API 엔드포인트 사용
            # NCP Object Storage API v2 사용
            storage_endpoint = "https://ncloud.apigw.ntruss.com/storage/v2"
            
            # 파라미터 설정
            params = {
                'action': 'getBucketList',
                'responseFormatType': 'json'
            }
            
            # URI 구성
            uri = "/storage/v2"
            if params:
                from urllib.parse import urlencode
                query_string = urlencode(sorted(params.items()))
                uri += f"?{query_string}"
            
            # 타임스탬프 생성
            timestamp = str(int(time.time() * 1000))
            
            # 서명 생성
            signature = self._make_signature('GET', uri, timestamp)
            
            # 헤더 설정
            headers = self.base_headers.copy()
            headers.update({
                'x-ncp-apigw-timestamp': timestamp,
                'x-ncp-apigw-signature-v2': signature
            })
            
            # 요청 URL 구성
            url = f"{storage_endpoint}{uri}"
            
            logger.debug(f"Object Storage API 요청: GET {url}")
            
            # 요청 시작 시간 기록
            start_time = time.time()
            
            # HTTP 요청 실행 (세션 사용)
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            # 요청 완료 시간 기록
            elapsed_time = time.time() - start_time
            logger.debug(f"Object Storage API 요청 완료: {elapsed_time:.2f}초")
            
            # 응답 상태 확인
            if response.status_code != 200:
                error_msg = f"Object Storage API 오류: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'responseError' in error_data:
                        error_info = error_data['responseError']
                        error_msg = f"{error_info.get('returnMessage', error_msg)} (코드: {error_info.get('returnCode', 'N/A')})"
                except:
                    pass
                
                raise NCPAPIError(error_msg, status_code=response.status_code)
            
            # JSON 응답 파싱
            response_data = response.json()
            logger.debug("Object Storage API 응답 수신")
            
            # 응답에서 버킷 목록 추출
            if 'getBucketListResponse' in response_data:
                buckets = response_data['getBucketListResponse'].get('bucketList', [])
                logger.debug(f"조회된 버킷 수: {len(buckets)}")
                return buckets
            
            logger.warning("응답에서 버킷 목록을 찾을 수 없습니다.")
            return []
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Object Storage API 타임아웃: {e}")
            raise NCPAPIError(f"Object Storage 요청 타임아웃 ({self.timeout}초): {str(e)}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Object Storage API 연결 오류: {e}")
            raise NCPAPIError(f"Object Storage 연결 오류: {str(e)}")
        except NCPAPIError as e:
            logger.error(f"Object Storage 버킷 조회 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"Object Storage 버킷 조회 중 예상치 못한 오류: {e}")
            raise NCPAPIError(f"Object Storage 버킷 조회 실패: {str(e)}")
    
    def get_vpc_list(self, vpc_no_list: List[str] = None) -> List[Dict]:
        """
        VPC 목록 조회 (VPC 플랫폼 전용)
        
        Args:
            vpc_no_list: 조회할 VPC 번호 목록
            
        Returns:
            VPC 정보 목록
        """
        if self.platform != "VPC":
            raise NCPAPIError("VPC 서비스는 VPC 플랫폼에서만 사용 가능합니다.")
        
        params = {}
        if vpc_no_list:
            for i, vpc_no in enumerate(vpc_no_list):
                params[f'vpcNoList.{i+1}'] = vpc_no
        
        response = self._make_request('GET', 'vpc', 'getVpcList', params)
        
        if 'getVpcListResponse' in response:
            return response['getVpcListResponse'].get('vpcList', [])
        return []
    
    def get_cloud_db_instances(self, cloud_db_instance_no_list: List[str] = None) -> List[Dict]:
        """
        Cloud DB 인스턴스 목록 조회
        
        Args:
            cloud_db_instance_no_list: 조회할 DB 인스턴스 번호 목록
            
        Returns:
            DB 인스턴스 정보 목록
        """
        params = {}
        if cloud_db_instance_no_list:
            for i, instance_no in enumerate(cloud_db_instance_no_list):
                params[f'cloudDbInstanceNoList.{i+1}'] = instance_no
        
        try:
            # Cloud DB API 호출 (별도 엔드포인트 사용)
            response = self._make_request('GET', 'clouddb', 'getCloudDbInstanceList', params)
            
            # 응답에서 DB 인스턴스 목록 추출
            if 'getCloudDbInstanceListResponse' in response:
                instances = response['getCloudDbInstanceListResponse'].get('cloudDbInstanceList', [])
                logger.debug(f"조회된 Cloud DB 인스턴스 수: {len(instances)}")
                return instances
            
            logger.warning("응답에서 Cloud DB 인스턴스 목록을 찾을 수 없습니다.")
            return []
            
        except NCPAPIError as e:
            logger.error(f"Cloud DB 인스턴스 조회 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"Cloud DB 인스턴스 조회 중 예상치 못한 오류: {e}")
            raise NCPAPIError(f"Cloud DB 인스턴스 조회 실패: {str(e)}")
    
    def get_access_control_groups(self, access_control_group_no_list: List[str] = None) -> List[Dict]:
        """
        보안 그룹(Access Control Group) 목록 조회
        
        Args:
            access_control_group_no_list: 조회할 보안 그룹 번호 목록
            
        Returns:
            보안 그룹 정보 목록
        """
        params = {}
        if access_control_group_no_list:
            for i, group_no in enumerate(access_control_group_no_list):
                params[f'accessControlGroupNoList.{i+1}'] = group_no
        
        # 플랫폼에 따른 서비스 선택
        service = "vserver" if self.platform == "VPC" else "server"
        
        response = self._make_request('GET', service, 'getAccessControlGroupList', params)
        
        if 'getAccessControlGroupListResponse' in response:
            return response['getAccessControlGroupListResponse'].get('accessControlGroupList', [])
        return []
    
    def get_access_control_group_rules(self, access_control_group_no: str) -> List[Dict]:
        """
        보안 그룹 규칙 목록 조회
        
        Args:
            access_control_group_no: 보안 그룹 번호
            
        Returns:
            보안 그룹 규칙 정보 목록
        """
        params = {
            'accessControlGroupNo': access_control_group_no
        }
        
        # 플랫폼에 따른 서비스 선택
        service = "vserver" if self.platform == "VPC" else "server"
        
        try:
            response = self._make_request('GET', service, 'getAccessControlRuleList', params)
            
            if 'getAccessControlRuleListResponse' in response:
                rules = response['getAccessControlRuleListResponse'].get('accessControlRuleList', [])
                logger.debug(f"조회된 보안 그룹 규칙 수: {len(rules)}")
                return rules
            
            logger.warning("응답에서 보안 그룹 규칙 목록을 찾을 수 없습니다.")
            return []
            
        except NCPAPIError as e:
            logger.error(f"보안 그룹 규칙 조회 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"보안 그룹 규칙 조회 중 예상치 못한 오류: {e}")
            raise NCPAPIError(f"보안 그룹 규칙 조회 실패: {str(e)}")
    
    def get_subnet_list(self, vpc_no: str = None, subnet_no_list: List[str] = None) -> List[Dict]:
        """
        서브넷 목록 조회 (VPC 플랫폼 전용)
        
        Args:
            vpc_no: VPC 번호 (특정 VPC의 서브넷만 조회)
            subnet_no_list: 조회할 서브넷 번호 목록
            
        Returns:
            서브넷 정보 목록
        """
        if self.platform != "VPC":
            raise NCPAPIError("서브넷 서비스는 VPC 플랫폼에서만 사용 가능합니다.")
        
        params = {}
        if vpc_no:
            params['vpcNo'] = vpc_no
        if subnet_no_list:
            for i, subnet_no in enumerate(subnet_no_list):
                params[f'subnetNoList.{i+1}'] = subnet_no
        
        response = self._make_request('GET', 'vpc', 'getSubnetList', params)
        
        if 'getSubnetListResponse' in response:
            return response['getSubnetListResponse'].get('subnetList', [])
        return []
    
    def get_route_table_list(self, vpc_no: str = None, route_table_no_list: List[str] = None) -> List[Dict]:
        """
        라우트 테이블 목록 조회 (VPC 플랫폼 전용)
        
        Args:
            vpc_no: VPC 번호 (특정 VPC의 라우트 테이블만 조회)
            route_table_no_list: 조회할 라우트 테이블 번호 목록
            
        Returns:
            라우트 테이블 정보 목록
        """
        if self.platform != "VPC":
            raise NCPAPIError("라우트 테이블 서비스는 VPC 플랫폼에서만 사용 가능합니다.")
        
        params = {}
        if vpc_no:
            params['vpcNo'] = vpc_no
        if route_table_no_list:
            for i, route_table_no in enumerate(route_table_no_list):
                params[f'routeTableNoList.{i+1}'] = route_table_no
        
        response = self._make_request('GET', 'vpc', 'getRouteTableList', params)
        
        if 'getRouteTableListResponse' in response:
            return response['getRouteTableListResponse'].get('routeTableList', [])
        return []

    def get_paginated_results(self, method: str, service: str, action: str, 
                             params: Dict = None, page_size: int = 100, max_pages: int = None) -> List[Dict]:
        """
        페이지네이션을 지원하는 API 결과 조회
        
        Args:
            method: HTTP 메서드
            service: 서비스 이름
            action: API 액션
            params: 요청 파라미터
            page_size: 페이지당 항목 수
            max_pages: 최대 페이지 수 (None이면 모든 페이지)
            
        Returns:
            모든 페이지의 결과를 합친 리스트
        """
        all_results = []
        page_no = 1
        
        if params is None:
            params = {}
        
        while True:
            # 페이지네이션 파라미터 추가
            paginated_params = params.copy()
            paginated_params['pageNo'] = page_no
            paginated_params['pageSize'] = page_size
            
            try:
                response = self._make_request(method, service, action, paginated_params)
                
                # 응답에서 결과 추출 (API별로 다를 수 있음)
                response_key = f"{action}Response"
                if response_key in response:
                    page_results = response[response_key].get('list', [])
                    if not page_results:
                        break
                    
                    all_results.extend(page_results)
                    
                    # 총 개수 확인 (더 이상 결과가 없으면 중단)
                    total_count = response[response_key].get('totalCount', 0)
                    if len(all_results) >= total_count:
                        break
                    
                    # 최대 페이지 수 확인
                    if max_pages and page_no >= max_pages:
                        break
                    
                    page_no += 1
                else:
                    break
                    
            except NCPAPIError as e:
                logger.error(f"페이지네이션 조회 실패 (페이지 {page_no}): {e}")
                break
        
        logger.debug(f"페이지네이션 완료: 총 {len(all_results)}개 항목, {page_no-1}페이지")
        return all_results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        성능 통계 정보 반환
        
        Returns:
            성능 관련 통계 정보
        """
        return {
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'backoff_factor': self.backoff_factor,
            'region': self.region,
            'platform': self.platform
        }
    
    def close(self):
        """
        클라이언트 리소스 정리
        """
        if hasattr(self, 'session'):
            self.session.close()
            logger.debug("NCP Client 세션 종료")
    
    def __enter__(self):
        """Context manager 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()
    
    def test_connection(self) -> bool:
        """
        연결 테스트
        
        Returns:
            연결 성공 여부
        """
        try:
            # 간단한 API 호출로 연결 테스트
            start_time = time.time()
            self.get_server_instances()
            elapsed_time = time.time() - start_time
            logger.debug(f"NCP 연결 테스트 성공: {elapsed_time:.2f}초")
            return True
        except Exception as e:
            logger.error(f"NCP 연결 테스트 실패: {e}")
            return False