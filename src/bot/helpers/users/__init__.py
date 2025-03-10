from loguru import logger
from sqlalchemy import select
from telegram import Chat, Message, Update
from telegram import User as TelegramUser
from telegram.ext import ContextTypes

from src.bot.exceptions import TelegramUserNotFoundError, UserNotFoundError
from src.bot.helpers.telegram import get_base_callback_query_data, get_base_message_data
from src.bot.telegram.application import BBApplication
from src.utils.db_model import Settings, User


async def get_user_message_data_send_strange_error_and_rise(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    handler: str,
) -> tuple[BBApplication, User, Message, Settings]:
    """
    Получить данные пользователя для сообщения или ответить странной ошибкой и вернуть ошибку если пользователь не найден

    Параметры:
     * update: Update - Обновление
     * context: ContextTypes.DEFAULT_TYPE - Контекст
     * handler: str - Название обработчика для логов

    Возвращает:
     * BBApplication - Приложение
     * User - Пользователь
     * Chat - Чат
     * Message - Сообщение
     * TelegramUser - Пользователь Telegram
     * Settings - Настройки приложения
    """
    app, user, _, message, _, settings = await get_user_message_data_return_none(update, context, handler)
    user = await _raise_for_none_user(user, message, settings)
    return app, user, message, settings


async def get_user_message_data_return_none(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    handler: str,
) -> tuple[BBApplication, User | None, Chat, Message, TelegramUser, Settings]:
    """
    Получить данные пользователя для сообщения


    Параметры:
     * update: Update - Обновление
     * context: ContextTypes.DEFAULT_TYPE - Контекст
     * handler: str - Название обработчика для логов

    Возвращает:
     * BBApplication - Приложение
     * User | None - Пользователь (None если action_not_found="return_none" и пользователь не найден)
     * Chat - Чат
     * Message - Сообщение
     * TelegramUser - Пользователь Telegram
     * Settings - Настройки приложения
    """
    app, chat, message, settings = await get_base_message_data(update, context)

    if not update.effective_user:
        raise TelegramUserNotFoundError

    user = await _get_user_by_chat(app, chat, handler)

    return app, user, chat, message, update.effective_user, settings


async def get_user_callback_query_data_send_strange_error_and_rise(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    handler: str,
) -> tuple[BBApplication, User, str, Message, Settings]:
    """
    Получить данные пользователя для ответа на нажатие inline-кнопки или ответить странной ошибкой и вернуть ошибку если пользователь не найден

    Параметры:
     * update: Update - Обновление
     * context: ContextTypes.DEFAULT_TYPE - Контекст
     * handler: str - Название обработчика для логов

    Возвращает:
     * BBApplication - Приложение
     * User - Пользователь
     * str - Данные нажатой inline-кнопки
     * Message - Сообщение, для которого пользователь нажал inline-кнопку (т.е. сообщение бота)
     * Settings - Настройки приложения
    """
    app, chat, callback_query_data, callback_query_message, settings = await get_base_callback_query_data(
        update, context
    )

    user = await _get_user_by_chat(app, chat, handler)
    user = await _raise_for_none_user(user, callback_query_message, settings)

    return app, user, callback_query_data, callback_query_message, settings


async def _get_user_by_chat(app: BBApplication, chat: Chat, handler: str) -> User | None:
    """Найти пользователя по чату"""

    async with app.provider.db_sessionmaker() as session:
        user = await session.scalar(select(User).where(User.chat_id == chat.id).limit(1))

    if not user:
        logger.debug(f"Got {handler} from unknown user {chat.id=}")
    else:
        logger.debug(f"Got {handler} from user {user.id=}")

    return user


async def _raise_for_none_user(user: User | None, message: Message, settings: Settings) -> User:
    """Вызвать ошибку о ненайденном пользователе и отправить странную ошибку"""
    if not user:
        await message.reply_markdown(settings.user_strange_error_massage_plain)
        raise UserNotFoundError
    return user
