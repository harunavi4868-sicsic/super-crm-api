from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
from services.supabase_client import supabase
from models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ALLOWED_ROLES = ["user", "admin"]   # superadmin은 SQL로만 부여


# ── JWT 토큰으로 요청자 인증 + 권한 확인 ──────────────
def get_caller_profile(authorization: str):
    """Authorization: Bearer <token> 헤더에서 사용자 정보 추출"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    token = authorization.split(" ", 1)[1]
    try:
        user_resp = supabase.auth.get_user(token)
        user = user_resp.user
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    if not user:
        raise HTTPException(status_code=401, detail="인증 실패")

    profile_resp = supabase.table("user_profiles").select("*").eq("id", str(user.id)).single().execute()
    profile = profile_resp.data
    if not profile:
        raise HTTPException(status_code=403, detail="프로필을 찾을 수 없습니다.")
    return profile


def require_superadmin(authorization: str):
    profile = get_caller_profile(authorization)
    if profile.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="최고 경영자만 접근 가능합니다.")
    return profile


def require_admin(authorization: str):
    profile = get_caller_profile(authorization)
    if profile.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="관리자만 접근 가능합니다.")
    return profile


# ── 요청 스키마 ────────────────────────────────────────
class SetRoleRequest(BaseModel):
    email: str
    role: str   # 'user' | 'admin'

class ToggleActiveRequest(BaseModel):
    user_id: str
    is_active: bool

class InviteUserRequest(BaseModel):
    email: str
    name: Optional[str] = None
    role: str = "user"


# ── 엔드포인트 ─────────────────────────────────────────

@router.get("/users")
def list_users(authorization: str = Header(None)):
    """전체 회원 목록 조회 (admin 이상)"""
    require_admin(authorization)
    result = supabase.table("user_profiles").select("*").order("created_at", desc=True).execute()
    return ApiResponse(success=True, data=result.data, message=f"{len(result.data)}명 조회")


@router.post("/set-role")
def set_role(req: SetRoleRequest, authorization: str = Header(None)):
    """이메일로 사용자 역할 변경 (superadmin 전용)"""
    caller = require_superadmin(authorization)

    if req.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"허용 역할: {ALLOWED_ROLES}")

    # 대상 사용자 조회
    target = supabase.table("user_profiles").select("*").eq("email", req.email).execute()
    if not target.data:
        raise HTTPException(status_code=404, detail=f"{req.email} 사용자를 찾을 수 없습니다. 먼저 회원가입이 필요합니다.")

    t = target.data[0]
    if t.get("role") == "superadmin":
        raise HTTPException(status_code=403, detail="최고 경영자 계정은 변경할 수 없습니다.")
    if t.get("id") == caller.get("id"):
        raise HTTPException(status_code=400, detail="본인 계정의 역할은 변경할 수 없습니다.")

    supabase.table("user_profiles").update({"role": req.role}).eq("email", req.email).execute()
    role_label = "센터 관리자" if req.role == "admin" else "일반 설계사"
    return ApiResponse(success=True, data={"email": req.email, "role": req.role},
                       message=f"{req.email} → {role_label} 변경 완료")


@router.post("/toggle-active")
def toggle_active(req: ToggleActiveRequest, authorization: str = Header(None)):
    """회원 활성/비활성 토글 (superadmin 전용)"""
    caller = require_superadmin(authorization)
    if req.user_id == caller.get("id"):
        raise HTTPException(status_code=400, detail="본인 계정은 변경할 수 없습니다.")

    target = supabase.table("user_profiles").select("role").eq("id", req.user_id).single().execute()
    if target.data and target.data.get("role") == "superadmin":
        raise HTTPException(status_code=403, detail="최고 경영자 계정은 변경할 수 없습니다.")

    supabase.table("user_profiles").update({"is_active": req.is_active}).eq("id", req.user_id).execute()
    return ApiResponse(success=True, data=None,
                       message=f"{'활성' if req.is_active else '비활성'} 변경 완료")
