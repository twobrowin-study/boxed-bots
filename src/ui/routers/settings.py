from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)
from loguru import logger
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from src.ui.app import provider
from src.ui.dependencies import RequireRoles, get_user
from src.ui.helpers import (
    get_request_data_or_responce,
    template,
)
from src.ui.keycloak import KEYCLOAK_ROLE, KeycloakUser
from src.utils.db_model import Settings

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/settings", tags=["settings"])
async def get_settings(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """
    Показывает настройки бота
    """
    curr_settings = await provider.settings
    settings_with_description = [
        {
            "key": key,
            "description": default_dict["description"],
            "value": getattr(curr_settings, key),
        }
        for key, default_dict in provider.config.defaults.model_dump().items()
    ]
    return template(
        request=request,
        user=user,
        template_name="settings.j2.html",
        title=provider.config.i18n.settings,
        settings=settings_with_description,
    )


@router.post("/settings", tags=["settings"])
async def post_settings(request: Request) -> JSONResponse:
    """
    Устанавливает настройки бота
    """
    request_data = await get_request_data_or_responce(request, "settings")

    logger.debug(f"Got settings update request with {request_data=}")

    settings_attrs = {
        key: value_dict["value"]
        for key, value_dict in request_data.items()
        if isinstance(value_dict, dict) and "value" in value_dict
    }

    async with provider.db_sessionmaker() as session:
        await session.execute(update(Settings).values(**settings_attrs))

        try:
            await session.commit()
            logger.success("Set Status table...")
            return JSONResponse({"error": False})
        except IntegrityError as err:
            logger.error(err)
            await session.rollback()
            raise HTTPException(500, provider.config.i18n.error_could_not_update_settings) from err
