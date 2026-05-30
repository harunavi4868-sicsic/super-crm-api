"""인증/권한 의존성 — 모든 라우터에서 재사용.

사용:
    from services.auth import get_current_user

    @router.get("")
    def list_things(user = Depends(get_current_user)):
        # user["id"], user["role"], user["is_admin"]
"""
import time
from fastapi import Header, HTTPException
from typing import Optional
from services.supabase_client import supabase


# 토큰별 user dict 캐시 — Supabase 왕복 2회 줄임
# 토큰이 동일하면 같은 사용자이므로 60초 캐시는 안전
_USER_CACHE: dict = {}      # {token: (expires_at, user_dict)}
_CACHE_TTL = 60             # 60초
_CACHE_MAX_SIZE = 2000      # 메모리 폭주 방지


def _cleanup_cache(now: float) -> None:
    """만료 캐시 제거 (사이즈 초과 시에만)"""
    if len(_USER_CACHE) <= _CACHE_MAX_SIZE:
        return
    expired = [k for k, v in _USER_CACHE.items() if v[0] < now]
    for k in expired:
        _USER_CACHE.pop(k, None)


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Authorization: Bearer <token> → user dict.

    반환: {id, email, role, is_admin, profile}
    실패: 401 Unauthorized
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    token = authorization.split(" ", 1)[1]

    # ── 캐시 hit
    now = time.time()
    cached = _USER_CACHE.get(token)
    if cached and cached[0] > now:
        return cached[1]

    # ── 캐시 miss → 실제 검증
    try:
        user_resp = supabase.auth.get_user(token)
        user = user_resp.user
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    if not user:
        raise HTTPException(status_code=401, detail="인증 실패")

    try:
        profile_resp = (
            supabase.table("user_profiles")
            .select("*")
            .eq("id", str(user.id))
            .single()
            .execute()
        )
        profile = profile_resp.data
    except Exception:
        profile = None

    role = (profile or {}).get("role", "user")
    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "role": role,
        "is_admin": role in ("admin", "superadmin"),
        "profile": profile or {},
    }

    # 캐시 저장 + 가끔 정리
    _USER_CACHE[token] = (now + _CACHE_TTL, user_dict)
    _cleanup_cache(now)

    return user_dict


def scope_by_agent(query, user: dict, column: str = "agent_id"):
    """관리자가 아니면 agent_id 필터 적용. 관리자면 그대로 반환."""
    if user.get("is_admin"):
        return query
    return query.eq(column, user["id"])
