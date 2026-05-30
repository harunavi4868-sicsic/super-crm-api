"""
medical_notes — 의료/상담 기록 (보무기록)
PDF 10번 p9 (보무기록창) + p11 (의료정보 기록창) 통합

⚠️ 중요: 기존 medical_records 테이블이 아닌 신규 medical_notes 테이블 사용
(SUPER_CRM v2 마이그레이션에서 신규 생성됨)
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from datetime import date
from pydantic import BaseModel
from services.supabase_client import supabase
from services.auth import get_current_user, scope_by_agent
from models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/medical", tags=["medical"])


class MedicalNoteCreate(BaseModel):
    customer_id: str
    patient_name: str
    patient_ssn: Optional[str] = None
    family_head: Optional[str] = None
    accident_date: Optional[date] = None       # 사고(발병)일
    treatment_date: Optional[date] = None      # 진료일
    disease_name: Optional[str] = None         # 병명
    treatment_name: Optional[str] = None       # 진토(수술)명
    ward_type: Optional[str] = None            # '입원' / '통원'
    disease_code: Optional[str] = None         # 질병코드
    content: Optional[str] = None              # 의료내용
    match_card: Optional[bool] = False         # 일치 체크
    reflect_to_card: Optional[bool] = False    # 고객카드 반영
    reference_date: Optional[date] = None      # 기준일
    # v3.1 — 가족 매칭
    relation_id: Optional[str] = None          # customer_relations.id (FK)
    relation_label: Optional[str] = None       # 캐시: '본인','배우자','자녀1' 등
    relation_type: Optional[str] = None        # 캐시: 'self','spouse','child1'~'child4','custom'


class MedicalNoteUpdate(BaseModel):
    patient_name: Optional[str] = None
    patient_ssn: Optional[str] = None
    family_head: Optional[str] = None
    accident_date: Optional[date] = None
    treatment_date: Optional[date] = None
    disease_name: Optional[str] = None
    treatment_name: Optional[str] = None
    ward_type: Optional[str] = None
    disease_code: Optional[str] = None
    content: Optional[str] = None
    match_card: Optional[bool] = None
    reflect_to_card: Optional[bool] = None
    reference_date: Optional[date] = None
    # v3.1 — 가족 매칭
    relation_id: Optional[str] = None
    relation_label: Optional[str] = None
    relation_type: Optional[str] = None


def _serialize_dates(data: dict) -> dict:
    return {
        k: (v.isoformat() if isinstance(v, date) else v)
        for k, v in data.items()
        if v is not None
    }


@router.get("")
def list_all_medical_notes(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """전체 의료/상담 기록 목록 — 일반 유저는 자기 것만, 관리자는 전체"""
    try:
        offset = (page - 1) * size
        q = supabase.table("medical_notes").select("*, customers(name, phone)")
        q = scope_by_agent(q, user)
        result = q.order("treatment_date", desc=True).range(offset, offset + size - 1).execute()
        return ApiResponse(success=True, data=result.data, message=f"{len(result.data)}건")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}")
def list_medical_notes(
    customer_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    relation_id: Optional[str] = Query(None, description="특정 가족원 필터"),
    relation_type: Optional[str] = Query(None, description="self/spouse/child1~ 필터"),
):
    """고객별 의료/상담 기록 조회 (페이징, 가족 필터 지원)"""
    try:
        offset = (page - 1) * size
        query = supabase.table("medical_notes") \
            .select("*", count="exact") \
            .eq("customer_id", customer_id)

        if relation_id:
            query = query.eq("relation_id", relation_id)
        if relation_type:
            query = query.eq("relation_type", relation_type)

        result = query \
            .order("treatment_date", desc=True) \
            .range(offset, offset + size - 1) \
            .execute()

        return ApiResponse(
            success=True,
            data={
                "items": result.data or [],
                "total": result.count or 0,
                "page": page,
                "size": size,
            },
            message=f"{len(result.data or [])}건"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}/stats")
def medical_stats_by_relation(customer_id: str):
    """가족원별 상담/의료 기록 횟수 통계 (relation_label 기준)"""
    try:
        result = supabase.table("medical_notes") \
            .select("relation_id, relation_label, relation_type, treatment_date") \
            .eq("customer_id", customer_id) \
            .execute()
        rows = result.data or []

        stats: dict = {}
        for r in rows:
            key = r.get("relation_label") or "미지정"
            if key not in stats:
                stats[key] = {
                    "relation_id": r.get("relation_id"),
                    "relation_label": key,
                    "relation_type": r.get("relation_type"),
                    "count": 0,
                    "last_treatment_date": None,
                }
            stats[key]["count"] += 1
            td = r.get("treatment_date")
            if td and (stats[key]["last_treatment_date"] is None or td > stats[key]["last_treatment_date"]):
                stats[key]["last_treatment_date"] = td

        items = sorted(stats.values(), key=lambda x: x["count"], reverse=True)
        return ApiResponse(
            success=True,
            data={"items": items, "total": len(rows)},
            message=f"{len(items)}명 / 총 {len(rows)}건"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}/recent")
def recent_medical_notes(customer_id: str, limit: int = Query(3, ge=1, le=20)):
    """최근 상담 N건 (좌측 카드 위젯용 — 가족 라벨 포함)"""
    try:
        result = supabase.table("medical_notes") \
            .select("id, treatment_date, accident_date, disease_name, treatment_name, ward_type, relation_label, patient_name") \
            .eq("customer_id", customer_id) \
            .order("treatment_date", desc=True) \
            .limit(limit) \
            .execute()
        return ApiResponse(success=True, data=result.data or [], message=f"{len(result.data or [])}건")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{note_id}")
def get_medical_note(note_id: str):
    """의료 기록 단일 조회"""
    try:
        result = supabase.table("medical_notes").select("*").eq("id", note_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="의료 기록을 찾을 수 없습니다.")
        return ApiResponse(success=True, data=result.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_medical_note(body: MedicalNoteCreate, user: dict = Depends(get_current_user)):
    """의료/상담 기록 등록. agent_id 자동 부여."""
    try:
        payload = _serialize_dates(body.model_dump())
        payload["agent_id"] = user["id"]
        result = supabase.table("medical_notes").insert(payload).execute()
        return ApiResponse(
            success=True,
            data=result.data[0] if result.data else {},
            message="의료 기록 등록 완료"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{note_id}")
def update_medical_note(note_id: str, body: MedicalNoteUpdate):
    """의료/상담 기록 수정"""
    try:
        payload = _serialize_dates(body.model_dump())
        if not payload:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다.")
        result = supabase.table("medical_notes").update(payload).eq("id", note_id).execute()
        return ApiResponse(
            success=True,
            data=result.data[0] if result.data else {},
            message="수정 완료"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{note_id}")
def delete_medical_note(note_id: str):
    """의료/상담 기록 삭제"""
    try:
        supabase.table("medical_notes").delete().eq("id", note_id).execute()
        return ApiResponse(success=True, message="삭제 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
