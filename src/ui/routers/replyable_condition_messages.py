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
from src.utils.custom_types import FieldStatusEnum, FieldTypeEnum, ReplyTypeEnum
from src.utils.db_model import (
    Field,
    FieldBranch,
    ReplyableConditionMessage,
)

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/replyable_condition_messages", tags=["replyable_condition_messages"])
async def get_replyable_condition_messages(
    request: Request, user: Annotated[KeycloakUser, Depends(get_user)]
) -> HTMLResponse:
    """
    Показывает сообщения с условиями и ответами
    """
    async with provider.db_sessionmaker() as session:
        replyable_condition_messages = list(
            await session.scalars(select(ReplyableConditionMessage).order_by(ReplyableConditionMessage.id.asc()))
        )
        fields = list(await session.scalars(select(Field).order_by(Field.id.asc())))
        field_branches = list(await session.scalars(select(FieldBranch).order_by(FieldBranch.id.asc())))

    return template(
        request=request,
        user=user,
        template_name="replyable_condition_messages.j2.html",
        title=provider.config.i18n.replyable_condition_messages,
        replyable_condition_messages=replyable_condition_messages,
        reply_type_enum=ReplyTypeEnum,
        fields=fields,
        field_branches=field_branches,
        field_type_enum=FieldTypeEnum,
        field_status_enum=FieldStatusEnum,
    )


@router.post("/replyable_condition_messages", tags=["replyable_condition_messages"])
async def post_replyable_condition_messages(request: Request) -> JSONResponse:
    """
    Изменяет настройки сообщений с условиями и ответами
    """
    request_data = await get_request_data_or_responce(request, "replyable_condition_messages")

    logger.debug(f"Got replyable_condition_messages update request with {request_data=}")

    replyable_condition_messages_attrs = prepare_attrs_object_from_request(request_data, reply_type=ReplyTypeEnum)

    for idx, replyable_condition_message in replyable_condition_messages_attrs.items():
        error_prefix = provider.prepare_error_prefix(
            replyable_condition_message.get("name") or idx,
            provider.config.i18n.error_replyable_condition_message_prefix,
        )
        replyable_condition_message["photo_file_id"] = None

        if not replyable_condition_message.get("name") or not replyable_condition_message.get("text_markdown"):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_no_name_or_text_markdown_in_replyable_condition_message}",
            )

        photo_link = replyable_condition_message.get("photo_link")
        photo_bucket = replyable_condition_message.get("photo_bucket")
        photo_filename = replyable_condition_message.get("photo_filename")

        if photo_link and (photo_bucket or photo_filename):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_found_photo_link_in_replyable_condition_message_while_photo_bucket_or_photo_filename_are_also_in_replyable_condition_message}",
            )

        if (photo_bucket and not photo_filename) or (not photo_bucket and photo_filename):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_should_set_both_photo_bucket_and_photo_filename_at_the_same_time}",
            )

        reply_type: ReplyTypeEnum | None = replyable_condition_message.get("reply_type")
        reply_answer_field_branch_id: int | None = replyable_condition_message.get("reply_answer_field_branch_id")
        reply_answer_field_id: int | None = replyable_condition_message.get("reply_answer_field_id")
        reply_keyboard_keys: str | None = replyable_condition_message.get("reply_keyboard_keys")
        reply_status_replies: str | None = replyable_condition_message.get("reply_status_replies")

        if reply_type in [
            ReplyTypeEnum.FULL_TEXT_ANSWER,
            ReplyTypeEnum.FAST_ANSWER,
            ReplyTypeEnum.FAST_ANSWER_WITH_NEXT,
            ReplyTypeEnum.BRANCH_START,
        ] and (not reply_keyboard_keys or not reply_status_replies):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_reply_type_is_set_but_there_is_no_reply_keyboard_keys_or_reply_status_replies}",
            )

        if reply_type == ReplyTypeEnum.BRANCH_START and not reply_answer_field_branch_id:
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_did_not_found_reply_answer_field_branch_id_in_replyable_condition_message_object_while_status_is_branch_start}",
            )

        if (
            reply_type
            in [
                ReplyTypeEnum.FULL_TEXT_ANSWER,
                ReplyTypeEnum.FAST_ANSWER,
                ReplyTypeEnum.FAST_ANSWER_WITH_NEXT,
            ]
            and not reply_answer_field_id
        ):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_did_not_found_reply_answer_field_id_in_replyable_condition_message_object_while_status_is_full_text_answer_or_fast_answer}",
            )

        if (
            reply_type
            in [
                ReplyTypeEnum.FULL_TEXT_ANSWER,
                ReplyTypeEnum.BRANCH_START,
            ]
            and reply_keyboard_keys
            and "\n" in reply_keyboard_keys
        ):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_new_lines_found_in_reply_keyboard_keys_in_replyable_condition_message_object_while_status_is_full_text_answer_or_branch_start}",
            )

    return await try_to_save_attrs(ReplyableConditionMessage, replyable_condition_messages_attrs)
