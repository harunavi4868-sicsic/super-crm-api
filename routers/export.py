from fastapi import APIRouter, HTTPException, Response, Query
from typing import Optional
from services.supabase_client import supabase
import pandas as pd
import io

router = APIRouter(prefix="/api/v1/export", tags=["export"])

# 고객 컬럼 한글 매핑
CUSTOMER_COL_LABELS = {
    "name": "이름", "phone": "연락처", "category": "고객구분",
    "status": "관리상태", "address": "주소", "birth_date": "생년월일",
    "first_meet_date": "첫만남일", "created_at": "등록일",
}
CUSTOMER_DROP = {"id", "agent_id", "updated_at"}


def _to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


@router.get("/customers")
def export_customers(
    status: Optional[str] = Query(None, description="관리상태 필터"),
    category: Optional[str] = Query(None, description="고객구분 필터"),
):
    """고객 목록 → Excel 다운로드 (.xlsx)"""
    try:
        q = supabase.table("customers").select("*")
        if status:
            q = q.eq("status", status)
        if category:
            q = q.eq("category", category)
        data = q.order("name").execute().data or []
        if not data:
            raise HTTPException(status_code=404, detail="내보낼 데이터가 없습니다.")

        df = pd.DataFrame(data)
        df = df.drop(columns=[c for c in CUSTOMER_DROP if c in df.columns])
        df = df.rename(columns={k: v for k, v in CUSTOMER_COL_LABELS.items() if k in df.columns})

        # 카테고리/상태 한글 변환
        cat_map = {"vip": "VIP", "existing": "기존", "new": "신규", "dormant": "휴면"}
        sts_map = {"active": "진행중", "hold": "보류", "completed": "완료", "cancelled": "해지"}
        if "고객구분" in df.columns:
            df["고객구분"] = df["고객구분"].map(cat_map).fillna(df["고객구분"])
        if "관리상태" in df.columns:
            df["관리상태"] = df["관리상태"].map(sts_map).fillna(df["관리상태"])

        return Response(
            content=_to_excel_bytes(df, "고객목록"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''customers.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts")
def export_contracts():
    """계약 전체 목록 → Excel 다운로드 (.xlsx)"""
    try:
        data = supabase.table("contracts").select(
            "*, customers(name, phone)"
        ).execute().data or []
        if not data:
            raise HTTPException(status_code=404, detail="내보낼 데이터가 없습니다.")

        rows = []
        for r in data:
            row = {k: v for k, v in r.items() if k not in ("customers", "id", "customer_id")}
            cust = r.get("customers") or {}
            row["고객명"] = cust.get("name", "")
            row["고객연락처"] = cust.get("phone", "")
            rows.append(row)

        df = pd.DataFrame(rows)
        col_order = ["고객명", "고객연락처"] + [c for c in df.columns if c not in ("고객명", "고객연락처")]
        df = df[col_order]

        return Response(
            content=_to_excel_bytes(df, "계약목록"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''contracts.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities")
def export_activities():
    """활동 전체 목록 → Excel 다운로드 (.xlsx)"""
    try:
        data = supabase.table("activities").select(
            "*, customers(name)"
        ).execute().data or []
        if not data:
            raise HTTPException(status_code=404, detail="내보낼 데이터가 없습니다.")

        type_map = {
            "call": "전화", "visit": "미팅", "message": "문자",
            "contract": "계약", "renewal": "갱신",
        }
        rows = []
        for r in data:
            row = {k: v for k, v in r.items() if k not in ("customers", "id", "customer_id", "agent_id")}
            row["고객명"] = (r.get("customers") or {}).get("name", "")
            if "activity_type" in row:
                row["activity_type"] = type_map.get(row["activity_type"], row["activity_type"])
            rows.append(row)

        df = pd.DataFrame(rows)
        col_order = ["고객명"] + [c for c in df.columns if c != "고객명"]
        df = df[col_order]
        df = df.rename(columns={
            "activity_date": "활동일자", "activity_type": "활동유형",
            "content": "상담내용", "next_step": "향후계획",
            "manager_name": "담당자", "created_at": "등록일",
        })

        return Response(
            content=_to_excel_bytes(df, "활동기록"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''activities.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
