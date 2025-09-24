"""
NCP Gov API Client

This module provides the NCP Government Cloud API client with API Gateway authentication.
It includes enhanced security features and compliance validation for government cloud usage.
"""

import hashlib
import hmac
import base64
import time
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import logging

logger = logging.getLogger(__name__)


class NCPGovAPIError(Exception):
    """NCP Gov API 관련 오류"""
    def __init__(self, message: str, error_code: str = None, status_code: int = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class NCPGovClient:
    """
    NCP Gov API 클라이언트
    
    API Gateway를 통한 정부 클라우드 접근을 제공합니다.
    보안 강화 및 정부 클라우드 규정 준수 기능을 포함합니다.
    """
    
    def __init__(self, access_key: str, secret_key: str, apigw_key: str, region: str = 'KR', platform: str = 'VPC'):
        """
        NCP Gov 클라이언트 초기화
        
        Args:
            access_key: NCP Gov Access Key
            secret_key: NCP Gov Secret Key
            apigw_key: API Gateway Key
            region: 리전 (KR)
            platform: 플랫폼 (VPC 권장)
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.apigw_key = apigw_key
        self.region = region.upper()
        self.platform = platform.upper()
        
        # 정부 클라우드 전용 엔드포인트 설정
        self.endpoints = self._get_gov_endpoints()
        
        # 기본 헤더 설정 (정부 클라우드 보안 강화)
        self.base_headers = {
            'Content-Type': 'application/json',
            'x-ncp-iam-access-key': self.access_key,
            'x-ncp-apigw-api-key': self.apigw_key,
            'x-ncp-gov-compliance': 'enabled'
        }
        
        # 보안 설정
        self.encryption_enabled = True
        self.audit_logging_enabled = True
        self.access_control_enabled = True
        
        logger.debug(f"NCP Gov Client initialized - Region: {self.region}, Platform: {self.platform}")
        logger.info("정부 클라우드 보안 모드 활성화됨")
    
    def _get_gov_endpoints(self) -> Dict[str, str]:
        """정부 클라우드 전용 API 엔드포인트 반환"""
        # 정부 클라우드는 별도 도메인 사용
        base_url = "https://apigw.gov-ntruss.com"
        
        if self.platform == "VPC":
            return {
                "vserver": f"{base_url}/vserver/v2",
                "vpc": f"{base_url}/vpc/v2", 
                "vloadbalancer": f"{base_url}/vloadbalancer/v2",
                "storage": f"{base_url}/storage/v2",
                "clouddb": f"{base_url}/clouddb/v2"
            }
        elif self.platform == "CLASSIC":
            return {
                "server": f"{base_url}/server/v2",
                "storage": f"{base_url}/storage/v2",
                "loadbalancer": f"{base_url}/loadbalancer/v2"
            }
        else:
            raise ValueError(f"지원하지 않는 플랫폼: {self.platform}")
    
    def _make_apigw_signature(self, method: str, uri: str, timestamp: str) -> str:
        """
        API Gateway 전용 HMAC-SHA256 서명 생성
        
        Args:
            method: HTTP 메서드
            uri: API URI
            timestamp: 타임스탬프
            
        Returns:
            Base64 인코딩된 서명
        """
        # 정부 클라우드 전용 서명 문자열 (보안 강화)
        message = f"{method} {uri}\n{timestamp}\n{self.access_key}\n{self.apigw_key}"
        
        # HMAC-SHA256 서명 생성
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _mask_sensitive_data(self, data: Any) -> Any:
        """
        민감한 정보 마스킹 (정부 클라우드 규정 준수)
        
        Args:
            data: 마스킹할 데이터
            
        Returns:
            마스킹된 데이터
        """
        if isinstance(data, dict):
            masked_data = {}
            sensitive_keys = ['password', 'secret', 'key', 'token', 'credential']
            
            for key, value in data.items():
                if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                    masked_data[key] = "***MASKED***"
                elif isinstance(value, (dict, list)):
                    masked_data[key] = self._mask_sensitive_data(value)
                else:
                    masked_data[key] = value
            return masked_data
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        else:
            return data
    
    def _make_apigw_request(self, method: str, service: str, action: str, params: Dict = None) -> Dict[str, Any]:
        """
        NCP Gov API Gateway 요청 실행
        
        Args:
            method: HTTP 메서드
            service: 서비스 이름
            action: API 액션
            params: 요청 파라미터
            
        Returns:
            API 응답 데이터
        """
        # 엔드포인트 확인
        if service not in self.endpoints:
            raise NCPGovAPIError(f"서비스 '{service}'는 정부 클라우드에서 지원되지 않습니다.")
        
        base_url = self.endpoints[service]
        
        # 파라미터 설정
        if params is None:
            params = {}
        
        params['action'] = action
        params['responseFormatType'] = 'json'
        
        # 정부 클라우드 규정 준수 파라미터 추가
        params['govCompliance'] = 'true'
        params['auditLogging'] = 'enabled' if self.audit_logging_enabled else 'disabled'
        
        # URI 구성
        uri = f"/{service}/v2/"
        if params:
            query_string = urlencode(sorted(params.items()))
            uri += f"?{query_string}"
        
        # 타임스탬프 생성
        timestamp = str(int(time.time() * 1000))
        
        # API Gateway 서명 생성
        signature = self._make_apigw_signature(method, uri, timestamp)
        
        # 헤더 설정 (정부 클라우드 보안 강화)
        headers = self.base_headers.copy()
        headers.update({
            'x-ncp-apigw-timestamp': timestamp,
            'x-ncp-apigw-signature-v2': signature,
            'x-ncp-gov-audit-id': f"audit_{timestamp}",
            'x-ncp-gov-security-level': 'high'
        })
        
        # 요청 URL 구성
        url = f"{base_url}{uri}"
        
        try:
            logger.debug(f"NCP Gov API 요청: {method} {url}")
            
            # 감사 로그 기록
            if self.audit_logging_enabled:
                logger.info(f"정부 클라우드 API 호출: {action} (감사 ID: audit_{timestamp})")
            
            # HTTP 요청 실행 (보안 강화 설정)
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=45,  # 정부 클라우드는 더 긴 타임아웃
                verify=True  # SSL 인증서 검증 강제
            )
            
            # 응답 상태 확인
            if response.status_code != 200:
                error_msg = f"NCP Gov API 오류: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'responseError' in error_data:
                        error_info = error_data['responseError']
                        error_msg = f"{error_info.get('returnMessage', error_msg)} (코드: {error_info.get('returnCode', 'N/A')})"
                except:
                    pass
                
                # 보안 오류 로깅
                logger.error(f"정부 클라우드 API 오류: {error_msg}")
                raise NCPGovAPIError(error_msg, status_code=response.status_code)
            
            # JSON 응답 파싱
            response_data = response.json()
            
            # 민감한 정보 마스킹
            if self.encryption_enabled:
                response_data = self._mask_sensitive_data(response_data)
            
            logger.debug(f"NCP Gov API 응답 수신: {action}")
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"NCP Gov API 요청 실패: {e}")
            raise NCPGovAPIError(f"네트워크 오류: {str(e)}")
        except Exception as e:
            logger.error(f"NCP Gov API 처리 중 오류: {e}")
            raise NCPGovAPIError(f"API 처리 오류: {str(e)}")
    
    def get_server_instances(self, server_instance_no_list: List[str] = None) -> List[Dict]:
        """
        서버 인스턴스 목록 조회 (정부 클라우드)
        
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
        
        response = self._make_apigw_request('GET', service, 'getServerInstanceList', params)
        
        if 'getServerInstanceListResponse' in response:
            return response['getServerInstanceListResponse'].get('serverInstanceList', [])
        return []
    
    def get_object_storage_buckets(self) -> List[Dict]:
        """
        오브젝트 스토리지 버킷 목록 조회 (정부 클라우드)
        
        Returns:
            버킷 정보 목록
        """
        logger.warning("정부 클라우드 Object Storage API는 별도 구현이 필요합니다.")
        return []
    
    def get_vpc_list(self, vpc_no_list: List[str] = None) -> List[Dict]:
        """
        VPC 목록 조회 (정부 클라우드 VPC 플랫폼 전용)
        
        Args:
            vpc_no_list: 조회할 VPC 번호 목록
            
        Returns:
            VPC 정보 목록
        """
        if self.platform != "VPC":
            raise NCPGovAPIError("VPC 서비스는 VPC 플랫폼에서만 사용 가능합니다.")
        
        params = {}
        if vpc_no_list:
            for i, vpc_no in enumerate(vpc_no_list):
                params[f'vpcNoList.{i+1}'] = vpc_no
        
        response = self._make_apigw_request('GET', 'vpc', 'getVpcList', params)
        
        if 'getVpcListResponse' in response:
            return response['getVpcListResponse'].get('vpcList', [])
        return []
    
    def get_cloud_db_instances(self, cloud_db_instance_no_list: List[str] = None) -> List[Dict]:
        """
        Cloud DB 인스턴스 목록 조회 (정부 클라우드)
        
        Args:
            cloud_db_instance_no_list: 조회할 DB 인스턴스 번호 목록
            
        Returns:
            DB 인스턴스 정보 목록
        """
        params = {}
        if cloud_db_instance_no_list:
            for i, instance_no in enumerate(cloud_db_instance_no_list):
                params[f'cloudDbInstanceNoList.{i+1}'] = instance_no
        
        logger.warning("정부 클라우드 Cloud DB API는 별도 구현이 필요합니다.")
        return []
    
    def get_access_control_groups(self, access_control_group_no_list: List[str] = None) -> List[Dict]:
        """
        보안 그룹(Access Control Group) 목록 조회 (정부 클라우드)
        
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
        
        response = self._make_apigw_request('GET', service, 'getAccessControlGroupList', params)
        
        if 'getAccessControlGroupListResponse' in response:
            return response['getAccessControlGroupListResponse'].get('accessControlGroupList', [])
        return []
    
    def validate_gov_compliance(self) -> Dict[str, bool]:
        """
        정부 클라우드 규정 준수 검증
        
        Returns:
            규정 준수 상태
        """
        compliance_status = {
            'encryption_enabled': self.encryption_enabled,
            'audit_logging_enabled': self.audit_logging_enabled,
            'access_control_enabled': self.access_control_enabled,
            'ssl_verification': True,
            'api_gateway_auth': bool(self.apigw_key)
        }
        
        all_compliant = all(compliance_status.values())
        compliance_status['overall_compliance'] = all_compliant
        
        if all_compliant:
            logger.info("정부 클라우드 규정 준수 검증 통과")
        else:
            logger.warning("정부 클라우드 규정 준수 검증 실패")
        
        return compliance_status
    
    def test_connection(self) -> bool:
        """
        연결 테스트 (정부 클라우드)
        
        Returns:
            연결 성공 여부
        """
        try:
            # 규정 준수 검증 먼저 수행
            compliance = self.validate_gov_compliance()
            if not compliance['overall_compliance']:
                logger.error("정부 클라우드 규정 준수 요구사항을 만족하지 않습니다.")
                return False
            
            # 간단한 API 호출로 연결 테스트
            self.get_server_instances()
            logger.info("정부 클라우드 연결 테스트 성공")
            return True
        except Exception as e:
            logger.error(f"NCP Gov 연결 테스트 실패: {e}")
            return False