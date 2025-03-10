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
from src.utils.custom_types import FieldBranchStatusEnum
from src.utils.db_model import FieldBranch

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/field_branches", tags=["field_branches"])
async def get_field_branches(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """
    Показывает ветки пользовательскх полей
    """
    async with provider.db_sessionmaker() as session:
        field_branches = list(await session.scalars(select(FieldBranch).order_by(FieldBranch.order_place.asc())))

    return template(
        request=request,
        user=user,
        template_name="field_branches.j2.html",
        title=provider.config.i18n.field_branches,
        field_branches=field_branches,
        field_branch_status_enum=FieldBranchStatusEnum,
    )


@router.post("/field_branches", tags=["field_branches"])
async def post_field_branches(request: Request) -> JSONResponse:
    """
    Изменяет настройки веток пользовательских полей
    """
    request_data = await get_request_data_or_responce(request, "field_branches")
    logger.debug(f"Got field_branches update request with {request_data=}")
    field_branches_attrs = prepare_attrs_object_from_request(
        request_data, ["order_place"], status=FieldBranchStatusEnum
    )
    return await try_to_save_attrs(FieldBranch, field_branches_attrs)
