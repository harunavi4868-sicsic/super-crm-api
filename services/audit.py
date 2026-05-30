"""
audit.py — 수정/삭제 감사 로그 헬퍼
감사 로그 실패가 메인 비즈니스 로직에 영향을 주지 않도록 예외를 삼킵니다.

DB: audit_logs 테이블 필요 (super_crm_v3_audit.sql 참조)
"""
from typing import Any, Optional
from services.supabase_client import supabase


def log_audit(
    table_name: str,
    record_id: str,
    action: str,            # "UPDATE" | "DELETE" | "INSERT"
    before_data: Optional[Any] = None,
    after_data: Optional[Any] = None,
    changed_by: Optional[str] = None,
) -> None:
    """
    수정/삭제 이력을 audit_logs 테이블에 기록합니다.

    Args:
        table_name: 변경된 테이블명 (예: "customers", "contracts")
        record_id:  변경된 레코드 UUID
        action:     "UPDATE" | "DELETE" | "INSERT"
        before_data: 변경 전 데이터 (dict) — UPDATE/DELETE 시
        after_data:  변경 후 데이터 (dict) — INSERT/UPDATE 시
        changed_by:  변경자 user_id (UUID)
    """
    try:
        supabase.table("audit_logs").insert({
            "table_name": table_name,
            "record_id": record_id,
            "action": action,
            "before_data": before_data,
            "after_data": after_data,
            "changed_by": changed_by,
        }).execute()
    except Exception:
        pass  # 감사 로그 실패가 메인 로직을 막으면 안 됨
