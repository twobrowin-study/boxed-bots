from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.exceptions import ChangeFieldNoQuestionError, ChangeFieldNotFoundError
from src.bot.helpers.fields.keyboards import construct_field_reply_keyboard_markup
from src.bot.helpers.users import (
    get_user_callback_query_data_send_strange_error_and_rise,
)
from src.bot.helpers.users.registration import update_user_registration_and_send_message
from src.bot.telegram.callback_constants import UserChangeFieldCallback
from src.utils.db_model import Field


async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку изменения значения поля"""
    handler = "user field value change"

    (
        app,
        user,
        callback_query_data,
        callback_query_message,
        settings,
    ) = await get_user_callback_query_data_send_strange_error_and_rise(update, context, handler)

    changing_field_id = int(callback_query_data.removeprefix(UserChangeFieldCallback.PREFIX))

    async with app.provider.db_sessionmaker() as session:
        changing_field = await session.scalar(select(Field).where(Field.id == changing_field_id))
        if not changing_field:
            raise ChangeFieldNotFoundError
        if not changing_field.question_markdown_or_j2_template:
            raise ChangeFieldNoQuestionError

    await update_user_registration_and_send_message(
        app=app,
        user=user,
        message=callback_query_message,
        text=changing_field.question_markdown_or_j2_template,
        settings=settings,
        reply_keyboad_override=construct_field_reply_keyboard_markup(
            changing_field, settings, "change_user_field_value"
        ),
        curr_field_id=changing_field.id,
        change_field_message_id=callback_query_message.id,
        pass_field_change=False,
    )
