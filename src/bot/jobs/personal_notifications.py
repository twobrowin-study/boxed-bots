from jinja2 import Template
from loguru import logger
from sqlalchemy import select, update
from telegram.ext import CallbackContext

from src.bot.helpers.telegram.prepare_field_file_value_and_type import prepare_field_file_value_and_type
from src.bot.helpers.telegram.send_message_and_return_file_id import send_message_and_return_file_id
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import (
    FieldStatusEnum,
    FieldTypeEnum,
    PersonalNotificationStatusEnum,
)
from src.utils.db_model import (
    Field,
    User,
    UserFieldValue,
)


async def job(context: CallbackContext) -> None:  # type: ignore
    """Рассылка персональных уведомлений"""
    app: BBApplication = context.application  # type: ignore

    logger.debug("Start personal notifications job")

    async with app.provider.db_sessionmaker() as session:
        personal_notifications_to_deliver = await session.execute(
            select(User, Field, UserFieldValue)
            .where(Field.id == UserFieldValue.field_id)
            .where(User.id == UserFieldValue.user_id)
            .where(Field.status == FieldStatusEnum.PERSONAL_NOTIFICATION)
            .where(UserFieldValue.personal_notification_status == PersonalNotificationStatusEnum.TO_DELIVER)
        )

    for (
        user,
        field,
        user_field_value,
    ) in personal_notifications_to_deliver.tuples():
        if user.have_banned_bot:
            logger.debug(
                f"Could not perform personal notification to user {user.id=} of field {field.id=} because user have banned bot"
            )
            continue

        logger.debug(f"Performing personal notification to user {user.id=} of field {field.id=}")
        try:
            async with app.provider.db_sessionmaker() as session:
                await session.execute(
                    update(UserFieldValue)
                    .where(UserFieldValue.id == user_field_value.id)
                    .values(personal_notification_status=PersonalNotificationStatusEnum.DELIVERED)
                )

                message_template = await _get_messsage_template(app=app, field=field, user_field_value=user_field_value)

                if field.type == FieldTypeEnum.FULL_TEXT:
                    message_text = await message_template.render_async(
                        field={
                            "key": field.key,
                            "value": user_field_value.value,
                        }
                    )
                elif field.type == FieldTypeEnum.BOOLEAN:
                    message_text = await message_template.render_async(
                        field={
                            "key": field.key,
                            "value": app.provider.config.i18n.yes
                            if user_field_value.value == "true"
                            else app.provider.config.i18n.no,
                        }
                    )
                else:
                    message_text = await message_template.render_async(
                        field={
                            "key": field.key,
                        }
                    )

                file, file_type = await prepare_field_file_value_and_type(app, field, user_field_value)

                file_id = await send_message_and_return_file_id(
                    app=app,
                    user=user,
                    text=message_text,
                    file=file,
                    file_type=file_type,
                    filename=user_field_value.value,
                )

                if file_id and type(file) is not str:
                    await session.execute(
                        update(UserFieldValue)
                        .where(UserFieldValue.id == user_field_value.id)
                        .values(value_file_id=file_id)
                    )
                await session.commit()

        except Exception:
            logger.debug(
                f"Could not perform personal notification to user {user.id=} of field {field.id=} for unknown reason"
            )
            file_id = None

    logger.debug("Done personal notifications job")


async def _get_messsage_template(app: BBApplication, field: Field, user_field_value: UserFieldValue) -> Template:
    """Получить шаблон сообщения"""
    settings = await app.provider.settings
    if field.key == settings.user_pass_field_plain:
        if user_field_value.value:
            return Template(settings.user_pass_message_plain, enable_async=True)
        return Template(settings.user_pass_removed_message_plain, enable_async=True)
    return Template(settings.user_personal_notification_message_j2_template, enable_async=True)
