from datetime import datetime

from jinja2 import Template
from loguru import logger
from sqlalchemy import select, update
from telegram.ext import CallbackContext

from src.bot.helpers.replyable_condition_messages.sends import (
    send_replyable_condition_message,
    send_replyable_condition_message_to_user,
)
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import GroupStatusEnum, NotificationStatusEnum
from src.utils.db_model import Group, Notification, User


async def job(context: CallbackContext) -> None:  # type: ignore
    """Задача по рассылки уведомлений"""
    app: BBApplication = context.application  # type: ignore
    await _plan_notifications(app)
    await _perform_notifications(app)


async def _plan_notifications(app: BBApplication) -> None:
    """Планирование отправки уведомлений"""
    logger.debug("Start plan notifications job")

    settings = await app.provider.settings

    async with app.provider.db_sessionmaker() as session:
        notifications_to_plan = await session.scalars(
            select(Notification).where(Notification.status == NotificationStatusEnum.TO_DELIVER)
        )

        for planned_notification in notifications_to_plan:
            logger.debug(f"Planned notification {planned_notification.id=} and sending message to admins")

            await session.execute(
                update(Notification)
                .where(Notification.id == planned_notification.id)
                .values(status=NotificationStatusEnum.PLANNED)
            )

            admin_message = await Template(
                settings.group_admin_notification_planned_message_j2_template, enable_async=True
            ).render_async(notification=planned_notification)

            await _send_notification_to_all_admins(
                app=app,
                notification=planned_notification,
                text_markdown_override=admin_message,
            )

        await session.commit()

    logger.debug("Done plan notifications job")


async def _perform_notifications(app: BBApplication) -> None:
    """Выполнение уведомлений"""
    logger.debug("Start perform notifications job")

    settings = await app.provider.settings

    async with app.provider.db_sessionmaker() as session:
        notifications_to_perform = await session.scalars(
            select(Notification)
            .where(Notification.status == NotificationStatusEnum.PLANNED)
            .where(Notification.schedule_datetime <= datetime.now())  # noqa: DTZ005
        )

        for notification_to_perform in notifications_to_perform:
            logger.debug(f"Performing notification {notification_to_perform.id=}")

            await session.execute(
                update(Notification)
                .where(Notification.id == notification_to_perform.id)
                .values(status=NotificationStatusEnum.DELIVERED)
            )

            for user in await session.scalars(select(User)):
                if user.have_banned_bot:
                    logger.debug(
                        f"Could not perform notification {notification_to_perform.id=} to user {user.id=} because user have banned bot"
                    )
                    continue

                logger.debug(f"Performing notification {notification_to_perform.id=} to user {user.id=}")

                await send_replyable_condition_message_to_user(
                    app=app,
                    user=user,
                    reply_condition_message=notification_to_perform.reply_condition_message,
                )

            for normal_group in await session.scalars(select(Group).where(Group.status == GroupStatusEnum.NORMAL)):
                logger.debug(
                    f"Performing notification {notification_to_perform.id=} to normal group {normal_group.id=}"
                )

                await send_replyable_condition_message(
                    app=app,
                    chat_id=normal_group.chat_id,
                    reply_condition_message=notification_to_perform.reply_condition_message,
                )

            logger.debug(f"Performed notification {notification_to_perform.id=} to admins")

            admin_message = await Template(
                settings.group_admin_notification_sent_message_j2_template, enable_async=True
            ).render_async(notification=notification_to_perform)

            await _send_notification_to_all_admins(
                app=app,
                notification=notification_to_perform,
                text_markdown_override=admin_message,
            )

        await session.commit()

    logger.debug("Done perform notifications job")


async def _send_notification_to_all_admins(
    app: BBApplication,
    notification: Notification,
    text_markdown_override: str,
) -> None:
    async with app.provider.db_sessionmaker() as session:
        admin_groups = await session.scalars(
            select(Group).where(Group.status.in_([GroupStatusEnum.ADMIN, GroupStatusEnum.SUPER_ADMIN]))
        )
    for admin_group in admin_groups:
        await send_replyable_condition_message(
            app=app,
            chat_id=admin_group.chat_id,
            reply_condition_message=notification.reply_condition_message,
            text_markdown_override=text_markdown_override,
        )
