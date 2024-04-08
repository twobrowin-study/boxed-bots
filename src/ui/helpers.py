from enum import Enum
from fastapi import Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse

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
        user = provider.keycloak.decode_token(token)
        if 'preferred_username' in user:
            logger.success(f"Request from user {user['preferred_username']}")
        else:
            logger.warning(f"Request from user without preferred_username!!!")
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

async def get_request_data_or_responce(request: Request, type_str: str) -> tuple[dict[str, dict[str, str|dict[str, str]]], JSONResponse|None]:
    request_data = await request.json()

    bad_responce = JSONResponse({'error': True}, status_code=500)

    if not isinstance(request_data, dict):
        logger.error("Found unknown request type...")
        return {}, bad_responce

    if type_str not in request_data:
        logger.error(f"Type {type_str} not in request...")
        return {}, bad_responce
    
    typed_request_data = request_data[type_str]
    if not isinstance(typed_request_data, dict):
        logger.error(f"Type {type_str} is bad type request...")
        return {}, bad_responce

    return typed_request_data, None

def prepare_attrs_object_from_request(
        request_data: dict[str, dict[str, str|dict[str, str]]],
        status_type: type[Enum],
        numeric_keys: list[str]
    ) -> tuple[dict[str|int, dict[str, str|Enum]], JSONResponse|None]:
    bad_responce = JSONResponse({'error': True}, status_code=500)
    attrs: dict[str|int, dict[str, str|Enum]] = {}
    for idx, plain_obj in request_data.items():
        if idx != 'new' and not idx.isnumeric():
            logger.warning(f"Got bad id {idx=}")
            return {}, bad_responce

        if idx.isnumeric():
            idx = int(idx)
        
        obj: dict[str, str|Enum] = {}
        for key, value in plain_obj.items():
            if key in numeric_keys:
                try:
                    obj[key] = int(value)
                except Exception:
                    logger.warning(f"Got value error as {key=} should be numeric but gor {value=}")
                    return {}, bad_responce
            elif isinstance(value, str):
                obj[key] = value
            elif isinstance(value, dict):
                obj[key] = status_type(**value)
            else:
                logger.warning(f"Got bad key value pair {key=} {value=}")
                return {}, bad_responce

        attrs[idx] = obj
    return attrs, None