from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


# ─── Customer Relations (가족 정보) ─────────────────────
class CustomerRelationBase(BaseModel):
    """가족 1명 단위 — 본인/배우자/자녀 등"""
    relation_type: str  # 'self','spouse','child1'~'child4','custom'
    relation_label: Optional[str] = None  # 사용자 정의 라벨
    name: Optional[str] = None
    ssn: Optional[str] = None
    birth_date: Optional[date] = None
    lunar_solar: Optional[str] = None  # '양' / '음'
    gender: Optional[str] = None       # '남' / '여'
    job: Optional[str] = None
    phone: Optional[str] = None
    sort_order: Optional[int] = 0


class CustomerRelationCreate(CustomerRelationBase):
    customer_id: str


class CustomerRelationUpdate(BaseModel):
    relation_type: Optional[str] = None
    relation_label: Optional[str] = None
    name: Optional[str] = None
    ssn: Optional[str] = None
    birth_date: Optional[date] = None
    lunar_solar: Optional[str] = None
    gender: Optional[str] = None
    job: Optional[str] = None
    phone: Optional[str] = None
    sort_order: Optional[int] = None


class CustomerRelationResponse(CustomerRelationBase):
    id: str
    customer_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─── Customers — 50+ 필드 (내고객다보여 25 풀필드) ─────────────────────
class CustomerBase(BaseModel):
    """고객 기본/확장 필드 (가족은 별도 relations로 nested)"""
    # 기본
    name: str
    phone: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None
    birth_date: Optional[date] = None
    memo: Optional[str] = None

    # 헤더
    family_head: Optional[str] = None
    family_head_phone: Optional[str] = None
    first_meeting_date: Optional[date] = None

    # 결혼/배경
    marital_status: Optional[str] = None
    marriage_date: Optional[date] = None
    spouse_hometown: Optional[str] = None
    hometown: Optional[str] = None

    # 주소(집)
    home_postcode: Optional[str] = None
    home_address: Optional[str] = None
    home_phone: Optional[str] = None
    fax: Optional[str] = None
    mobile: Optional[str] = None

    # 회사
    company_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    company_postcode: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None

    # 이메일
    email_local: Optional[str] = None
    email_domain: Optional[str] = None

    # 신상
    introducer: Optional[str] = None
    introducer_relation: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    hobby: Optional[str] = None
    religion: Optional[str] = None
    blood_type: Optional[str] = None
    final_school: Optional[str] = None
    job_title: Optional[str] = None
    car_brand: Optional[str] = None
    second_car: Optional[str] = None

    # 특이사항
    special_note_1: Optional[str] = None
    special_note_2: Optional[str] = None

    # 보조정보 — 분류/등급
    customer_grade: Optional[str] = None
    group_category: Optional[str] = None
    todo_list: Optional[str] = None
    birthday_management: Optional[str] = None
    dm_type: Optional[str] = None

    # 보조정보 — 통신/외부
    telecom_carrier: Optional[str] = None
    korfd_grade: Optional[str] = None
    haru_family_grade: Optional[str] = None
    agent_grade: Optional[str] = None
    company_homepage: Optional[str] = None

    # 보조정보 — 이벤트/관리
    gift_member_type: Optional[str] = None
    cancer_diagnosis_amount: Optional[int] = None
    newsletter_target: Optional[str] = None
    expected_birth_date: Optional[date] = None
    gift_send_group: Optional[str] = None

    # 명절/달력 (JSONB)
    seasonal_data: Optional[Dict[str, Any]] = None

    # 금융
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    monthly_message_group: Optional[str] = None

    # 메신저
    kkakto_group: Optional[str] = None
    kkakto_nickname: Optional[str] = None
    kkakto_name: Optional[str] = None

    # 사용자 정의 (JSONB)
    custom_data: Optional[Dict[str, Any]] = None


class CustomerCreate(CustomerBase):
    """고객 생성 — 가족 nested 입력 가능"""
    relations: Optional[List[CustomerRelationBase]] = None


class CustomerUpdate(BaseModel):
    """고객 수정 — 모든 필드 옵션. relations는 별도 endpoint"""
    name: Optional[str] = None
    phone: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None
    birth_date: Optional[date] = None
    memo: Optional[str] = None

    # 헤더
    family_head: Optional[str] = None
    family_head_phone: Optional[str] = None
    first_meeting_date: Optional[date] = None

    # 결혼/배경
    marital_status: Optional[str] = None
    marriage_date: Optional[date] = None
    spouse_hometown: Optional[str] = None
    hometown: Optional[str] = None

    # 주소(집)
    home_postcode: Optional[str] = None
    home_address: Optional[str] = None
    home_phone: Optional[str] = None
    fax: Optional[str] = None
    mobile: Optional[str] = None

    # 회사
    company_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    company_postcode: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None

    # 이메일
    email_local: Optional[str] = None
    email_domain: Optional[str] = None

    # 신상
    introducer: Optional[str] = None
    introducer_relation: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    hobby: Optional[str] = None
    religion: Optional[str] = None
    blood_type: Optional[str] = None
    final_school: Optional[str] = None
    job_title: Optional[str] = None
    car_brand: Optional[str] = None
    second_car: Optional[str] = None

    # 특이사항
    special_note_1: Optional[str] = None
    special_note_2: Optional[str] = None

    # 보조정보 — 분류/등급
    customer_grade: Optional[str] = None
    group_category: Optional[str] = None
    todo_list: Optional[str] = None
    birthday_management: Optional[str] = None
    dm_type: Optional[str] = None

    # 보조정보 — 통신/외부
    telecom_carrier: Optional[str] = None
    korfd_grade: Optional[str] = None
    haru_family_grade: Optional[str] = None
    agent_grade: Optional[str] = None
    company_homepage: Optional[str] = None

    # 보조정보 — 이벤트/관리
    gift_member_type: Optional[str] = None
    cancer_diagnosis_amount: Optional[int] = None
    newsletter_target: Optional[str] = None
    expected_birth_date: Optional[date] = None
    gift_send_group: Optional[str] = None

    # JSONB
    seasonal_data: Optional[Dict[str, Any]] = None
    custom_data: Optional[Dict[str, Any]] = None

    # 금융
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    monthly_message_group: Optional[str] = None

    # 메신저
    kkakto_group: Optional[str] = None
    kkakto_nickname: Optional[str] = None
    kkakto_name: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: str
    agent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    relations: Optional[List[CustomerRelationResponse]] = None


# ─── Activities ──────────────────────────────
class ActivityCreate(BaseModel):
    customer_id: str
    activity_date: date
    activity_type: Optional[str] = "call"
    content: Optional[str] = None
    next_step: Optional[str] = None
    manager_name: Optional[str] = None

class ActivityUpdate(BaseModel):
    activity_date: Optional[date] = None
    activity_type: Optional[str] = None
    content: Optional[str] = None
    next_step: Optional[str] = None
    manager_name: Optional[str] = None

class ActivityResponse(BaseModel):
    id: str
    customer_id: str
    activity_date: date
    activity_type: Optional[str]
    content: Optional[str]
    next_step: Optional[str]
    manager_name: Optional[str]
    agent_id: Optional[str]
    created_at: Optional[datetime]


# ─── Common Codes ─────────────────────────────
class CodeCreate(BaseModel):
    group_name: str
    item_name: str
    item_value: str
    sort_order: Optional[int] = 0

class CodeResponse(BaseModel):
    id: int
    group_name: str
    item_name: str
    item_value: str
    sort_order: int
    is_active: bool


# ─── Cabinet Files (캐비닛 시스템 v3) ─────────────────────
class CabinetFileBase(BaseModel):
    category_key: str                       # 12 기본 키 또는 'custom'
    category_label: Optional[str] = None
    memo: Optional[str] = None
    tags: Optional[List[str]] = None


class CabinetFileUpdate(BaseModel):
    category_key: Optional[str] = None
    category_label: Optional[str] = None
    memo: Optional[str] = None
    tags: Optional[List[str]] = None


class CabinetFileResponse(CabinetFileBase):
    id: str
    customer_id: str
    filename: str
    original_name: Optional[str] = None
    storage_path: str
    storage_bucket: Optional[str] = None
    size_bytes: Optional[int] = 0
    mime_type: Optional[str] = None
    url: Optional[str] = None  # 동적 생성 (public URL)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─── API 공통 응답 형식 ─────────────────────
class ApiResponse(BaseModel):
    success: bool
    data: Optional[object] = None
    message: str = ""
