"""
customer_relations CRUD — 가족 정보 (본인/배우자/자녀1~4 + 동적 추가)

엔드포인트:
- GET    /api/v1/relations/customer/{customer_id}  - 고객별 가족 목록
- POST   /api/v1/relations                          - 단일 가족 추가
- POST   /api/v1/relations/bulk                     - 여러 가족 일괄 추가/교체
- PATCH  /api/v1/relations/{relation_id}            - 가족 정보 수정
- DELETE /api/v1/relations/{relation_id}            - 가족 삭제
"""
from fastapi import APIRouter, HTTPException
from typing import List
from datetime import date
from models.schemas import (
    CustomerRelationCreate,
    CustomerRelationUpdate,
    CustomerRelationBase,
    ApiResponse,
)
from services.supabase_client import supabase

router = APIRouter(prefix="/api/v1/relations", tags=["relations"])


def _serialize_dates(data: dict) -> dict:
    return {
        k: (v.isoformat() if isinstance(v, date) else v)
        for k, v in data.items()
        if v is not None
    }


@router.get("/customer/{customer_id}")
def list_relations(customer_id: str):
    """고객별 가족 정보 조회 (sort_order 정렬)"""
    try:
        result = supabase.table("customer_relations") \
            .select("*") \
            .eq("customer_id", customer_id) \
            .order("sort_order") \
            .execute()
        return ApiResponse(success=True, data=result.data or [], message=f"{len(result.data or [])}명")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_relation(body: CustomerRelationCreate):
    """단일 가족 정보 추가"""
    try:
        data = body.model_dump(exclude_none=True)
        data = _serialize_dates(data)
        result = supabase.table("customer_relations").insert(data).execute()
        return ApiResponse(
            success=True,
            data=result.data[0] if result.data else {},
            message="가족 정보 추가 완료"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BulkReplaceBody(CustomerRelationBase):
    pass


@router.post("/bulk/{customer_id}")
def bulk_replace_relations(customer_id: str, body: List[CustomerRelationBase]):
    """
    가족 정보 일괄 교체 — 기존 행 모두 삭제 후 새로 입력
    프론트엔드의 고객 폼에서 가족 8행을 한 번에 저장할 때 사용.
    """
    try:
        # 1) 기존 가족 모두 삭제
        supabase.table("customer_relations").delete().eq("customer_id", customer_id).execute()

        # 2) 새 가족 정보 일괄 insert
        if not body:
            return ApiResponse(success=True, data=[], message="가족 정보 0건")

        payload = []
        for idx, rel in enumerate(body):
            rel_data = rel.model_dump(exclude_none=True)
            rel_data = _serialize_dates(rel_data)
            rel_data["customer_id"] = customer_id
            if rel_data.get("sort_order") is None:
                rel_data["sort_order"] = idx
            payload.append(rel_data)

        result = supabase.table("customer_relations").insert(payload).execute()
        return ApiResponse(
            success=True,
            data=result.data or [],
            message=f"{len(result.data or [])}명 일괄 등록"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{relation_id}")
def update_relation(relation_id: str, body: CustomerRelationUpdate):
    """가족 정보 수정"""
    try:
        data = body.model_dump(exclude_none=True)
        data = _serialize_dates(data)
        if not data:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")
        result = supabase.table("customer_relations").update(data).eq("id", relation_id).execute()
        return ApiResponse(
            success=True,
            data=result.data[0] if result.data else {},
            message="수정 완료"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{relation_id}")
def delete_relation(relation_id: str):
    """가족 정보 삭제"""
    try:
        supabase.table("customer_relations").delete().eq("id", relation_id).execute()
        return ApiResponse(success=True, message="삭제 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
