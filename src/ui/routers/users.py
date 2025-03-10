import io
from datetime import datetime
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from loguru import logger
from sqlalchemy import insert, select, update
from starlette.status import HTTP_302_FOUND, HTTP_404_NOT_FOUND
from xlsxwriter.worksheet import Worksheet

from src.ui.app import provider
from src.ui.dependencies import RequireRoles, get_user
from src.ui.helpers import (
    get_request_data_or_responce,
    template,
)
from src.ui.keycloak import KEYCLOAK_ROLE, KeycloakUser
from src.utils.custom_types import (
    FieldStatusEnum,
    FieldTypeEnum,
    PassSubmitStatusEnum,
    PersonalNotificationStatusEnum,
)
from src.utils.db_model import (
    Field,
    FieldBranch,
    User,
    UserFieldValue,
)

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/users", tags=["users"])
async def get_users() -> RedirectResponse:
    """Перенаправляет на страницу пользователей с самой первой веткой полей"""
    async with provider.db_sessionmaker() as session:
        first_field_branch_id = await session.scalar(
            select(FieldBranch.id).order_by(FieldBranch.order_place.asc()).limit(1)
        )
        if not first_field_branch_id:
            raise HTTPException(500, provider.config.i18n.error_there_is_no_field_branches)
    return RedirectResponse(
        url=f"{provider.config.path_prefix}/users/branch/{first_field_branch_id}",
        status_code=HTTP_302_FOUND,
    )


@router.get("/users/branch/{branch_id}", tags=["users"])
async def get_users_by_branch(
    branch_id: int, request: Request, user: Annotated[KeycloakUser, Depends(get_user)]
) -> HTMLResponse:
    """Показывает пользователей"""
    settings = await provider.settings
    async with provider.db_sessionmaker() as session:
        curr_field_branch = await session.scalar(select(FieldBranch).where(FieldBranch.id == branch_id))
        if not curr_field_branch:
            return HTMLResponse(status_code=HTTP_404_NOT_FOUND)

        field_branches = list(await session.scalars(select(FieldBranch).order_by(FieldBranch.order_place.asc())))

        fields = list(
            await session.scalars(select(Field).where(Field.branch_id == branch_id).order_by(Field.order_place.asc()))
        )

        users = await session.scalars(select(User).order_by(User.id.asc()))
        users_prepared = [user.prepare() for user in users]

        user_name_field = await session.scalar(select(Field).where(Field.key == settings.user_name_field_plain))

        return template(
            request=request,
            user=user,
            template_name="users.j2.html",
            title=provider.config.i18n.users,
            curr_field_branch=curr_field_branch,
            field_branches=field_branches,
            fields=fields,
            users=users_prepared,
            user_name_field=user_name_field,
            field_status_enum=FieldStatusEnum,
            field_type_enum=FieldTypeEnum,
            personal_notification_status_enum=PersonalNotificationStatusEnum,
        )


def get_user_message_data(
    data_user_id: str, fields_dict: dict[str, Any]
) -> tuple[int, dict[str, dict[str, str] | str]]:
    if not data_user_id.isnumeric():
        raise HTTPException(500, f"{provider.config.i18n.error_got_not_numeric_user_id} {data_user_id=}")
    if type(fields_dict["fields"]) is not dict:
        raise HTTPException(500, f"{provider.config.i18n.error_got_bad_user_fields} {fields_dict['fields']=}")
    return int(data_user_id), fields_dict["fields"]


def get_field_data(data_field_id: str, field_value: dict[str, str] | str) -> tuple[int, str]:
    if not data_field_id.isnumeric():
        raise HTTPException(500, f"{provider.config.i18n.error_got_not_numeric_field_id} {data_field_id=}")

    if type(field_value) is str:
        return int(data_field_id), field_value

    if type(field_value) is dict:
        if "value" not in field_value:
            raise HTTPException(500, f"{provider.config.i18n.error_value_not_in_field_value} {field_value=}")
        return int(data_field_id), field_value["value"]

    raise HTTPException(500, f"{provider.config.i18n.error_value_not_directory_field_value} {field_value=}")


@router.post("/users/branch/{branch_id}", tags=["users"])
async def post_users_by_branch(branch_id: int, request: Request) -> JSONResponse:
    """Устанавливает значения полей для пользователей"""
    request_data = await get_request_data_or_responce(request, "users")

    logger.debug(f"Got fields update request on branch {branch_id=} with {request_data=}")

    async with provider.db_sessionmaker() as session:
        for data_user_id, fields_dict in request_data.items():
            user_id, fields_request = get_user_message_data(data_user_id, fields_dict)

            for data_field_id, field_value in fields_request.items():
                field_id, value = get_field_data(data_field_id, field_value)

                user_field_value_obj = await session.scalar(
                    select(UserFieldValue)
                    .where(UserFieldValue.user_id == user_id)
                    .where(UserFieldValue.field_id == field_id)
                )

                field = await session.scalar(select(Field).where(Field.id == field_id))
                if not field:
                    raise HTTPException(500, f"{provider.config.i18n.error_field_id_was_not_found} {field_id=}")

                personal_notification_status = None
                if field.status == FieldStatusEnum.PERSONAL_NOTIFICATION:
                    if value:
                        personal_notification_status = PersonalNotificationStatusEnum.TO_DELIVER
                    else:
                        personal_notification_status = PersonalNotificationStatusEnum.INACTIVE

                    settings = await provider.settings
                    if field.key == settings.user_pass_field_plain and value:
                        await session.execute(
                            update(User).where(User.id == user_id).values(pass_status=PassSubmitStatusEnum.APPROVED)
                        )

                if not user_field_value_obj:
                    await session.execute(
                        insert(UserFieldValue).values(
                            user_id=user_id,
                            field_id=field_id,
                            value=value,
                            personal_notification_status=personal_notification_status,
                        )
                    )
                elif value != user_field_value_obj.value:
                    await session.execute(
                        update(UserFieldValue)
                        .where(UserFieldValue.id == user_field_value_obj.id)
                        .values(
                            value=value,
                            personal_notification_status=personal_notification_status,
                            value_file_id=None,
                        )
                    )

        await session.commit()
        return JSONResponse({"error": False}, status_code=200)


@router.get("/users/report/xslx", tags=["users"])
async def get_users_report() -> Response:
    """Возвращает полный отчёт по пользователям в формате xlsx"""
    logger.debug("Starting prepare of users full report")

    async with provider.db_sessionmaker() as session:
        users_selected = await session.execute(select(User).order_by(User.id.asc()))
        users_df = pd.DataFrame([user.to_plain_dict(i18n=provider.config.i18n) for user in users_selected.scalars()])

        logger.debug(f"Users df:\n{users_df}")

        filename = f"{datetime.now(provider.tz).strftime('%Y_%m_%d__%H_%M_%S')}__{provider.config.path_prefix.replace('/', '')}_user_report.xlsx"
        headers = {
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }

        sheet_name = provider.config.i18n.download_users_report

        report_bio = io.BytesIO()
        with pd.ExcelWriter(report_bio) as writer:
            users_df.to_excel(
                writer,
                startrow=0,
                merge_cells=False,
                sheet_name=sheet_name,
                index=False,
            )

            worksheet: Worksheet = writer.sheets[sheet_name]
            row_count = len(users_df.index)
            column_count = len(users_df.columns)

            worksheet.autofilter(0, 0, row_count - 1, column_count - 1)

            for idx, col in enumerate(users_df):
                series = users_df[col]
                max_len = max((series.astype(str).map(len).max(), len(str(series.name)))) + 5
                worksheet.set_column(idx, idx, max_len)

        report_bio.seek(0)
        return StreamingResponse(report_bio, headers=headers, media_type=headers["Content-Type"])
