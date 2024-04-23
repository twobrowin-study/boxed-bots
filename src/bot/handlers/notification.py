from telegram import Bot
from telegram.ext import CallbackContext
from telegram.constants import ParseMode

from sqlalchemy import select, update

from loguru import logger
from datetime import datetime

from bot.application import BBApplication

from utils.db_model import (
    User, Field,
    UserFieldValue,
    Notification,
    ReplyableConditionMessage
)
from utils.custom_types import NotificationStatusEnum

from bot.handlers.group import group_send_to_all_superadmin_tasked
from bot.helpers.keyboards import get_awaliable_inline_keyboard_for_user, get_keyboard_of_user

async def notify_job(context: CallbackContext) -> None:
    """
    Рассылка уведомлений
    """
    app: BBApplication = context.application
    bot: Bot = app.bot
    settings = await app.provider.settings

    logger.info("Perfoming notify job")

    async with app.provider.db_session() as session:
        notifications_to_plan_selected = await session.execute(
            select(Notification)
            .where(Notification.status == NotificationStatusEnum.TO_DELIVER)
        )
        notifications_to_plan = notifications_to_plan_selected.scalars().all()

        await session.execute(
            update(Notification)
            .where(Notification.id.in_([
                notification_to_plan.id for notification_to_plan in notifications_to_plan
            ]))
            .values(status = NotificationStatusEnum.PLANNED)
        )

        for planned_notification in notifications_to_plan:
            planned_notification: Notification
            logger.info(f"Planned notification {planned_notification.id} and performing notification to admins")

            reply_message: ReplyableConditionMessage = planned_notification.reply_condition_message
            condition_bool_field: Field = reply_message.condition_bool_field

            if not condition_bool_field:
                message = settings.notification_planned_admin_groups_template.format(
                    scheldue_date = planned_notification.notify_date,
                    text_markdown = reply_message.text_markdown
                )
            else:
                message = settings.notification_planned_admin_groups_condition_template.format(
                    condition = condition_bool_field.key,
                    scheldue_date = planned_notification.notify_date,
                    text_markdown = reply_message.text_markdown
                )
            
            await group_send_to_all_superadmin_tasked(
                app=app, message=message,
                parse_mode=ParseMode.MARKDOWN,
                session=session
            )

        await session.commit()

        notifications_to_perform_selected = await session.execute(
            select(Notification)
            .where(
                (Notification.status == NotificationStatusEnum.PLANNED) &
                (Notification.notify_date <= datetime.now())
            )
        )
        notifications_to_perform = notifications_to_perform_selected.scalars().all()

        await session.execute(
            update(Notification)
            .where(Notification.id.in_([
                notification_to_plan.id for notification_to_plan in notifications_to_perform
            ]))
            .values(status = NotificationStatusEnum.DELIVERED)
        )

        for planned_notification in notifications_to_perform:
            planned_notification: Notification
            logger.info(f"Performing notification {planned_notification.id} and performing notification to admins")

            reply_message: ReplyableConditionMessage = planned_notification.reply_condition_message
            condition_bool_field: Field = reply_message.condition_bool_field

            if not condition_bool_field:
                message = settings.notification_admin_groups_template.format(
                    text_markdown = reply_message.text_markdown
                )
                users_to_perform_notifications_selected = await session.execute(select(User))
            else:
                message = settings.notification_admin_groups_condition_template.format(
                    condition = condition_bool_field.key,
                    text_markdown = reply_message.text_markdown
                )
                users_to_perform_notifications_selected = await session.execute(
                    select(User)
                    .where(
                        (User.id == UserFieldValue.user_id) &
                        (Field.id == condition_bool_field.id) &
                        (Field.is_boolean == True) &
                        (UserFieldValue.field_id == Field.id) &
                        (UserFieldValue.value    == 'true')
                    )
                )

            users_to_perform_notifications = users_to_perform_notifications_selected.scalars().all()
            for user in users_to_perform_notifications:
                reply_markup = (
                    await get_awaliable_inline_keyboard_for_user(reply_message, user, session)
                ) or (
                    await get_keyboard_of_user(session, user)
                )

                app.create_task(
                    bot.send_message(
                        chat_id = user.chat_id,
                        text    = reply_message.text_markdown,
                        parse_mode   = ParseMode.MARKDOWN,
                        reply_markup = reply_markup
                    ),
                    update={
                        'user_id': user.id,
                        'chat_id': user.chat_id,
                        'notification_id':  planned_notification.id,
                        'reply_message_id': reply_message.id
                    }
                )
            
            await group_send_to_all_superadmin_tasked(
                app=app, message=message,
                parse_mode=ParseMode.MARKDOWN,
                session=session
            )

        await session.commit()

    logger.info("Done notify job")