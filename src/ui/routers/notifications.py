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
from src.utils.custom_types import NotificationStatusEnum
from src.utils.db_model import (
    Notification,
    ReplyableConditionMessage,
)

router = APIRouter(prefix=provider.config.path_prefix, dependencies=[Depends(RequireRoles([KEYCLOAK_ROLE]))])


@router.get("/notifications", tags=["notifications"])
async def get_notifications(request: Request, user: Annotated[KeycloakUser, Depends(get_user)]) -> HTMLResponse:
    """
    Показывает уведомления
    """
    async with provider.db_sessionmaker() as session:
        notifications = list(await session.scalars(select(Notification).order_by(Notification.id.asc())))
        replyable_condition_messages = list(
            await session.scalars(select(ReplyableConditionMessage).order_by(ReplyableConditionMessage.id.asc()))
        )

    return template(
        request=request,
        user=user,
        template_name="notifications.j2.html",
        title=provider.config.i18n.notifications,
        notifications=notifications,
        notification_status_enum=NotificationStatusEnum,
        replyable_condition_messages=replyable_condition_messages,
    )


@router.post("/notifications", tags=["notifications"])
async def post_notifications(request: Request) -> JSONResponse:
    """
    Изменяет настройки уведомлений
    """
    request_data = await get_request_data_or_responce(request, "notifications")
    logger.debug(f"Got notifications update request with {request_data=}")
    notifications_attrs = prepare_attrs_object_from_request(request_data, status=NotificationStatusEnum)
    return await try_to_save_attrs(Notification, notifications_attrs)
