from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from datetime import date
from models.schemas import CustomerCreate, CustomerUpdate, ApiResponse
from services.supabase_client import supabase
from services.audit import log_audit
from services.auth import get_current_user, scope_by_agent

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _serialize_dates(data: dict) -> dict:
    """Pydantic date 필드를 PostgreSQL TEXT로 직렬화 (Supabase는 자동 변환 안함)"""
    return {
        k: (v.isoformat() if isinstance(v, date) else v)
        for k, v in data.items()
        if v is not None
    }


@router.get("")
def get_customers(
    status: Optional[str] = Query(None, description="관리상태 필터"),
    category: Optional[str] = Query(None, description="고객구분 필터"),
    search: Optional[str] = Query(None, description="이름/연락처 검색"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """고객 목록 조회 (검색/필터/페이징) — 일반 유저는 자기 고객만, 관리자는 전체"""
    try:
        query = supabase.table("customers").select("*")
        query = scope_by_agent(query, user)   # 관리자 아니면 agent_id=내것 강제
        if status:
            query = query.eq("status", status)
        if category:
            query = query.eq("category", category)
        if search:
            query = query.or_(f"name.ilike.%{search}%,phone.ilike.%{search}%")
        offset = (page - 1) * size
        result = query.order("created_at", desc=True).range(offset, offset + size - 1).execute()

        customers = result.data or []
        customer_ids = [c["id"] for c in customers]
        if customer_ids:
            acts = supabase.table("activities") \
                .select("customer_id, activity_date") \
                .in_("customer_id", customer_ids) \
                .order("activity_date", desc=True) \
                .execute()
            latest = {}
            for a in acts.data or []:
                cid = a.get("customer_id")
                if cid and cid not in latest:
                    latest[cid] = a.get("activity_date")
            for c in customers:
                c["last_contact_date"] = latest.get(c["id"])

        return ApiResponse(success=True, data=customers, message=f"{len(customers)}건 조회")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-by-contract")
def search_by_contract_preview(
    insurer: Optional[str] = Query(None),
    product_name: Optional[str] = Query(None),
    policy_number: Optional[str] = Query(None),
    contractor_name: Optional[str] = Query(None),
    insured_name: Optional[str] = Query(None),
):
    """계약 정보로 고객 검색 — /{customer_id} 보다 먼저 정의해야 함"""
    try:
        if not any([insurer, product_name, policy_number, contractor_name, insured_name]):
            raise HTTPException(status_code=400, detail="검색 조건을 하나 이상 입력해주세요.")

        q = supabase.table("contracts").select("*, customers(*)")
        if insurer:          q = q.ilike("insurer", f"%{insurer}%")
        if product_name:     q = q.ilike("product_name", f"%{product_name}%")
        if policy_number:    q = q.ilike("policy_number", f"%{policy_number}%")
        if contractor_name:  q = q.ilike("contractor_name", f"%{contractor_name}%")
        if insured_name:     q = q.ilike("insured_name", f"%{insured_name}%")

        result = q.execute()
        seen, customers = set(), []
        for c in result.data or []:
            cust = c.get("customers")
            if cust and cust.get("id") not in seen:
                seen.add(cust["id"])
                cust["matched_contract"] = {k: c.get(k) for k in
                    ("insurer", "product_name", "policy_number", "contractor_name", "insured_name", "contract_date")}
                customers.append(cust)

        return ApiResponse(success=True, data=customers, message=f"{len(customers)}명")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}")
def get_customer(
    customer_id: str,
    with_relations: bool = Query(True, description="가족 정보 포함"),
    user: dict = Depends(get_current_user),
):
    """고객 상세 조회 — 가족 정보(relations) 포함. 소유권 검증."""
    try:
        result = supabase.table("customers").select("*").eq("id", customer_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")

        customer = result.data
        # 소유권 검증: 본인 고객 또는 관리자만 접근
        if not user.get("is_admin") and customer.get("agent_id") != user["id"]:
            raise HTTPException(status_code=403, detail="이 고객 정보에 접근할 권한이 없습니다.")

        if with_relations:
            relations = supabase.table("customer_relations") \
                .select("*") \
                .eq("customer_id", customer_id) \
                .order("sort_order") \
                .execute()
            customer["relations"] = relations.data or []

        return ApiResponse(success=True, data=customer)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_customer(body: CustomerCreate, user: dict = Depends(get_current_user)):
    """고객 등록 — 가족 정보(relations) 함께 nested 입력 가능. agent_id 자동 부여."""
    try:
        # 1) customer 본체 분리 (relations는 별도)
        customer_data = body.model_dump(exclude={"relations"}, exclude_none=True)
        customer_data = _serialize_dates(customer_data)
        customer_data["agent_id"] = user["id"]   # 소유자 자동 기입

        result = supabase.table("customers").insert(customer_data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="고객 등록 실패")

        new_customer = result.data[0]
        customer_id = new_customer["id"]

        # 2) relations nested insert
        if body.relations:
            relations_payload = []
            for rel in body.relations:
                rel_data = rel.model_dump(exclude_none=True)
                rel_data = _serialize_dates(rel_data)
                rel_data["customer_id"] = customer_id
                relations_payload.append(rel_data)

            if relations_payload:
                rel_result = supabase.table("customer_relations").insert(relations_payload).execute()
                new_customer["relations"] = rel_result.data or []
        else:
            new_customer["relations"] = []

        return ApiResponse(success=True, data=new_customer, message="고객이 등록되었습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{customer_id}")
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    user: dict = Depends(get_current_user),
):
    """고객 정보 수정 (relations는 /api/v1/relations 별도 endpoint 사용). 소유권 검증."""
    try:
        data = body.model_dump(exclude_none=True)
        data = _serialize_dates(data)
        if not data:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")

        # 감사 로그: 수정 전 데이터 조회 + 소유권 검증
        before = supabase.table("customers").select("*").eq("id", customer_id).maybe_single().execute()
        before_data = before.data if before else None
        if before_data and not user.get("is_admin") and before_data.get("agent_id") != user["id"]:
            raise HTTPException(status_code=403, detail="이 고객 정보를 수정할 권한이 없습니다.")

        result = supabase.table("customers").update(data).eq("id", customer_id).execute()
        after_data = result.data[0] if result.data else {}

        log_audit("customers", customer_id, "UPDATE", before_data=before_data, after_data=after_data)
        return ApiResponse(success=True, data=after_data, message="수정되었습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{customer_id}")
def delete_customer(customer_id: str, user: dict = Depends(get_current_user)):
    """고객 삭제 (CASCADE로 relations, contracts, medical_notes 모두 삭제). 소유권 검증."""
    try:
        # 감사 로그: 삭제 전 데이터 조회 + 소유권 검증
        before = supabase.table("customers").select("*").eq("id", customer_id).maybe_single().execute()
        before_data = before.data if before else None
        if before_data and not user.get("is_admin") and before_data.get("agent_id") != user["id"]:
            raise HTTPException(status_code=403, detail="이 고객을 삭제할 권한이 없습니다.")

        supabase.table("customers").delete().eq("id", customer_id).execute()
        log_audit("customers", customer_id, "DELETE", before_data=before_data)
        return ApiResponse(success=True, message="삭제되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
