from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from loguru import logger
from sqlalchemy import select
from starlette.status import HTTP_302_FOUND

from src.ui.app import provider
from src.ui.dependencies import RequireRoles, get_user
from src.ui.helpers import (
    get_request_data_or_responce,
    prepare_attrs_object_from_request,
    template,
    try_to_save_attrs,
)
from src.ui.keycloak import KEYCLOAK_ROLE, KeycloakUser
from src.utils.custom_types import FieldStatusEnum, FieldTypeEnum
from src.utils.db_model import Field, FieldBranch

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/fields", tags=["fields"])
async def get_fields() -> RedirectResponse:
    """Перенаправляет на страницу полей с самой первой веткой полей"""
    async with provider.db_sessionmaker() as session:
        first_field_branch_id = await session.scalar(
            select(FieldBranch.id).order_by(FieldBranch.order_place.asc()).limit(1)
        )
        if not first_field_branch_id:
            raise HTTPException(500, provider.config.i18n.error_there_is_no_field_branches)
    return RedirectResponse(
        url=f"{provider.config.path_prefix}/fields/{first_field_branch_id}",
        status_code=HTTP_302_FOUND,
    )


@router.get("/fields/{branch_id}", tags=["fields"])
async def get_fields_by_branch(
    branch_id: int, request: Request, user: Annotated[KeycloakUser, Depends(get_user)]
) -> HTMLResponse:
    """Показывает пользовательские поля"""
    async with provider.db_sessionmaker() as session:
        field_branches = list(await session.scalars(select(FieldBranch).order_by(FieldBranch.order_place.asc())))
        fields = list(
            await session.scalars(select(Field).where(Field.branch_id == branch_id).order_by(Field.order_place.asc()))
        )

    return template(
        request=request,
        user=user,
        template_name="fields.j2.html",
        title=provider.config.i18n.fields,
        field_branch_id=branch_id,
        field_branches=field_branches,
        fields=fields,
        field_status_enum=FieldStatusEnum,
        field_type_enum=FieldTypeEnum,
    )


@router.post("/fields/{branch_id}", tags=["fields"])
async def post_fields(branch_id: int, request: Request) -> JSONResponse:
    """
    Изменяет настройки пользовательские поля
    """
    request_data = await get_request_data_or_responce(request, "fields")

    logger.debug(f"Got fields update request on branch {branch_id=} with {request_data=}")

    fields_attrs = prepare_attrs_object_from_request(
        request_data, ["order_place", "report_order"], status=FieldStatusEnum, type=FieldTypeEnum
    )

    for idx, field in fields_attrs.items():
        error_prefix = provider.prepare_error_prefix(field.get("key") or idx, provider.config.i18n.error_field_prefix)

        if field.get("bucket") and field.get("type") not in [
            FieldTypeEnum.PDF_DOCUMENT,
            FieldTypeEnum.ZIP_DOCUMENT,
            FieldTypeEnum.IMAGE,
        ]:
            raise HTTPException(
                500, f"{error_prefix} {provider.config.i18n.error_field_with_bucket_must_have_document_or_image_type}"
            )

        if field.get("type") in [
            FieldTypeEnum.PDF_DOCUMENT,
            FieldTypeEnum.ZIP_DOCUMENT,
            FieldTypeEnum.IMAGE,
        ] and not field.get("bucket"):
            raise HTTPException(
                500, f"{error_prefix} {provider.config.i18n.error_field_with_document_or_image_type_must_have_bucket}"
            )

        if field.get("validation_regexp") and field.get("type") != FieldTypeEnum.FULL_TEXT:
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_field_with_validation_regexp_should_be_full_text_type}",
            )

        if field.get("validation_remove_regexp") and field.get("type") != FieldTypeEnum.FULL_TEXT:
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_field_with_validation_remove_regexp_should_be_full_text_type}",
            )

        if field.get("answer_options") and field.get("type") != FieldTypeEnum.FULL_TEXT:
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_answer_options_can_only_be_shown_with_full_text_field}",
            )

        if field.get("status") in [
            FieldStatusEnum.JINJA2_FROM_USER_AFTER_REGISTRATION,
            FieldStatusEnum.JINJA2_FROM_USER_ON_CREATE,
            FieldStatusEnum.PERSONAL_NOTIFICATION,
        ] and (
            field.get("is_skippable")
            or field.get("check_future_date")
            or field.get("check_future_year")
            or field.get("upper_before_save")
        ):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_for_jinja2_field_must_not_be_set_is_skippable_check_future_date_check_future_year_upper_before_save_params}",
            )

        if field.get("status") in [
            FieldStatusEnum.JINJA2_FROM_USER_AFTER_REGISTRATION,
            FieldStatusEnum.JINJA2_FROM_USER_ON_CREATE,
        ] and field.get("type") not in [FieldTypeEnum.FULL_TEXT, FieldTypeEnum.BOOLEAN]:
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_jinja2_field_should_be_full_text_or_boolean}",
            )

    return await try_to_save_attrs(Field, fields_attrs)
