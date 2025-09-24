#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import oci
from rich.console import Console

def get_all_subscribed_regions(identity_client, tenancy_ocid):
    """테넌시가 구독한 모든 리전 목록을 반환"""
    try:
        resp = identity_client.list_region_subscriptions(tenancy_ocid)
        return [r.region_name for r in resp.data]
    except Exception as e:
        Console().print(f"[red]리전 구독 정보 조회 실패: {e}[/red]")
        return []

def get_compartments(identity_client, tenancy_ocid, compartment_filter=None, console=None):
    """활성 상태의 모든 컴파트먼트 목록을 반환 (루트 포함)"""
    if console is None:
        console = Console()
    try:
        comps = []
        resp = identity_client.list_compartments(
            tenancy_ocid,
            compartment_id_in_subtree=True,
            lifecycle_state="ACTIVE"
        )
        comps.extend(resp.data)
        # 루트 컴파트먼트 추가
        root_comp = identity_client.get_compartment(tenancy_ocid).data
        comps.append(root_comp)
    except Exception as e:
        console.print(f"[red]컴파트먼트 조회 실패: {e}[/red]")
        sys.exit(1)

    if compartment_filter:
        # 쉼표로 구분된 여러 필터 처리
        filters = [f.strip().lower() for f in compartment_filter.split(',')]
        # any()를 사용하여 필터 중 하나라도 컴파트먼트 이름에 포함되면 선택
        comps = [c for c in comps if any(f in c.name.lower() for f in filters)]
    return comps 