from fastapi import Request, Depends
from fastapi.responses import HTMLResponse

from typing import Annotated
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

from loguru import logger

from ui.setup import provider, templates

async def verify_token(token: Annotated[str, Depends(provider.oauth2_scheme)]) -> str:
    """
    Убедиться в корректности токена
    """
    logger.info(f"Received Bearer token with request")
    try:
        provider.keycloak.decode_token(token)
    except Exception as e:
        logger.info(f"Bearer token could not be verified: {e}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=f"Bearer token could not be verified: {e}")
    return token

def template(request: Request, template_name: str, additional_context: dict) -> HTMLResponse:
    """
    Прослойка для стандартизации вывода шиблонов
    """
    return templates.TemplateResponse(
        request=request, name=template_name,
        context = {
            'uri_prefix': provider.config.path_prefix,
            'i18n':       provider.config.i18n,
            'keycloak':   provider.config.keycloak
        } | additional_context
    )