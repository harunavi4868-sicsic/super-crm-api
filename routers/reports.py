from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, date
from models.schemas import ApiResponse
from services.supabase_client import supabase
from services.auth import get_current_user, scope_by_agent

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/dashboard")
def get_dashboard_all(user: dict = Depends(get_current_user)):
    """대시보드 통합 엔드포인트 — 일반 유저는 본인 데이터만, 관리자는 전체."""
    try:
        from dateutil.relativedelta import relativedelta

        now = datetime.now()
        today = now.date()
        this_month_prefix = now.strftime("%Y-%m")

        # ── customers 풀스캔 1회 (agent_id 스코프)
        q = supabase.table("customers").select("id, status, category, created_at, birth_date")
        q = scope_by_agent(q, user)
        customers = q.execute().data or []

        # ── contracts 풀스캔 1회 (agent_id 스코프)
        q = supabase.table("contracts").select("status, monthly_premium, contract_date")
        q = scope_by_agent(q, user)
        contracts = q.execute().data or []

        # ── activities 풀스캔 1회 (agent_id 스코프)
        q = supabase.table("activities").select("activity_type, created_at")
        q = scope_by_agent(q, user)
        all_activities = q.execute().data or []
        this_month_activities = sum(
            1 for a in all_activities
            if (a.get("created_at") or "").startswith(this_month_prefix)
        )

        # ── 최근 활동 5건 (대시보드 테이블용)
        q = supabase.table("activities").select("*, customers(name, phone)")
        q = scope_by_agent(q, user)
        recent = q.order("activity_date", desc=True).limit(5).execute().data or []
        # 프론트에서 customer_name으로 쓰던 필드 호환
        for a in recent:
            cust = a.get("customers") or {}
            a["customer_name"] = cust.get("name") or "—"

        # ── stats
        total_customers = len(customers)
        this_month_new = sum(1 for c in customers if (c.get("created_at") or "").startswith(this_month_prefix))
        total_contracts = len(contracts)
        active_contracts = sum(1 for c in contracts if c.get("status") == "active")
        total_premium = sum(float(c.get("monthly_premium") or 0) for c in contracts if c.get("status") == "active")

        # ── 고객 상태별 카운트 (active/hold/completed/cancelled)
        status_counts = {"active": 0, "hold": 0, "completed": 0, "cancelled": 0}
        for c in customers:
            s = c.get("status") or ""
            if s in status_counts:
                status_counts[s] += 1

        # ── 활동 유형별 카운트
        ACTIVITY_TYPE_META = {
            "call":     {"label": "전화", "color": "#2563EB"},
            "visit":    {"label": "방문", "color": "#16A34A"},
            "message":  {"label": "문자", "color": "#94A3B8"},
            "contract": {"label": "계약", "color": "#7C3AED"},
            "renewal":  {"label": "갱신", "color": "#D97706"},
        }
        atype_count = {k: 0 for k in ACTIVITY_TYPE_META}
        for a in all_activities:
            t = a.get("activity_type") or ""
            if t in atype_count:
                atype_count[t] += 1
        activity_types = [
            {"type": k, "label": meta["label"], "count": atype_count[k], "color": meta["color"]}
            for k, meta in ACTIVITY_TYPE_META.items()
        ]

        # ── 월별 신규 (최근 6개월)
        months = []
        for i in range(5, -1, -1):
            dt = now - relativedelta(months=i)
            months.append({"key": dt.strftime("%Y-%m"), "label": f"{dt.month}월"})
        count_map = {m["key"]: 0 for m in months}
        for c in customers:
            prefix = (c.get("created_at") or "")[:7]
            if prefix in count_map:
                count_map[prefix] += 1
        monthly = [{"month": m["key"], "label": m["label"], "count": count_map[m["key"]]} for m in months]

        # ── 카테고리 분포 (7종)
        CATEGORY_META = {
            "visit":   {"name": "방문",   "color": "#0EA5E9"},
            "signup":  {"name": "가입",   "color": "#6366F1"},
            "deal":    {"name": "거래",   "color": "#10B981"},
            "invest":  {"name": "투자",   "color": "#2563EB"},
            "vip":     {"name": "VIP",    "color": "#F59E0B"},
            "agency":  {"name": "대리점", "color": "#E11D48"},
            "dormant": {"name": "휴면",   "color": "#94A3B8"},
        }
        cat_count = {k: 0 for k in CATEGORY_META}
        for c in customers:
            cat = c.get("category") or ""
            if cat in cat_count:
                cat_count[cat] += 1
        category_dist = [
            {"name": meta["name"], "value": cat_count[k], "color": meta["color"]}
            for k, meta in CATEGORY_META.items()
        ]

        # ── 알림 요약 (이번달 생일 / 90일내 갱신)
        birthday_count = sum(
            1 for c in customers
            if c.get("status") == "active" and c.get("birth_date")
            and len(c["birth_date"]) >= 7 and int(c["birth_date"][5:7]) == today.month
        )
        renewal_count = 0
        for c in contracts:
            if c.get("status") != "active" or not c.get("contract_date"):
                continue
            try:
                cd = date.fromisoformat(c["contract_date"])
                nr = cd.replace(year=today.year)
                if nr < today:
                    nr = nr.replace(year=today.year + 1)
                if 0 <= (nr - today).days <= 90:
                    renewal_count += 1
            except Exception:
                continue

        return ApiResponse(
            success=True,
            data={
                "stats": {
                    "total_customers": total_customers,
                    "this_month_new": this_month_new,
                    "this_month_activities": this_month_activities,
                    "total_contracts": total_contracts,
                    "active_contracts": active_contracts,
                    "total_premium": total_premium,
                    **status_counts,
                },
                "monthly_new": monthly,
                "category_dist": category_dist,
                "activity_types": activity_types,
                "alerts": {
                    "birthday_this_month": birthday_count,
                    "renewal_90days": renewal_count,
                },
                "recent_activities": recent,
            },
            message="대시보드 통합 조회 완료",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_stats():
    """대시보드 통계 - 고객/계약/활동 종합 현황"""
    try:
        # 전체 고객 목록 조회
        customers_result = supabase.table("customers").select("status, category, created_at").execute()
        customers = customers_result.data or []

        total_customers = len(customers)

        # status별 카운트
        status_counts = {"active": 0, "hold": 0, "completed": 0, "cancelled": 0}
        for c in customers:
            s = c.get("status", "")
            if s in status_counts:
                status_counts[s] += 1

        # category별 카운트
        category_counts = {"vip": 0, "existing": 0, "new": 0, "dormant": 0}
        for c in customers:
            cat = c.get("category", "")
            if cat in category_counts:
                category_counts[cat] += 1

        # 이번달 신규 고객수
        now = datetime.now()
        this_month_prefix = now.strftime("%Y-%m")
        this_month_new = sum(
            1 for c in customers
            if (c.get("created_at") or "").startswith(this_month_prefix)
        )

        # 계약 정보 조회
        contracts_result = supabase.table("contracts").select("status, monthly_premium").execute()
        contracts = contracts_result.data or []

        total_contracts = len(contracts)
        active_contracts = sum(1 for c in contracts if c.get("status") == "active")
        total_premium = sum(
            float(c.get("monthly_premium") or 0)
            for c in contracts
            if c.get("status") == "active"
        )

        # 이번달 활동 건수
        activities_result = (
            supabase.table("activities")
            .select("id, created_at")
            .gte("created_at", f"{this_month_prefix}-01")
            .execute()
        )
        this_month_activities = len(activities_result.data or [])

        return ApiResponse(
            success=True,
            data={
                "total_customers": total_customers,
                "active": status_counts["active"],
                "hold": status_counts["hold"],
                "completed": status_counts["completed"],
                "cancelled": status_counts["cancelled"],
                "vip": category_counts["vip"],
                "existing": category_counts["existing"],
                "new_cat": category_counts["new"],
                "dormant": category_counts["dormant"],
                "total_contracts": total_contracts,
                "active_contracts": active_contracts,
                "total_premium": total_premium,
                "this_month_activities": this_month_activities,
                "this_month_new": this_month_new,
            },
            message="통계 조회 완료",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monthly-new")
def get_monthly_new():
    """최근 6개월 월별 신규 고객 수"""
    try:
        from dateutil.relativedelta import relativedelta

        now = datetime.now()
        months = []
        for i in range(5, -1, -1):
            dt = now - relativedelta(months=i)
            months.append({
                "year": dt.year,
                "month": dt.month,
                "key": dt.strftime("%Y-%m"),
                "label": f"{dt.month}월",
            })

        start_date = f"{months[0]['key']}-01"
        result = (
            supabase.table("customers")
            .select("created_at")
            .gte("created_at", start_date)
            .execute()
        )
        customers = result.data or []

        count_map = {m["key"]: 0 for m in months}
        for c in customers:
            created = c.get("created_at") or ""
            prefix = created[:7]  # "YYYY-MM"
            if prefix in count_map:
                count_map[prefix] += 1

        data = [
            {"month": m["key"], "label": m["label"], "count": count_map[m["key"]]}
            for m in months
        ]

        return ApiResponse(success=True, data=data, message="월별 신규 고객 조회 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity-types")
def get_activity_types():
    """활동 유형별 카운트"""
    try:
        TYPE_META = {
            "call":     {"label": "전화",   "color": "#2563EB"},
            "visit":    {"label": "방문",   "color": "#16A34A"},
            "message":  {"label": "문자",   "color": "#94A3B8"},
            "contract": {"label": "계약",   "color": "#7C3AED"},
            "renewal":  {"label": "갱신",   "color": "#D97706"},
        }

        result = supabase.table("activities").select("activity_type").execute()
        activities = result.data or []

        count_map = {t: 0 for t in TYPE_META}
        for a in activities:
            t = a.get("activity_type", "")
            if t in count_map:
                count_map[t] += 1

        data = [
            {
                "type": t,
                "label": meta["label"],
                "count": count_map[t],
                "color": meta["color"],
            }
            for t, meta in TYPE_META.items()
        ]

        return ApiResponse(success=True, data=data, message="활동 유형별 통계 조회 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category-dist")
def get_category_dist():
    """고객 구분별 분포"""
    try:
        CATEGORY_META = {
            "visit":   {"name": "방문",   "color": "#0EA5E9"},
            "signup":  {"name": "가입",   "color": "#6366F1"},
            "deal":    {"name": "거래",   "color": "#10B981"},
            "invest":  {"name": "투자",   "color": "#2563EB"},
            "vip":     {"name": "VIP",    "color": "#F59E0B"},
            "agency":  {"name": "대리점", "color": "#E11D48"},
            "dormant": {"name": "휴면",   "color": "#94A3B8"},
        }

        result = supabase.table("customers").select("category").execute()
        customers = result.data or []

        count_map = {cat: 0 for cat in CATEGORY_META}
        for c in customers:
            cat = c.get("category", "")
            if cat in count_map:
                count_map[cat] += 1

        data = [
            {
                "name": meta["name"],
                "value": count_map[cat],
                "color": meta["color"],
            }
            for cat, meta in CATEGORY_META.items()
        ]

        return ApiResponse(success=True, data=data, message="고객 구분 분포 조회 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
