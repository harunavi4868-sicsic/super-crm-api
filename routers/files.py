from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional
import os
from services.supabase_client import supabase
from models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/files", tags=["files"])

BUCKET = "customer-files"
MAX_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = {
    "application/pdf", "image/jpeg", "image/png", "image/gif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/{customer_id}")
def list_files(customer_id: str):
    """고객별 파일 목록"""
    try:
        result = supabase.storage.from_(BUCKET).list(customer_id)
        files = []
        for f in (result or []):
            if f.get("name") == ".emptyFolderPlaceholder":
                continue
            url = supabase.storage.from_(BUCKET).get_public_url(
                f"{customer_id}/{f['name']}"
            )
            files.append({
                "name":       f["name"],
                "size":       f.get("metadata", {}).get("size", 0),
                "type":       f.get("metadata", {}).get("mimetype", ""),
                "created_at": f.get("created_at", ""),
                "url":        url,
                "path":       f"{customer_id}/{f['name']}",
            })
        return ApiResponse(success=True, data=files, message=f"{len(files)}개")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{customer_id}")
async def upload_file(customer_id: str, file: UploadFile = File(...)):
    """파일 업로드"""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400,
            detail="지원하지 않는 파일 형식입니다. (PDF, 이미지, Word, Excel)")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="파일 크기는 10MB 이하만 가능합니다.")

    try:
        # 파일명 중복 방지: 타임스탬프 prefix
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_name = f"{ts}_{file.filename}"
        path = f"{customer_id}/{safe_name}"

        supabase.storage.from_(BUCKET).upload(
            path, contents,
            file_options={"content-type": file.content_type}
        )
        url = supabase.storage.from_(BUCKET).get_public_url(path)

        return ApiResponse(success=True, data={"name": safe_name, "url": url, "path": path},
                           message="업로드 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"업로드 오류: {str(e)}")


@router.delete("/{customer_id}/{filename}")
def delete_file(customer_id: str, filename: str):
    """파일 삭제"""
    try:
        path = f"{customer_id}/{filename}"
        supabase.storage.from_(BUCKET).remove([path])
        return ApiResponse(success=True, message="삭제 완료")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
