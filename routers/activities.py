from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from models.schemas import ActivityCreate, ActivityUpdate, ApiResponse
from services.supabase_client import supabase
from services.auth import get_current_user, scope_by_agent

router = APIRouter(prefix="/api/v1/activities", tags=["activities"])


@router.get("")
def get_activities(
    customer_id: Optional[str] = Query(None, description="고객 ID 필터"),
    activity_type: Optional[str] = Query(None, description="활동유형 필터"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """활동 기록 목록 조회 — 일반 유저는 자기 것만, 관리자는 전체"""
    try:
        query = supabase.table("activities").select("*, customers(name, phone)")
        query = scope_by_agent(query, user)
        if customer_id:
            query = query.eq("customer_id", customer_id)
        if activity_type:
            query = query.eq("activity_type", activity_type)
        offset = (page - 1) * size
        result = query.order("activity_date", desc=True).range(offset, offset + size - 1).execute()
        return ApiResponse(success=True, data=result.data, message=f"{len(result.data)}건 조회")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{activity_id}")
def get_activity(activity_id: str):
    """활동 기록 상세 조회"""
    try:
        result = supabase.table("activities").select("*, customers(name, phone)").eq("id", activity_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
        return ApiResponse(success=True, data=result.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_activity(body: ActivityCreate, user: dict = Depends(get_current_user)):
    """활동 기록 등록 — agent_id 자동 부여"""
    try:
        data = body.model_dump(exclude_none=True)
        data["activity_date"] = str(body.activity_date)
        data["agent_id"] = user["id"]
        result = supabase.table("activities").insert(data).execute()
        return ApiResponse(success=True, data=result.data[0], message="활동 기록이 등록되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{activity_id}")
def update_activity(activity_id: str, body: ActivityUpdate):
    """활동 기록 수정"""
    try:
        data = body.model_dump(exclude_none=True)
        if body.activity_date:
            data["activity_date"] = str(body.activity_date)
        result = supabase.table("activities").update(data).eq("id", activity_id).execute()
        return ApiResponse(success=True, data=result.data[0], message="수정되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{activity_id}")
def delete_activity(activity_id: str):
    """활동 기록 삭제"""
    try:
        supabase.table("activities").delete().eq("id", activity_id).execute()
        return ApiResponse(success=True, message="삭제되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
