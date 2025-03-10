from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
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
from src.utils.custom_types import GroupStatusEnum
from src.utils.db_model import Group

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/groups", tags=["groups"])
async def get_groups(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """
    Показывает все группы телеграм
    """
    async with provider.db_sessionmaker() as session:
        groups = list(await session.scalars(select(Group).order_by(Group.id.asc())))

    return template(
        request=request,
        user=user,
        template_name="groups.j2.html",
        title=provider.config.i18n.groups,
        groups=groups,
        group_status_enum=GroupStatusEnum,
    )


@router.post("/groups", tags=["groups"])
async def post_groups(request: Request) -> JSONResponse:
    """
    Изменяет настройки групп телеграм
    """
    request_data = await get_request_data_or_responce(request, "groups")
    logger.debug(f"Got groups update request with {request_data=}")
    groups_attrs = prepare_attrs_object_from_request(request_data, ["chat_id"], status=GroupStatusEnum)

    for idx, group in groups_attrs.items():
        error_prefix = provider.prepare_error_prefix(
            group.get("chat_id") or idx, provider.config.i18n.error_group_prefix
        )
        if group.get("pass_management") and group.get("status") not in [
            GroupStatusEnum.ADMIN,
            GroupStatusEnum.SUPER_ADMIN,
            GroupStatusEnum.INACTIVE,
        ]:
            HTTPException(
                500, f"{error_prefix} {provider.config.i18n.error_trying_to_set_pass_managment_to_non_admin_group}"
            )

    return await try_to_save_attrs(Group, groups_attrs)
