from telegram import Bot
from telegram.ext import CallbackContext
from telegram.constants import ParseMode

from sqlalchemy import select, update

from loguru import logger
from datetime import datetime
from jinja2 import Template

from bot.application import BBApplication

from utils.db_model import (
    User, Field,
    UserFieldValue,
    Notification,
    ReplyableConditionMessage
)
from utils.custom_types import (
    NotificationStatusEnum,
    FieldStatusEnum,
    PersonalNotificationStatusEnum
)

from bot.handlers.group import group_send_to_all_superadmin_tasked
from bot.helpers.keyboards import get_awaliable_inline_keyboard_for_user, get_keyboard_of_user

from bot.helpers.promocodes import check_expired_promocodes

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
            logger.info(f"Planned notification {planned_notification.id=} and performing notification to admins")

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

        for notification_to_perform in notifications_to_perform:
            notification_to_perform: Notification
            logger.info(f"Performing notification {notification_to_perform.id=} and performing notification to admins")

            reply_message: ReplyableConditionMessage = notification_to_perform.reply_condition_message
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
                if user.have_banned_bot:
                    logger.info(f"Could not perform notification {notification_to_perform.id=} to user {user.id=} because user have banned bot")
                    continue

                logger.info(f"Performing notification {notification_to_perform.id=} and performing notification to user {user.id=}")
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
                        'notification_id':  notification_to_perform.id,
                        'reply_message_id': reply_message.id
                    }
                )
            
            await group_send_to_all_superadmin_tasked(
                app=app, message=message,
                parse_mode=ParseMode.MARKDOWN,
                session=session
            )
        
        logger.info("Performing personal notifications")

        personal_notifications_to_perform = await session.execute(
            select(User, Field, UserFieldValue)
            .where(Field.id == UserFieldValue.field_id)
            .where(User.id == UserFieldValue.user_id)
            .where(Field.status == FieldStatusEnum.PERSONAL_NOTIFICATION)
            .where(UserFieldValue.personal_notification_status == PersonalNotificationStatusEnum.TO_DELIVER)
        )

        for user, field, uf_personal_notification in personal_notifications_to_perform.tuples():
            logger.info(f"Performing personal notification to user {user.id=} of field {field.id}")
            await session.execute(
                update(UserFieldValue)
                .where(UserFieldValue.id == uf_personal_notification.id)
                .values(personal_notification_status = PersonalNotificationStatusEnum.DELIVERED)
            )

            if field.key == settings.qr_code_user_field:
                qr_code = uf_personal_notification.value
                if qr_code in ['', None]:
                    app.create_task(
                        bot.send_message(
                            user.chat_id, settings.no_qr_code_message,
                            parse_mode=ParseMode.MARKDOWN
                        ),
                        update={
                            'user_id': user.id,
                            'chat_id': user.chat_id,
                            'field_id': field.id,
                            'uf_personal_notification_id':  uf_personal_notification.id,
                            'type': 'no_qr'
                        }
                    )
                else:
                    app.create_task(
                        bot.send_photo(
                            user.chat_id, uf_personal_notification.value,
                            caption=settings.qr_code_message,
                            parse_mode=ParseMode.MARKDOWN
                        ),
                        update={
                            'user_id': user.id,
                            'chat_id': user.chat_id,
                            'field_id': field.id,
                            'uf_personal_notification_id':  uf_personal_notification.id,
                            'type': 'qr'
                        }
                    )
                logger.info(f"Performed QR personal notification to user {user.id=} of field {field.id}")
                continue
            
            app.create_task(
                bot.send_message(
                    user.chat_id,
                    Template(settings.personal_notification_jinja_template)
                        .render(field = {
                            "key": field.key,
                            "value": uf_personal_notification.value
                        }),
                    parse_mode=ParseMode.MARKDOWN
                ),
                update={
                    'user_id': user.id,
                    'chat_id': user.chat_id,
                    'field_id': field.id,
                    'uf_personal_notification_id':  uf_personal_notification.id,
                    'type': 'personal_notify'
                }
            )
            logger.info(f"Performed personal notification to user {user.id=} of field {field.id}")

        await session.commit()
    
    app.create_task(
        check_expired_promocodes(context)
    )

    logger.info("Done notify job")