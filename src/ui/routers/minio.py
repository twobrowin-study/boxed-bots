import base64

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from fastapi.responses import (
    JSONResponse,
    Response,
    StreamingResponse,
)

from src.ui.app import provider
from src.ui.dependencies import RequireRoles
from src.ui.keycloak import KEYCLOAK_ROLE

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/minio/base64/{bucket}/{filename}", tags=["minio"])
async def get_minio_b64(bucket: str, filename: str) -> Response:
    """Прокси к minio, который возвращает ответ в формате base64"""
    bio, content_type = await provider.minio.download(bucket, filename)
    if not bio:
        raise HTTPException(500, f"{provider.config.i18n.error_minio_no_bio} {bucket}/{filename}")
    bio.seek(0)
    return JSONResponse(
        content={
            "image": base64.b64encode(bio.getvalue()).decode(),
            "mime": content_type,
        }
    )


@router.get("/minio/{bucket}/{filename}", tags=["minio"])
async def get_minio_stream(bucket: str, filename: str) -> Response:
    """Прокси к minio, который возвращает файл"""
    bio, _ = await provider.minio.download(bucket, filename)
    if not bio:
        raise HTTPException(500, f"{provider.config.i18n.error_minio_no_bio} {bucket}/{filename}")
    bio.seek(0)
    return StreamingResponse(bio)
