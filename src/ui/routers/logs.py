from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from src.ui.app import provider
from src.ui.dependencies import RequireRoles, get_user
from src.ui.helpers import template
from src.ui.keycloak import KEYCLOAK_ROLE, KeycloakUser
from src.utils.db_model import Log

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/logs", tags=["logs"])
async def logs(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """
    Показывает текущие логи работы бота
    """
    async with provider.db_sessionmaker() as session:
        logs = await session.scalars(select(Log).order_by(Log.id.desc()).limit(1000))

    return template(
        request=request,
        user=user,
        template_name="logs.j2.html",
        title=provider.config.i18n.logs,
        logs=logs,
    )
