from telegram import Chat, Message, Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from src.bot.exceptions import (
    CallbackQueryDataIsEmptyError,
    CallbackQueryIsEmptyError,
    CallbackQueryMessageIsEmptyOrInaccesibleError,
    ChatIsEmptyError,
    MessageIsEmptyError,
)
from src.bot.telegram.application import BBApplication
from src.utils.db_model import Settings


async def _get_base_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[BBApplication, Chat, Settings]:
    """
    Получить основные данные Telegram

    Параметры:
    * update: Update - Обновление
    * context: ContextTypes.DEFAULT_TYPE - Контекст

    Возвращает:
    * BBApplication - Экземпляр приложения
    * Chat - Чат
    * Settings - Настройки приложения
    """
    app: BBApplication = context.application  # type: ignore

    if not update.effective_chat:
        raise ChatIsEmptyError

    settings = await app.provider.settings

    return app, update.effective_chat, settings


async def get_base_message_data(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> tuple[BBApplication, Chat, Message, Settings]:
    """
    Получить основные данные Telegram для сообщения

    Параметры:
    * update: Update - Обновление
    * context: ContextTypes.DEFAULT_TYPE - Контекст

    Возвращает:
    * BBApplication - Экземпляр приложения
    * Chat - Чат
    * Message - Сообщение
    * Settings - Настройки приложения
    """
    app, chat, settings = await _get_base_data(update, context)

    if not update.effective_message:
        raise MessageIsEmptyError

    return app, chat, update.effective_message, settings


async def get_base_callback_query_data(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> tuple[BBApplication, Chat, str, Message, Settings]:
    """
    Получить основные данные Telegram для нажатия на inline-кнопку

    Параметры:
    * update: Update - Обновление
    * context: ContextTypes.DEFAULT_TYPE - Контекст

    Возвращает:
    * BBApplication - Экземпляр приложения
    * Chat - Чат
    * str: Данные inline-кнопки
    * Message - Сообщение, для которого пользователь нажал inline-кнопку (т.е. сообщение бота)
    * Settings - Настройки приложения
    """
    app, chat, settings = await _get_base_data(update, context)

    if not update.callback_query:
        raise CallbackQueryIsEmptyError

    await update.callback_query.answer()

    if not update.callback_query.data:
        raise CallbackQueryDataIsEmptyError

    if not update.callback_query.message or not update.callback_query.message.is_accessible:
        raise CallbackQueryMessageIsEmptyOrInaccesibleError

    message = Message.de_json(update.callback_query.message.to_dict(), app.bot)

    if not message:
        raise CallbackQueryMessageIsEmptyOrInaccesibleError

    return app, chat, update.callback_query.data, message, settings


def shrink_text_up_to_80_symbols(text: str | None) -> str:
    """Обрезать сообщение до 80 символов"""
    if not text:
        return ""
    if len(text) > 80:
        return f"{text[:80]}..."
    return text


def get_safe_message_markdown_v1_content(message: Message) -> str:
    """
    Безопасно получить значение текста пользователя

    Используется для того чтобы превратить текст markdown_v2 в markdown_v1
    """
    try:
        text = message.text_markdown_urled
    except Exception:
        text = escape_markdown(message.text if message.text else "")
    return text
