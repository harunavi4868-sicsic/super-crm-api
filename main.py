from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routers import customers, activities, codes, import_excel, admin_mgmt, contracts, medical, alerts, reports, files, relations, cabinet, export, notifications, email_send

app = FastAPI(
    title="SUPER CRM API",
    description="보험설계사 고객 관리 시스템 API",
    version="1.0.0",
)

# CORS — Netlify 프론트 + 로컬 개발 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://crm-insurance.netlify.app",
        "https://super-crm-haru.netlify.app",
        "https://super-crm-app.netlify.app",
        "https://crm.haru.tips",
        "http://localhost:3200",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(relations.router)
app.include_router(activities.router)
app.include_router(codes.router)
app.include_router(import_excel.router)
app.include_router(admin_mgmt.router)
app.include_router(contracts.router)
app.include_router(medical.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(files.router)
app.include_router(cabinet.router)
app.include_router(export.router)
app.include_router(notifications.router)
app.include_router(email_send.router)


@app.get("/")
def root():
    return {"message": "SUPER CRM API 정상 작동 중", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
