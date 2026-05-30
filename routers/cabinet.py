"""
Cabinet (캐비닛 시스템 v3) — 12종 분류 + 사용자 정의 카테고리

엔드포인트:
- GET    /api/v1/cabinet/customer/{customer_id}              - 고객별 전체 캐비닛 (카테고리별 그룹)
- GET    /api/v1/cabinet/customer/{customer_id}/category/{key} - 특정 카테고리만
- POST   /api/v1/cabinet/upload/{customer_id}                - 파일 업로드 (multipart, category_key 필수)
- PATCH  /api/v1/cabinet/{file_id}                           - 메타데이터 수정 (메모/카테고리)
- DELETE /api/v1/cabinet/{file_id}                           - 파일 삭제 (DB + Storage)
- GET    /api/v1/cabinet/categories                          - 12 기본 카테고리 목록 (참조용)

저장 전략:
- 메타데이터: cabinet_files 테이블 (Supabase Postgres)
- 실제 파일: Supabase Storage 'customer-files' 버킷
- 저장 경로: {customer_id}/{category_key}/{timestamp}_{filename}
"""
import re
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional, List
from datetime import datetime
from services.supabase_client import supabase
from services.auth import get_current_user, scope_by_agent
from models.schemas import ApiResponse, CabinetFileUpdate

router = APIRouter(prefix="/api/v1/cabinet", tags=["cabinet"])

BUCKET = "customer-files"
MAX_SIZE = 500 * 1024 * 1024              # 단일 파일 500MB (영상/녹취/큰 PDF 수용)
MAX_TOTAL_PER_CUSTOMER = 10 * 1024 * 1024 * 1024  # 고객당 10GB

# 12 기본 카테고리 (PDF p13)
DEFAULT_CATEGORIES = [
    {"key": "id_card",           "label": "신분증 사본",         "icon": "🪪"},
    {"key": "proposal",          "label": "가입설계서",           "icon": "📋"},
    {"key": "coverage_analysis", "label": "보장분석 자료",        "icon": "📊"},
    {"key": "claim_docs",        "label": "보험금 청구 자료",     "icon": "💰"},
    {"key": "gift_photo",        "label": "선물 사진",            "icon": "🎁"},
    {"key": "kkakto_capture",    "label": "카톡 캡처",            "icon": "💬"},
    {"key": "recording",         "label": "녹취 파일",            "icon": "🎙️"},
    {"key": "family_photo",      "label": "고객/가족 사진",       "icon": "👨‍👩‍👧"},
    {"key": "car_insurance",     "label": "자동차 보험 관련",     "icon": "🚗"},
    {"key": "business_card",     "label": "명함",                 "icon": "📇"},
    {"key": "cs_field",          "label": "CS 현장 사진",         "icon": "📸"},
    {"key": "business_doc",      "label": "사업자/법인 서류",     "icon": "🏢"},
]
DEFAULT_CATEGORY_KEYS = {c["key"] for c in DEFAULT_CATEGORIES} | {"custom"}

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a",  # 녹취 파일
    "text/plain",
}


SIGNED_URL_TTL = 60 * 60  # 1시간 — 화면 보는 동안 안 끊김


def _signed_url(path: str) -> str:
    """Private 버킷용 — 1시간 만료 서명 URL 생성. 실패 시 빈 문자열."""
    if not path:
        return ""
    try:
        result = supabase.storage.from_(BUCKET).create_signed_url(path, SIGNED_URL_TTL)
        # supabase-py는 dict 또는 객체로 반환 (버전별 차이)
        if isinstance(result, dict):
            return result.get("signedURL") or result.get("signed_url") or result.get("signedUrl") or ""
        return getattr(result, "signed_url", "") or getattr(result, "signedURL", "") or ""
    except Exception:
        return ""


def _enrich(rows: list) -> list:
    """DB 행에 1시간 만료 signed URL 동적 부착"""
    out = []
    for r in rows or []:
        item = dict(r)
        item["url"] = _signed_url(item.get("storage_path", ""))
        out.append(item)
    return out


@router.get("/categories")
def list_categories():
    """12 기본 카테고리 목록 (프론트엔드 참조용)"""
    return ApiResponse(success=True, data=DEFAULT_CATEGORIES, message=f"{len(DEFAULT_CATEGORIES)}개")


@router.get("")
def list_all_cabinet_files(
    category_key: Optional[str] = None,
    page: int = 1,
    size: int = 100,
    user: dict = Depends(get_current_user),
):
    """전체 캐비닛 파일 목록 — 일반 유저는 자기 것만, 관리자는 전체"""
    try:
        q = supabase.table("cabinet_files").select("*, customers(name, phone)")
        q = scope_by_agent(q, user)
        if category_key:
            q = q.eq("category_key", category_key)
        offset = (page - 1) * size
        result = q.order("created_at", desc=True).range(offset, offset + size - 1).execute()
        files = _enrich(result.data)
        return ApiResponse(success=True, data=files, message=f"{len(files)}개")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}")
def list_cabinet(customer_id: str):
    """고객별 전체 캐비닛 — 카테고리별 그룹 + 합계"""
    try:
        result = supabase.table("cabinet_files") \
            .select("*") \
            .eq("customer_id", customer_id) \
            .order("created_at", desc=True) \
            .execute()
        files = _enrich(result.data)

        # 카테고리별 그룹
        grouped: dict = {}
        for f in files:
            key = f.get("category_key") or "custom"
            grouped.setdefault(key, []).append(f)

        # 통계
        total_size = sum(f.get("size_bytes") or 0 for f in files)
        return ApiResponse(
            success=True,
            data={
                "files": files,
                "grouped": grouped,
                "total_count": len(files),
                "total_size_bytes": total_size,
                "max_total_bytes": MAX_TOTAL_PER_CUSTOMER,
            },
            message=f"{len(files)}개"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}/category/{category_key}")
def list_cabinet_by_category(customer_id: str, category_key: str):
    """특정 카테고리의 파일 목록"""
    try:
        result = supabase.table("cabinet_files") \
            .select("*") \
            .eq("customer_id", customer_id) \
            .eq("category_key", category_key) \
            .order("created_at", desc=True) \
            .execute()
        files = _enrich(result.data)
        return ApiResponse(success=True, data=files, message=f"{len(files)}개")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{customer_id}")
async def upload_cabinet_file(
    customer_id: str,
    category_key: str = Form(...),
    category_label: Optional[str] = Form(None),
    memo: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """캐비닛 파일 업로드 (multipart/form-data). agent_id 자동 부여."""
    # 1) 카테고리 검증
    if category_key not in DEFAULT_CATEGORY_KEYS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 카테고리: {category_key}")
    if category_key == "custom" and not category_label:
        raise HTTPException(status_code=400, detail="custom 카테고리는 라벨이 필요합니다.")

    # 2) MIME 검증
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다: {file.content_type}"
        )

    # 3) 크기 검증
    contents = await file.read()
    size = len(contents)
    if size > MAX_SIZE:
        raise HTTPException(status_code=400, detail="파일 크기는 500MB 이하만 가능합니다.")

    # 4) 고객당 합계 검증
    try:
        existing = supabase.table("cabinet_files") \
            .select("size_bytes") \
            .eq("customer_id", customer_id) \
            .execute()
        used = sum((r.get("size_bytes") or 0) for r in (existing.data or []))
        if used + size > MAX_TOTAL_PER_CUSTOMER:
            raise HTTPException(
                status_code=400,
                detail=f"고객당 캐비닛 용량 초과 (사용 {used // 1024 // 1024 // 1024}GB / 최대 10GB)"
            )
    except HTTPException:
        raise
    except Exception:
        pass  # 검증 실패해도 업로드는 시도

    # 5) Storage 업로드 — Supabase Storage는 키에 ASCII만 허용 → 한글 파일명 무력화
    try:
        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        original_name = file.filename or "file"
        # 확장자만 안전하게 추출 (영숫자 1~10자 한정)
        ext = ""
        if "." in original_name:
            candidate = "." + original_name.rsplit(".", 1)[-1].lower()
            if re.match(r"^\.[a-zA-Z0-9]{1,10}$", candidate):
                ext = candidate
        # 키 = timestamp_uuid.ext (한글/공백/특수문자 완전 배제)
        safe_name = f"{ts}_{uuid.uuid4().hex[:8]}{ext}"
        storage_path = f"{customer_id}/{category_key}/{safe_name}"

        supabase.storage.from_(BUCKET).upload(
            storage_path,
            contents,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage 업로드 오류: {str(e)}")

    # 6) DB insert
    try:
        payload = {
            "customer_id": customer_id,
            "category_key": category_key,
            "category_label": category_label,
            "filename": safe_name,
            "original_name": original_name,
            "storage_path": storage_path,
            "storage_bucket": BUCKET,
            "size_bytes": size,
            "mime_type": file.content_type,
            "memo": memo,
            "agent_id": user["id"],
        }
        result = supabase.table("cabinet_files").insert(payload).execute()
        row = result.data[0] if result.data else payload
        row["url"] = _signed_url(storage_path)
        return ApiResponse(success=True, data=row, message="업로드 완료")
    except Exception as e:
        # Storage는 올라갔는데 DB 실패 → 롤백
        try:
            supabase.storage.from_(BUCKET).remove([storage_path])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"DB 저장 오류: {str(e)}")


@router.patch("/{file_id}")
def update_cabinet_file(file_id: str, body: CabinetFileUpdate):
    """캐비닛 파일 메타데이터 수정 (메모/카테고리/태그)"""
    try:
        data = body.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")
        if "category_key" in data and data["category_key"] not in DEFAULT_CATEGORY_KEYS:
            raise HTTPException(status_code=400, detail=f"알 수 없는 카테고리: {data['category_key']}")

        result = supabase.table("cabinet_files").update(data).eq("id", file_id).execute()
        row = result.data[0] if result.data else {}
        if row:
            row["url"] = _signed_url(row.get("storage_path", ""))
        return ApiResponse(success=True, data=row, message="수정 완료")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{file_id}")
def delete_cabinet_file(file_id: str):
    """캐비닛 파일 삭제 — DB + Storage 동시"""
    try:
        # 1) 파일 정보 조회
        result = supabase.table("cabinet_files").select("storage_path").eq("id", file_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        storage_path = result.data[0].get("storage_path")

        # 2) Storage 삭제
        if storage_path:
            try:
                supabase.storage.from_(BUCKET).remove([storage_path])
            except Exception:
                pass  # Storage 삭제 실패해도 DB는 정리

        # 3) DB 삭제
        supabase.table("cabinet_files").delete().eq("id", file_id).execute()
        return ApiResponse(success=True, message="삭제 완료")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
