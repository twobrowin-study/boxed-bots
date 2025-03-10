from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)
from loguru import logger
from sqlalchemy import select

from src.ui.app import provider
from src.ui.dependencies import RequireRoles, get_user
from src.ui.helpers import (
    get_request_data_or_responce,
    prepare_attrs_object_from_request,
    template,
    try_to_save_attrs,
)
from src.ui.keycloak import KEYCLOAK_ROLE, KeycloakUser
from src.utils.custom_types import PromocodeStatusEnum
from src.utils.db_model import Promocode

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/promocodes", tags=["promocodes"])
async def get_promocodes(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """
    Показывает настроенные промокоды
    """
    async with provider.db_sessionmaker() as session:
        promocodes = list(await session.scalars(select(Promocode).order_by(Promocode.id.asc())))

    return template(
        request=request,
        user=user,
        template_name="promocodes.j2.html",
        title=provider.config.i18n.promocodes,
        promocodes=promocodes,
        promocode_status_enum=PromocodeStatusEnum,
    )


@router.post("/promocodes", tags=["promocodes"])
async def post_promocodes(request: Request) -> JSONResponse:
    """
    Изменяет настройки промокодов
    """
    request_data = await get_request_data_or_responce(request, "promocodes")
    logger.debug(f"Got promocodes update request with {request_data=}")
    promocodes_attrs = prepare_attrs_object_from_request(request_data, status=PromocodeStatusEnum)
    return await try_to_save_attrs(Promocode, promocodes_attrs)
