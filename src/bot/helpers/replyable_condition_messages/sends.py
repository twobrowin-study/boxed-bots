from loguru import logger
from sqlalchemy import update
from telegram import Bot, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode

from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.replyable_condition_messages.conditions import (
    select_user_replyable_condition_message_condition,
)
from src.bot.helpers.replyable_condition_messages.keyboards import get_user_reply_condition_message_reply_keyboard
from src.bot.telegram.application import BBApplication
from src.utils.db_model import ReplyableConditionMessage, User


async def send_replyable_condition_message(
    app: BBApplication,
    chat_id: int,
    reply_condition_message: ReplyableConditionMessage,
    text_markdown_override: str | None = None,
    reply_keyboard: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None,
) -> None:
    """
    Отправить сообщение с условием

    Не проверяет никакие условия, отпаравляет сообщение или фото по данным объекта reply_condition_message

    Параметры:
    * app: BBApplication - Приложение
    * chat_id: int - Идентификатор чата для отправки
    * reply_condition_message: ReplyableConditionMessage - Объект сообщения
    * text_markdown_override: str|None = None - Оверрайд текста для отправки (используется для отправки группам)
    * reply_keyboard: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None - клавиатура для отправки
    """
    bot: Bot = app.bot
    text_markdown = text_markdown_override or reply_condition_message.text_markdown

    logger.debug(f"Sending Replyable Condition Message {reply_condition_message.id=} to chat {chat_id=}")

    photo = None
    if reply_condition_message.photo_link:
        photo = reply_condition_message.photo_link
    elif reply_condition_message.photo_file_id:
        photo = reply_condition_message.photo_file_id
    elif reply_condition_message.photo_bucket and reply_condition_message.photo_filename:
        photo, _ = await app.provider.minio.download(
            reply_condition_message.photo_bucket, reply_condition_message.photo_filename
        )

    photo_message = None
    if photo and len(text_markdown) <= 1024:
        photo_message = await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=text_markdown,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_keyboard,
        )

    if photo and len(text_markdown) > 1024:
        photo_message = await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
        )
        await bot.send_message(
            chat_id=chat_id,
            text=text_markdown,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_keyboard,
        )

    if not photo:
        await bot.send_message(
            chat_id=chat_id,
            text=text_markdown,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_keyboard,
        )

    if photo_message and photo_message.photo and not reply_condition_message.photo_file_id:
        async with app.provider.db_sessionmaker() as session:
            await session.execute(
                update(ReplyableConditionMessage)
                .where(ReplyableConditionMessage.id == reply_condition_message.id)
                .values(photo_file_id=photo_message.photo[-1].file_id)
            )
            await session.commit()


async def send_replyable_condition_message_to_user(
    app: BBApplication,
    user: User,
    reply_condition_message: ReplyableConditionMessage,
) -> None:
    """
    Отправить пользователю сообщение с условием

    Вычисляет условие отправки и отправляемую клавиатуру для пользователя или подставляет текущую клавиатуру пользователя

    Параметры:
    * app: BBApplication - Приложение
    * user: User - Объект пользователя
    * reply_condition_message: ReplyableConditionMessage - Объект сообщения
    """
    if reply_condition_message.condition_bool_field:
        async with app.provider.db_sessionmaker() as session:
            condition = await session.scalar(
                select_user_replyable_condition_message_condition(user, reply_condition_message)
            )
            if condition is None:
                logger.debug(f"User {user.id=} cannot get Replyable Condition Message {reply_condition_message.id=}")
                return

    reply_keyboard = await get_user_reply_condition_message_reply_keyboard(app, user, reply_condition_message)
    if not reply_keyboard:
        reply_keyboard = await get_user_current_keyboard(app, user)

    logger.debug(f"Sending Replyable Condition Message {reply_condition_message.id=} to user {user.id=}")

    await send_replyable_condition_message(app, user.chat_id, reply_condition_message, reply_keyboard=reply_keyboard)
