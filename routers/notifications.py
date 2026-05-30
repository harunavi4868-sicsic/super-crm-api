"""
notifications.py — 알림 읽음 상태 관리 API
notification_reads 테이블 기반 읽음/미읽음 추적
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
from services.supabase_client import supabase
from models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _get_user_id(authorization: str) -> Optional[str]:
    """JWT 토큰에서 user_id 추출"""
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    try:
        resp = supabase.auth.get_user(token)
        return str(resp.user.id) if resp.user else None
    except Exception:
        return None


class MarkReadBody(BaseModel):
    notification_type: str   # birthday | anniversary | renewal | policy_anniversary
    reference_id: Optional[str] = None  # 고객 또는 계약 UUID


@router.post("/read")
def mark_as_read(
    body: MarkReadBody,
    authorization: str = Header(...),
):
    """알림 읽음 처리 (중복 무시)"""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    try:
        supabase.table("notification_reads").upsert({
            "user_id": user_id,
            "notification_type": body.notification_type,
            "reference_id": body.reference_id,
        }, on_conflict="user_id,notification_type,reference_id").execute()
        return ApiResponse(success=True, message="읽음 처리 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unread-count")
def get_unread_count(authorization: str = Header(...)):
    """알림 유형별 미읽음 카운트 반환"""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    try:
        # 읽은 알림 목록
        reads = supabase.table("notification_reads") \
            .select("notification_type, reference_id") \
            .eq("user_id", user_id) \
            .execute().data or []
        read_set = {(r["notification_type"], r.get("reference_id")) for r in reads}

        from datetime import date
        today = date.today()

        # 생일 알림 — 이번 달
        customers = supabase.table("customers") \
            .select("id, birth_date") \
            .eq("status", "active") \
            .not_.is_("birth_date", "null") \
            .execute().data or []
        birthday_unread = sum(
            1 for c in customers
            if c.get("birth_date")
            and int(c["birth_date"][5:7]) == today.month
            and ("birthday", c["id"]) not in read_set
        )

        # 갱신 알림 — 90일 이내
        contracts = supabase.table("contracts") \
            .select("id, contract_date, insurance_expiry, payment_expiry") \
            .eq("status", "active") \
            .execute().data or []
        from datetime import timedelta
        renewal_unread = 0
        for c in contracts:
            expiry = c.get("insurance_expiry") or c.get("payment_expiry") or c.get("contract_date")
            if not expiry:
                continue
            try:
                from datetime import date as d_type
                exp_date = d_type.fromisoformat(expiry)
                # 계약일만 있는 경우 연간 갱신 기준
                if not c.get("insurance_expiry") and not c.get("payment_expiry"):
                    exp_date = exp_date.replace(year=today.year)
                    if exp_date < today:
                        exp_date = exp_date.replace(year=today.year + 1)
                if 0 <= (exp_date - today).days <= 90:
                    if ("renewal", c["id"]) not in read_set:
                        renewal_unread += 1
            except Exception:
                continue

        return ApiResponse(success=True, data={
            "birthday": birthday_unread,
            "renewal": renewal_unread,
            "total": birthday_unread + renewal_unread,
        }, message="미읽음 카운트")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/read")
def mark_all_unread(
    notification_type: str,
    authorization: str = Header(...),
):
    """특정 유형 알림 읽음 초기화 (전체 미읽음으로)"""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    try:
        supabase.table("notification_reads") \
            .delete() \
            .eq("user_id", user_id) \
            .eq("notification_type", notification_type) \
            .execute()
        return ApiResponse(success=True, message="읽음 초기화 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
