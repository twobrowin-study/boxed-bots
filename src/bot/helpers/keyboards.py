from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from utils.db_model import User, KeyboardKey
from utils.custom_types import KeyboardKeyStatusEnum

def construct_keyboard_reply(reply_str: str|None) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """
    Получить клавиатуру по строке вариантов ответов
    """
    if reply_str in [None, '']:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup([
        [key] for key in reply_str.split('\n')
    ])

async def get_keyboard_of_user(session: AsyncSession, _: User) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """
    Получить клавиатуру, доступную пользователю
    """
    selected = await session.execute(
        select(KeyboardKey)
        .where(
            (KeyboardKey.status == KeyboardKeyStatusEnum.NORMAL) |
            (
                (KeyboardKey.status in [KeyboardKeyStatusEnum.ME, KeyboardKeyStatusEnum.DEFERRED]) &
                (KeyboardKey.branch_id is not None)
            )
        )
    )
    keyboard_keys     = selected.all()
    keyboard_keys_len = len(keyboard_keys)
    if keyboard_keys_len == 0:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        [
            [ key.t[0].key for key in keyboard_keys[idx:idx+2] ]
            for idx in range(0,keyboard_keys_len,2)
        ] if keyboard_keys_len > 2 \
            else [
                [ key.t[0].key ] for key in keyboard_keys
            ]
    )

async def get_keyboard_key_by_key_text(session: AsyncSession, key: str) -> KeyboardKey | None:
    """
    Получить полный объект кнопки клавиатуры по названию клавиши
    """
    selected = await session.execute(
        select(KeyboardKey)
        .where(KeyboardKey.key == key)
    )
    return selected.scalar_one_or_none()

async def answer_to_user_keyboard_key_hit(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, session: AsyncSession) -> bool:
    """
    Отвечает на пользовательский запрос на кнопку клавиатуры
    """
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    keyboard_key = await get_keyboard_key_by_key_text(session, update.message.text)
    
    if not keyboard_key:
        return False
    
    logger.info(f"Got keyboard key heat from user {chat_id=} and {username=} {keyboard_key.key=}")

    if keyboard_key.status == KeyboardKeyStatusEnum.ME:
        print(user.to_dict())

    if keyboard_key.photo_link in [None, '']:
        return await update.message.reply_markdown(
            keyboard_key.text_markdown,
            reply_markup = await get_keyboard_of_user(session, user)
        )
    elif keyboard_key.photo_link not in [None, ''] and len(keyboard_key.text_markdown) <= 1024:
        return await update.message.reply_photo(
            keyboard_key.photo_link,
            caption = keyboard_key.text_markdown,
            reply_markup = await get_keyboard_of_user(session, user),
            parse_mode = ParseMode.MARKDOWN
        )
    elif keyboard_key.photo_link not in [None, ''] and len(keyboard_key.text_markdown) > 1024:
        await update.message.reply_photo(keyboard_key.photo_link)
        return await update.message.reply_markdown(
            keyboard_key.text_markdown,
            reply_markup = await get_keyboard_of_user(session, user)
        )
    
    return True
    