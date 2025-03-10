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
from src.utils.custom_types import KeyboardKeyStatusEnum
from src.utils.db_model import (
    FieldBranch,
    KeyboardKey,
    ReplyableConditionMessage,
)

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/keyboard_keys", tags=["keyboard_keys"])
async def get_keyboard_keys(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """
    Показывает кнопки клавиатуры
    """
    async with provider.db_sessionmaker() as session:
        keyboard_keys = list(await session.scalars(select(KeyboardKey).order_by(KeyboardKey.id.asc())))
        replyable_condition_messages = list(
            await session.scalars(select(ReplyableConditionMessage).order_by(ReplyableConditionMessage.id.asc()))
        )
        field_branches = list(await session.scalars(select(FieldBranch).order_by(FieldBranch.id.asc())))

    return template(
        request=request,
        user=user,
        template_name="keyboard_keys.j2.html",
        title=provider.config.i18n.keyboard_keys,
        keyboard_keys=keyboard_keys,
        keyboard_key_status_enum=KeyboardKeyStatusEnum,
        replyable_condition_messages=replyable_condition_messages,
        field_branches=field_branches,
    )


@router.post("/keyboard_keys", tags=["keyboard_keys"])
async def post_keyboard_keys(request: Request) -> JSONResponse:
    """
    Изменяет настройки клавиш клавиатуры
    """
    request_data = await get_request_data_or_responce(request, "keyboard_keys")

    logger.debug(f"Got keyboard_keys update request with {request_data=}")

    keyboard_keys_attrs = prepare_attrs_object_from_request(request_data, status=KeyboardKeyStatusEnum)

    for idx, keyboard_key in keyboard_keys_attrs.items():
        error_prefix = provider.prepare_error_prefix(
            keyboard_key.get("key") or idx, provider.config.i18n.error_keyboard_key_prefix
        )

        if keyboard_key.get("status") == KeyboardKeyStatusEnum.NORMAL and not keyboard_key.get(
            "reply_condition_message_id"
        ):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_did_not_found_reply_condition_message_id_in_keyboard_key_object_while_status_is_normal}",
            )

        if keyboard_key.get("status") in [
            KeyboardKeyStatusEnum.ME,
            KeyboardKeyStatusEnum.ME_CHANGE,
        ] and not keyboard_key.get("branch_id"):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_did_not_found_branch_id_in_keyboard_key_object_while_status_is_me}",
            )

        if keyboard_key.get("status") == KeyboardKeyStatusEnum.BACK and not keyboard_key.get("parent_key_id"):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_did_not_found_parent_key_id_in_keyboard_key_object_while_status_is_back}",
            )

        if keyboard_key.get("status") == KeyboardKeyStatusEnum.NEWS and keyboard_key.get("parent_key_id"):
            raise HTTPException(
                500,
                f"{error_prefix} {provider.config.i18n.error_cannot_set_parent_key_id_in_keyboard_key_object_while_status_is_news}",
            )

    return await try_to_save_attrs(KeyboardKey, keyboard_keys_attrs)
