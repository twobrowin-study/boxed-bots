from jinja2 import Template
from loguru import logger
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.exceptions import (
    FastAnswerNoFieldError,
    FastAnswerNoReplyableConditionMessageError,
    FastAnswerNotEnoughReplyAnswersError,
    FastAnswerNotEnoughValuesError,
    NextReplyConditionMessageAfterFastAnswerWasNotFoundError,
)
from src.bot.helpers.fields.values.calculate import user_calculate_after_registration_fields
from src.bot.helpers.fields.values.upsert import user_upsert_string_field_value
from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.replyable_condition_messages.sends import send_replyable_condition_message_to_user
from src.bot.helpers.users import get_user_callback_query_data_send_strange_error_and_rise
from src.bot.telegram.application import BBApplication
from src.bot.telegram.callback_constants import UserFastAnswerReplyCallback
from src.utils.custom_types import ReplyTypeEnum
from src.utils.db_model import Field, ReplyableConditionMessage, Settings, User


async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопки быстрого ответа пользователя"""
    handler = "fast answer"

    (
        app,
        user,
        callback_query_data,
        callback_query_message,
        settings,
    ) = await get_user_callback_query_data_send_strange_error_and_rise(update, context, handler)

    reply_message_id, field_id, answer_idx = map(
        int,
        callback_query_data.removeprefix(UserFastAnswerReplyCallback.PREFIX).split(UserFastAnswerReplyCallback.SPLIT),
    )

    logger.debug(
        f"Got {handler} from user {user.id=} to reply message {reply_message_id=} for field {field_id=} with answer idx {answer_idx=}"
    )

    async with app.provider.db_sessionmaker() as session:
        reply_message = await session.scalar(
            select(ReplyableConditionMessage).where(ReplyableConditionMessage.id == reply_message_id)
        )
        field = await session.scalar(select(Field).where(Field.id == field_id))

    # Проверка наличия сообщения с условием и ответом и поля
    if not reply_message:
        raise FastAnswerNoReplyableConditionMessageError
    if not field:
        raise FastAnswerNoFieldError

    # Проверка наличия переданного пользователям значения поля
    if not reply_message.reply_keyboard_keys:
        raise FastAnswerNotEnoughValuesError
    try:
        field_value = reply_message.reply_keyboard_keys.split("\n")[answer_idx]
    except Exception as e:
        raise FastAnswerNotEnoughValuesError from e

    # Проверка наличия отправляемого ответа пользователю
    if not reply_message.reply_status_replies:
        raise FastAnswerNotEnoughReplyAnswersError
    try:
        answer_text_or_next_reply_message_name = reply_message.reply_status_replies.split("\n")[answer_idx]
    except Exception as e:
        raise FastAnswerNotEnoughReplyAnswersError from e

    # Отправка пользователю сообщения с ответом
    if reply_message.reply_type == ReplyTypeEnum.FAST_ANSWER:
        await callback_query_message.reply_markdown(
            text=answer_text_or_next_reply_message_name,
            reply_markup=await get_user_current_keyboard(app, user),
        )

    # Отправка пользователю:
    # - Выбранного им варианта ответа
    # - Следующего сообщения с ответом
    # - Удаление клавиатуры предыдущего сообщения
    elif reply_message.reply_type == ReplyTypeEnum.FAST_ANSWER_WITH_NEXT:
        selected_text = await Template(
            settings.user_fast_answer_reply_message_j2_template, enable_async=True
        ).render_async(answer=field_value)
        await callback_query_message.reply_markdown(selected_text)
        await _send_next_reply_message(app, user, answer_text_or_next_reply_message_name, settings)
        await callback_query_message.edit_reply_markup(reply_markup=None)

    # Сохранение ответа
    await user_upsert_string_field_value(app, user, field, callback_query_message, field_value)

    # Расчитать поля пользователя
    await user_calculate_after_registration_fields(app, user)


async def _send_next_reply_message(
    app: BBApplication, user: User, next_reply_message_name: str, settings: Settings
) -> None:
    async with app.provider.db_sessionmaker() as session:
        next_reply_message = await session.scalar(
            select(ReplyableConditionMessage).where(ReplyableConditionMessage.name == next_reply_message_name)
        )
    if not next_reply_message:
        raise NextReplyConditionMessageAfterFastAnswerWasNotFoundError
    await send_replyable_condition_message_to_user(app, user, next_reply_message, settings)
