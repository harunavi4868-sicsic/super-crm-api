from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import date
from pydantic import BaseModel
from services.supabase_client import supabase
from services.auth import get_current_user, scope_by_agent
from models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])


# ─── Contract v2 — 30+ 필드 (내고객다보여 25 PDF p12 정답지) ─────────
class ContractCreate(BaseModel):
    customer_id: str

    # 기존 (호환)
    insurer: Optional[str] = None
    product_name: Optional[str] = None
    contract_date: Optional[date] = None
    monthly_premium: Optional[int] = None
    payment_period: Optional[str] = None
    insurance_period: Optional[str] = None
    policy_number: Optional[str] = None
    status: Optional[str] = "active"
    memo: Optional[str] = None

    # 인적 정보 (v2)
    family_head: Optional[str] = None
    contractor_name: Optional[str] = None
    contractor_ssn: Optional[str] = None
    contractor_phone: Optional[str] = None
    insured_name: Optional[str] = None
    insured_ssn: Optional[str] = None
    insured_phone: Optional[str] = None
    beneficiary_death: Optional[str] = None
    beneficiary_disability: Optional[str] = None
    relation_to_main: Optional[str] = None

    # 보험 (v2)
    insurance_type: Optional[str] = None
    agent_name: Optional[str] = None
    agent_code: Optional[str] = None
    actual_premium: Optional[int] = None
    recruiter: Optional[str] = None
    sales_company: Optional[str] = None

    # 주계약 (v2)
    main_contract: Optional[str] = None
    insurance_amount: Optional[int] = None
    main_premium: Optional[int] = None
    insurance_period_year: Optional[int] = None
    insurance_period_unit: Optional[str] = None
    insurance_expiry: Optional[date] = None
    payment_period_year: Optional[int] = None
    payment_period_unit: Optional[str] = None
    payment_expiry: Optional[date] = None
    payment_status: Optional[str] = None
    contract_status: Optional[str] = None
    annuity_start: Optional[str] = None
    annuity_type: Optional[str] = None

    # 결제 (v2)
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    withdraw_day: Optional[int] = None

    # 메모 (v2)
    contract_summary: Optional[str] = None
    contract_memo: Optional[str] = None
    contract_source: Optional[str] = None
    registered_date: Optional[date] = None


class ContractUpdate(BaseModel):
    # 기존
    insurer: Optional[str] = None
    product_name: Optional[str] = None
    contract_date: Optional[date] = None
    monthly_premium: Optional[int] = None
    payment_period: Optional[str] = None
    insurance_period: Optional[str] = None
    policy_number: Optional[str] = None
    status: Optional[str] = None
    memo: Optional[str] = None

    # v2 — 인적
    family_head: Optional[str] = None
    contractor_name: Optional[str] = None
    contractor_ssn: Optional[str] = None
    contractor_phone: Optional[str] = None
    insured_name: Optional[str] = None
    insured_ssn: Optional[str] = None
    insured_phone: Optional[str] = None
    beneficiary_death: Optional[str] = None
    beneficiary_disability: Optional[str] = None
    relation_to_main: Optional[str] = None

    # v2 — 보험
    insurance_type: Optional[str] = None
    agent_name: Optional[str] = None
    agent_code: Optional[str] = None
    actual_premium: Optional[int] = None
    recruiter: Optional[str] = None
    sales_company: Optional[str] = None

    # v2 — 주계약
    main_contract: Optional[str] = None
    insurance_amount: Optional[int] = None
    main_premium: Optional[int] = None
    insurance_period_year: Optional[int] = None
    insurance_period_unit: Optional[str] = None
    insurance_expiry: Optional[date] = None
    payment_period_year: Optional[int] = None
    payment_period_unit: Optional[str] = None
    payment_expiry: Optional[date] = None
    payment_status: Optional[str] = None
    contract_status: Optional[str] = None
    annuity_start: Optional[str] = None
    annuity_type: Optional[str] = None

    # v2 — 결제
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    withdraw_day: Optional[int] = None

    # v2 — 메모
    contract_summary: Optional[str] = None
    contract_memo: Optional[str] = None
    contract_source: Optional[str] = None
    registered_date: Optional[date] = None


@router.get("")
def list_all_contracts(
    status: Optional[str] = Query(None, description="상태 필터 (active/cancelled 등)"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """전체 계약 목록 (모든 고객 합쳐서) — 일반 유저는 자기 것만, 관리자는 전체"""
    try:
        q = supabase.table("contracts").select("*, customers(name, phone)")
        q = scope_by_agent(q, user)
        if status:
            q = q.eq("status", status)
        offset = (page - 1) * size
        result = q.order("contract_date", desc=True).range(offset, offset + size - 1).execute()
        return ApiResponse(success=True, data=result.data, message=f"{len(result.data)}건")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}")
def list_contracts(customer_id: str):
    """고객별 계약 목록 조회"""
    try:
        result = supabase.table("contracts") \
            .select("*") \
            .eq("customer_id", customer_id) \
            .order("contract_date", desc=True) \
            .execute()
        return ApiResponse(success=True, data=result.data, message=f"{len(result.data)}건")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contract_id}")
def get_contract(contract_id: str):
    """계약 단일 조회"""
    try:
        result = supabase.table("contracts").select("*").eq("id", contract_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="계약을 찾을 수 없습니다.")
        return ApiResponse(success=True, data=result.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_contract(body: ContractCreate, user: dict = Depends(get_current_user)):
    """계약 등록 (v2 — 30+ 필드). agent_id 자동 부여."""
    try:
        payload = {k: (v.isoformat() if isinstance(v, date) else v)
                   for k, v in body.model_dump().items() if v is not None}
        payload["agent_id"] = user["id"]
        result = supabase.table("contracts").insert(payload).execute()
        return ApiResponse(success=True, data=result.data[0] if result.data else {}, message="계약 등록 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{contract_id}")
def update_contract(contract_id: str, body: ContractUpdate):
    """계약 수정 (v2)"""
    try:
        payload = {k: (v.isoformat() if isinstance(v, date) else v)
                   for k, v in body.model_dump().items() if v is not None}
        if not payload:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")
        result = supabase.table("contracts").update(payload).eq("id", contract_id).execute()
        return ApiResponse(success=True, data=result.data[0] if result.data else {}, message="수정 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{contract_id}")
def delete_contract(contract_id: str):
    """계약 삭제"""
    try:
        supabase.table("contracts").delete().eq("id", contract_id).execute()
        return ApiResponse(success=True, message="삭제 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
def contract_stats():
    """전체 계약 통계"""
    try:
        result = supabase.table("contracts").select("status, monthly_premium").execute()
        data = result.data or []
        total = len(data)
        active = sum(1 for r in data if r.get("status") == "active")
        total_premium = sum(r.get("monthly_premium") or 0 for r in data if r.get("status") == "active")
        return ApiResponse(success=True, data={
            "total": total, "active": active, "total_premium": total_premium
        }, message="통계 조회 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
