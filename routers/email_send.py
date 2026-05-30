"""
email_send.py — Resend API 기반 이메일 발송
환경변수: RESEND_API_KEY, EMAIL_FROM (발신 주소)

pip install resend 후 사용 가능
"""
import os
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from pydantic import BaseModel
from services.supabase_client import supabase
from models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/email", tags=["email"])

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM     = os.getenv("EMAIL_FROM", "noreply@crm.haru.tips")


def _send_via_resend(to: List[str], subject: str, html: str) -> dict:
    """Resend API HTTP 직접 호출 (SDK 없이 httpx 사용)"""
    import httpx
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY 환경변수가 설정되지 않았습니다.")
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": EMAIL_FROM, "to": to, "subject": subject, "html": html},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Resend 오류 {resp.status_code}: {resp.text}")
    return resp.json()


# ── 템플릿 ──────────────────────────────────────────────

def _birthday_html(customer_name: str, birth_date: str) -> str:
    return f"""
<div style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:12px">
  <h2 style="color:#1E293B">🎂 생일 알림</h2>
  <p style="color:#475569"><b>{customer_name}</b> 고객의 생일이 다가왔습니다.</p>
  <p style="color:#64748B">생년월일: {birth_date}</p>
  <p style="color:#94A3B8;font-size:12px;margin-top:24px">SUPER CRM 자동 알림</p>
</div>"""


def _renewal_html(customer_name: str, product_name: str, renewal_date: str, days_left: int) -> str:
    return f"""
<div style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:12px">
  <h2 style="color:#1E293B">📄 계약 갱신 알림</h2>
  <p style="color:#475569"><b>{customer_name}</b> 고객의 계약 갱신일이 <b>D-{days_left}</b>입니다.</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0">
    <tr><td style="color:#64748B;padding:6px 0">상품명</td><td style="font-weight:600">{product_name}</td></tr>
    <tr><td style="color:#64748B;padding:6px 0">갱신일</td><td style="font-weight:600">{renewal_date}</td></tr>
  </table>
  <p style="color:#94A3B8;font-size:12px;margin-top:24px">SUPER CRM 자동 알림</p>
</div>"""


def _custom_html(subject: str, body_text: str) -> str:
    return f"""
<div style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:12px">
  <h2 style="color:#1E293B">{subject}</h2>
  <p style="color:#475569;white-space:pre-line">{body_text}</p>
  <p style="color:#94A3B8;font-size:12px;margin-top:24px">SUPER CRM</p>
</div>"""


# ── 요청 스키마 ─────────────────────────────────────────

class BirthdayEmailBody(BaseModel):
    customer_id: str
    to_email: str


class RenewalEmailBody(BaseModel):
    contract_id: str
    to_email: str


class CustomEmailBody(BaseModel):
    to_emails: List[str]
    subject: str
    body_text: str


# ── 엔드포인트 ──────────────────────────────────────────

@router.post("/birthday")
def send_birthday_email(body: BirthdayEmailBody):
    """생일 알림 이메일 발송"""
    try:
        cust = supabase.table("customers").select("name, birth_date").eq("id", body.customer_id).single().execute()
        if not cust.data:
            raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
        name = cust.data["name"]
        bd   = cust.data.get("birth_date", "")
        html = _birthday_html(name, bd)
        _send_via_resend([body.to_email], f"🎂 [{name}] 고객 생일 알림", html)
        return ApiResponse(success=True, message=f"{body.to_email}로 생일 알림 발송 완료")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/renewal")
def send_renewal_email(body: RenewalEmailBody):
    """계약 갱신 알림 이메일 발송"""
    try:
        cont = supabase.table("contracts").select(
            "product_name, insurance_expiry, payment_expiry, contract_date, customers(name)"
        ).eq("id", body.contract_id).single().execute()
        if not cont.data:
            raise HTTPException(status_code=404, detail="계약을 찾을 수 없습니다.")
        d = cont.data
        name    = (d.get("customers") or {}).get("name", "")
        product = d.get("product_name", "")
        expiry  = d.get("insurance_expiry") or d.get("payment_expiry") or d.get("contract_date", "")
        from datetime import date
        days_left = (date.fromisoformat(expiry) - date.today()).days if expiry else 0
        html = _renewal_html(name, product, expiry, max(days_left, 0))
        _send_via_resend([body.to_email], f"📄 [{name}] 계약 갱신 알림 D-{max(days_left,0)}", html)
        return ApiResponse(success=True, message=f"{body.to_email}로 갱신 알림 발송 완료")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom")
def send_custom_email(body: CustomEmailBody):
    """커스텀 이메일 발송 (공지/안내 등)"""
    try:
        if not body.to_emails:
            raise HTTPException(status_code=400, detail="수신자 이메일이 없습니다.")
        html = _custom_html(body.subject, body.body_text)
        _send_via_resend(body.to_emails, body.subject, html)
        return ApiResponse(success=True, message=f"{len(body.to_emails)}명에게 발송 완료")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
