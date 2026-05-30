from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from models.schemas import CodeCreate, ApiResponse
from services.supabase_client import supabase

router = APIRouter(prefix="/api/v1/codes", tags=["codes"])


@router.get("")
def get_codes(group_name: Optional[str] = Query(None, description="분류명 필터")):
    """공통 코드 목록 조회"""
    try:
        query = supabase.table("common_codes").select("*").eq("is_active", True)
        if group_name:
            query = query.eq("group_name", group_name)
        result = query.order("group_name").order("sort_order").execute()
        return ApiResponse(success=True, data=result.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_code(body: CodeCreate):
    """공통 코드 등록"""
    try:
        result = supabase.table("common_codes").insert(body.model_dump()).execute()
        return ApiResponse(success=True, data=result.data[0], message="코드가 등록되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
