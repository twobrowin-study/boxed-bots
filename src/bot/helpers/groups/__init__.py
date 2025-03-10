import io

from loguru import logger
from sqlalchemy import select
from telegram import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from src.bot.exceptions import GroupNotFoundError, GroupPassesNoDocumentError
from src.bot.helpers.telegram import get_base_message_data
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import GroupStatusEnum
from src.utils.db_model import Group, Settings


async def get_group_message_data(
    update: Update, context: ContextTypes.DEFAULT_TYPE, handler: str
) -> tuple[BBApplication, Group, Message, Settings]:
    """
    Получить данные группы

    Параметры:
     * update: Update - Обновление
     * context: ContextTypes.DEFAULT_TYPE - Контекст
     * handler: str - Название обработчика для логов

    Возвращает:
     * BBApplication - Приложение
     * Group - Группа
     * Message - Сообщение
     * Settings - Настройки приложения
    """

    app, chat, message, settings = await get_base_message_data(update, context)

    async with app.provider.db_sessionmaker() as session:
        group = await session.scalar(
            select(Group).where(Group.chat_id == chat.id).where(Group.status != GroupStatusEnum.INACTIVE).limit(1)
        )

    if not group:
        logger.warning(f"Got {handler} from unknown group {chat.id=}")
        raise GroupNotFoundError

    logger.debug(f"Got {handler} from group {group.chat_id=} as {group.status=}")

    return app, group, message, settings


def get_group_default_keyboard(group: Group, settings: Settings) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """
    Получить стандартную клавиатуру группы

    Если группа имеет право на управление пропусками, то ей возвращается соответствующие кнопки
    """
    if group.pass_management:
        return ReplyKeyboardMarkup(
            [
                [settings.group_superadmin_pass_download_submited_button_plain],
                [settings.group_superadmin_pass_send_approved_button_plain],
            ]
        )
    return ReplyKeyboardRemove()


def get_group_cancel_keyboard(settings: Settings) -> ReplyKeyboardMarkup:
    """Клавиатура для отмена действий"""
    return ReplyKeyboardMarkup(
        [
            [settings.user_or_group_cancel_button_plain],
        ]
    )


async def group_passes_download_document(message: Message) -> io.BytesIO:
    """Выкачать документ пропусков"""
    if not message.document:
        raise GroupPassesNoDocumentError
    file = await message.document.get_file()
    bio = io.BytesIO()
    await file.download_to_memory(bio)
    bio.seek(0)
    return bio
