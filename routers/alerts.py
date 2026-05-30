from fastapi import APIRouter, HTTPException
from datetime import date, timedelta
from typing import Optional
from services.supabase_client import supabase
from models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("/birthday")
def birthday_alerts():
    """이번 달 + 다음 달 생일 고객"""
    try:
        today = date.today()
        result = supabase.table("customers") \
            .select("id, name, phone, birth_date, category") \
            .eq("status", "active") \
            .not_.is_("birth_date", "null") \
            .execute()

        customers = result.data or []
        this_month, next_month = [], []
        for c in customers:
            bd = c.get("birth_date")
            if not bd:
                continue
            try:
                m = int(bd[5:7])
                d = int(bd[8:10])
                if m == today.month:
                    c["birth_day"] = d
                    this_month.append(c)
                elif m == (today.month % 12) + 1:
                    c["birth_day"] = d
                    next_month.append(c)
            except Exception:
                continue

        this_month.sort(key=lambda x: x.get("birth_day", 0))
        next_month.sort(key=lambda x: x.get("birth_day", 0))

        return ApiResponse(success=True, data={
            "this_month": this_month,
            "next_month": next_month,
            "total": len(this_month) + len(next_month)
        }, message=f"이번 달 {len(this_month)}명, 다음 달 {len(next_month)}명")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anniversary")
def anniversary_alerts():
    """첫만남 기념일 D-30 이내 고객"""
    try:
        today = date.today()
        result = supabase.table("customers") \
            .select("id, name, phone, first_meet_date, category") \
            .eq("status", "active") \
            .not_.is_("first_meet_date", "null") \
            .execute()

        customers = result.data or []
        upcoming = []
        for c in customers:
            fmd = c.get("first_meet_date")
            if not fmd:
                continue
            try:
                m = int(fmd[5:7])
                d = int(fmd[8:10])
                this_year_date = date(today.year, m, d)
                diff = (this_year_date - today).days
                if 0 <= diff <= 30:
                    c["days_left"] = diff
                    c["years"] = today.year - int(fmd[:4])
                    upcoming.append(c)
            except Exception:
                continue

        upcoming.sort(key=lambda x: x.get("days_left", 99))
        return ApiResponse(success=True, data=upcoming, message=f"{len(upcoming)}명")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _parse_period_years(period_str) -> Optional[int]:
    """납입기간/보장기간 문자열 → 연수 (예: "10년" → 10, "종신" → 100)"""
    if not period_str:
        return None
    import re
    s = str(period_str).strip()
    if "종신" in s or "평생" in s:
        return 100
    m = re.search(r"(\d+)\s*년", s)
    if m:
        return int(m.group(1))
    return None


@router.get("/renewal")
def renewal_alerts():
    """계약 만기/갱신 D-90 이내 — 납입기간/만기일 실제 반영"""
    try:
        today = date.today()
        result = supabase.table("contracts") \
            .select("*, customers(id, name, phone)") \
            .eq("status", "active") \
            .execute()

        contracts = result.data or []
        upcoming = []
        for c in contracts:
            expiry_date = None

            # 1순위: insurance_expiry (보험 만기일 직접 입력된 경우)
            if c.get("insurance_expiry"):
                try:
                    expiry_date = date.fromisoformat(c["insurance_expiry"])
                except Exception:
                    pass

            # 2순위: payment_expiry (납입 만기일 직접 입력된 경우)
            if not expiry_date and c.get("payment_expiry"):
                try:
                    expiry_date = date.fromisoformat(c["payment_expiry"])
                except Exception:
                    pass

            # 3순위: contract_date + payment_period_year (납입기간 연수 계산)
            if not expiry_date and c.get("contract_date") and c.get("payment_period_year"):
                try:
                    cd = date.fromisoformat(c["contract_date"])
                    years = int(c["payment_period_year"])
                    expiry_date = cd.replace(year=cd.year + years)
                except Exception:
                    pass

            # 4순위: contract_date + payment_period 문자열 파싱 (예: "10년")
            if not expiry_date and c.get("contract_date") and c.get("payment_period"):
                years = _parse_period_years(c["payment_period"])
                if years:
                    try:
                        cd = date.fromisoformat(c["contract_date"])
                        expiry_date = cd.replace(year=cd.year + years)
                    except Exception:
                        pass

            # 5순위 폴백: contract_date 기준 연간 갱신 (기존 로직)
            if not expiry_date and c.get("contract_date"):
                try:
                    cd = date.fromisoformat(c["contract_date"])
                    next_renewal = cd.replace(year=today.year)
                    if next_renewal < today:
                        next_renewal = next_renewal.replace(year=today.year + 1)
                    expiry_date = next_renewal
                except Exception:
                    continue

            if not expiry_date:
                continue

            diff = (expiry_date - today).days
            if 0 <= diff <= 90:
                c["days_left"] = diff
                c["renewal_date"] = str(expiry_date)
                upcoming.append(c)

        upcoming.sort(key=lambda x: x.get("days_left", 999))
        return ApiResponse(success=True, data=upcoming, message=f"{len(upcoming)}건")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policy-anniversary")
def policy_anniversary():
    """상령일 명단 — 30일 이내 계약 상령일 도래"""
    try:
        today = date.today()
        result = supabase.table("contracts") \
            .select("*, customers(id, name, phone, category)") \
            .eq("status", "active") \
            .not_.is_("contract_date", "null") \
            .execute()

        contracts = result.data or []
        upcoming = []
        for c in contracts:
            cd = c.get("contract_date")
            if not cd:
                continue
            try:
                contract_d = date.fromisoformat(cd)
                this_year_anniv = contract_d.replace(year=today.year)
                if this_year_anniv < today:
                    this_year_anniv = this_year_anniv.replace(year=today.year + 1)
                diff = (this_year_anniv - today).days
                if 0 <= diff <= 30:
                    c["days_left"] = diff
                    c["anniversary_date"] = str(this_year_anniv)
                    c["contract_years"] = this_year_anniv.year - contract_d.year
                    upcoming.append(c)
            except Exception:
                continue

        upcoming.sort(key=lambda x: x.get("days_left", 999))
        return ApiResponse(success=True, data=upcoming, message=f"{len(upcoming)}건")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/age-groups")
def age_groups():
    """연령대별 고객 명단"""
    try:
        today = date.today()
        result = supabase.table("customers") \
            .select("id, name, phone, birth_date, category") \
            .eq("status", "active") \
            .execute()

        customers = result.data or []
        groups = {
            "10대": [], "20대": [], "30대": [], "40대": [],
            "50대": [], "60대": [], "70대 이상": [], "미상": [],
        }

        for c in customers:
            bd = c.get("birth_date")
            if not bd:
                groups["미상"].append(c)
                continue
            try:
                age = today.year - int(bd[:4])
                if age < 20:        groups["10대"].append(c)
                elif age < 30:      groups["20대"].append(c)
                elif age < 40:      groups["30대"].append(c)
                elif age < 50:      groups["40대"].append(c)
                elif age < 60:      groups["50대"].append(c)
                elif age < 70:      groups["60대"].append(c)
                else:               groups["70대 이상"].append(c)
            except Exception:
                groups["미상"].append(c)

        data = [
            {"group": k, "count": len(v), "customers": v}
            for k, v in groups.items() if v
        ]
        total = sum(len(v) for v in groups.values())
        return ApiResponse(success=True, data=data, message=f"전체 {total}명")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
def alert_summary():
    """대시보드용 알림 요약"""
    try:
        today = date.today()

        # 이번 달 생일
        customers = supabase.table("customers") \
            .select("birth_date") \
            .eq("status", "active") \
            .not_.is_("birth_date", "null") \
            .execute().data or []
        birthday_count = sum(
            1 for c in customers
            if c.get("birth_date") and int(c["birth_date"][5:7]) == today.month
        )

        # 만기 90일 이내
        contracts = supabase.table("contracts") \
            .select("contract_date") \
            .eq("status", "active") \
            .not_.is_("contract_date", "null") \
            .execute().data or []
        renewal_count = 0
        for c in contracts:
            try:
                cd = date.fromisoformat(c["contract_date"])
                nr = cd.replace(year=today.year)
                if nr < today:
                    nr = nr.replace(year=today.year + 1)
                if 0 <= (nr - today).days <= 90:
                    renewal_count += 1
            except Exception:
                continue

        return ApiResponse(success=True, data={
            "birthday_this_month": birthday_count,
            "renewal_90days": renewal_count,
        }, message="알림 요약")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
