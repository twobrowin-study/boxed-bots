from loguru import logger
from sqlalchemy import update as sql_update
from telegram import Message, Update
from telegram.ext import ContextTypes

from src.bot.helpers.fields.deferred import user_defer_field
from src.bot.helpers.fields.transitions import (
    user_set_next_field_and_send_next_question_or_final,
    user_upsert_changed_field_value_and_send_complete,
    user_upsert_field_value_and_send_next_question_or_final,
)
from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.keyboards.user_key_hits import reply_keyboard_key_hit
from src.bot.helpers.users import get_user_message_data_send_strange_error_and_rise
from src.bot.telegram.application import BBApplication
from src.utils.db_model import Settings, User


async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых и файловых сообщений пользователя"""

    app, user, message, settings = await get_user_message_data_send_strange_error_and_rise(
        update, context, handler="text/file"
    )

    # Реакция на отсутствие контекста ответа на вопрос
    if not user.curr_field:
        await _user_not_field_context_handlers(app, user, message, settings)
        return

    # Проверка нажатия на кнопки пропуска вопроса или откладывания ветки
    if not user.change_field_message_id:
        if user.curr_field.is_skippable and message.text == settings.user_skip_button_plain:
            logger.debug(f"Field skip button hitted by user {user.id=}")
            await user_set_next_field_and_send_next_question_or_final(app, user, user.curr_field, message, settings)
            return

        if user.curr_field.branch.is_deferrable and message.text == settings.user_defer_button_plain:
            logger.debug(f"Field defer button hitted by user {user.id=}")
            await user_defer_field(app, user, message, settings)
            return

    # Нажатие на кнопку отмены в контексте изменения поля
    if user.change_field_message_id and message.text == settings.user_or_group_cancel_button_plain:
        logger.debug(f"Change is canceled by user {user.id=}")
        await _user_cancel_change(app, user, message, settings)
        return

    # Изменения поля
    if user.change_field_message_id:
        logger.debug(f"Field value change from user {user.id=}")
        await user_upsert_changed_field_value_and_send_complete(app, user, user.curr_field, message, settings)
        return

    # Полнотекстовое значение поля
    logger.debug(f"Field value from user {user.id=}")
    await user_upsert_field_value_and_send_next_question_or_final(app, user, user.curr_field, message, settings)


async def _user_not_field_context_handlers(
    app: BBApplication, user: User, message: Message, settings: Settings
) -> None:
    """
    Реакция на ситуцию отсутствия у пользователя контекста ответа на поле:
     * Текст - это нажатие на кнопку клавиатуры
     * Отправка файла - вероятно ошбка пользователя, следует ему об этом сообщить
    """
    if message.text:
        logger.debug(f"Keyboard key hit from user {user.id=}")
        await reply_keyboard_key_hit(app, user, message, settings)
        return

    if message.photo or message.document:
        logger.debug(f"File upload from user {user.id=} without field context")
        await message.reply_markdown(
            settings.user_file_upload_without_field_context, reply_markup=await get_user_current_keyboard(app, user)
        )
        return


async def _user_cancel_change(app: BBApplication, user: User, message: Message, settings: Settings) -> None:
    """Пользователь отменил изменение поля"""
    await message.reply_markdown(
        settings.user_field_change_canceled_message_plain,
        reply_markup=await get_user_current_keyboard(app, user),
    )
    async with app.provider.db_sessionmaker() as session:
        await session.execute(
            sql_update(User)
            .where(User.id == user.id)
            .values(curr_field_id=None, change_field_message_id=None, pass_field_change=False)
        )
        await session.commit()
