from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

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
        .where(KeyboardKey.status != KeyboardKeyStatusEnum.INACTIVE)
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