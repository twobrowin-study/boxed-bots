from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from loguru import logger
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from starlette.status import HTTP_302_FOUND

from src.ui.app import provider
from src.ui.dependencies import RequireRoles, get_user
from src.ui.helpers import template
from src.ui.keycloak import KEYCLOAK_ROLE, KeycloakUser
from src.utils.custom_types import BotStatusEnum
from src.utils.db_model import BotStatus

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/", tags=["status"])
async def root() -> RedirectResponse:
    """Перенаправляет на статус бота"""
    return RedirectResponse(url=f"{provider.config.path_prefix}/status", status_code=HTTP_302_FOUND)


@router.get("/status", tags=["status"])
async def get_status(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """Показывает текущий статус работы бота"""
    bot_status = await provider.bot_status
    return template(
        request=request,
        user=user,
        template_name="status.j2.html",
        title=provider.config.i18n.bot_status,
        BotStatusEnum=BotStatusEnum,
        bot_status=bot_status,
    )


@router.post("/status", tags=["status"])
async def post_status(action: str) -> JSONResponse:
    """Устанавливает статус работы бота"""
    logger.success("Start set BotStatus...")
    async with provider.db_sessionmaker() as session:
        if action == "turn_off":
            await session.execute(update(BotStatus).values(bot_status=BotStatusEnum.OFF))
        elif action == "turn_on":
            await session.execute(update(BotStatus).values(bot_status=BotStatusEnum.ON))
        elif action == "restart":
            await session.execute(update(BotStatus).values(bot_status=BotStatusEnum.RESTART))
        elif action == "service":
            await session.execute(update(BotStatus).values(bot_status=BotStatusEnum.SERVICE))
        elif action == "activate_registration":
            await session.execute(update(BotStatus).values(is_registration_open=True))
        elif action == "deactivate_registration":
            await session.execute(update(BotStatus).values(is_registration_open=False))
        else:
            raise HTTPException(500, provider.config.i18n.error_found_unknown_bot_status)

        try:
            await session.commit()
            logger.success("Set BotStatus table")
            return JSONResponse({"error": False})
        except IntegrityError as err:
            logger.error(err)
            await session.rollback()
            raise HTTPException(500, provider.config.i18n.error_could_not_update_bot_status) from err
