from typing import Coroutine, Any
from telegram import (
    Bot,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup
)
from telegram.constants import ParseMode

from sqlalchemy.orm import aliased
from sqlalchemy import (
    ColumnElement,
    select
)
from sqlalchemy.ext.asyncio.session import AsyncSession

from utils.db_model import (
    Group, User,
    Field, UserFieldValue,
    KeyboardKey, Settings
)
from utils.custom_types import (
    FieldStatusEnum,
    KeyboardKeyStatusEnum
)

from bot.application import BBApplication

async def _get_send_to_all_coroutines(
        app: BBApplication, table: type[Group|User], selector: ColumnElement[bool],
        message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None
    ) -> list[Coroutine[Any, Any, Any]]:
    """
    Получить корутины для отправки всем пользователям или группам по заданному селектору
    """
    async with app.provider.db_session() as session:
        bot: Bot = app.bot
        selection = await session.execute(
            select(table).where(selector)
        )
        corotines = []
        for obj in selection.scalars().all():
            corotines.append(
                bot.send_message(chat_id=obj.chat_id, text=message, parse_mode=parse_mode, reply_markup=reply_markup)
            )
        return corotines

async def send_to_all_coroutines_awaited(
        app: BBApplication, table: type[Group|User], selector: ColumnElement[bool],
        message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None
    ):
    """
    Отправить всем пользователям или группам по заданному селектору с ожиданием
    """
    for coroutine in await _get_send_to_all_coroutines(
        app=app, table=table, selector=selector,
        message=message, parse_mode=parse_mode,
        reply_markup=reply_markup
    ):
        await coroutine

async def send_to_all_coroutines_tasked(
        app: BBApplication, table: type[Group|User], selector: ColumnElement[bool],
        message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None,
        update: dict|None = None
    ):
    """
    Отправить всем пользователям или группам по заданному селектору в виде параллельной задачи
    """
    for coroutine in await _get_send_to_all_coroutines(
        app=app, table=table, selector=selector,
        message=message, parse_mode=parse_mode,
        reply_markup=reply_markup
    ):
        app.create_task(coroutine=coroutine, update=update)

def construct_keyboard_reply(reply_str: str|None) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if reply_str in [None, '']:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup([
        [key] for key in reply_str.split('\n')
    ])

async def get_keyboard_to_user(session: AsyncSession, _: User) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
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

async def get_keyboard_key_obj_by_key_text(session: AsyncSession, key: str) -> KeyboardKey | None:
    selected = await session.execute(
        select(KeyboardKey)
        .where(KeyboardKey.key == key)
    )
    return selected.scalar_one_or_none()

async def get_first_user_field_question(session: AsyncSession, settings: Settings) -> Field:
    """
    Получить первое пользовательское поле, который нужно задать пользователю при регистрации
    """
    selected = await session.execute(
        select(Field)
        .where(Field.branch == settings.first_field_branch)
        .order_by(Field.id.asc())
        .limit(1)
    )
    return selected.scalar_one()

async def get_user_field_value_by_key(session: AsyncSession, user: User, key: str) -> str|None:
    """
    Получить значение пользовательских полей по заданному ключу
    """
    selected = await session.execute(
        select(UserFieldValue.value)
        .where(
            (Field.key == key) &
            (UserFieldValue.field_id == Field.id) &
            (UserFieldValue.user_id  == user.id)
        )
        .limit(1)
    )
    return selected.scalar_one_or_none()

async def get_next_field_question_in_branch(session: AsyncSession, curr_field: Field) -> Field|None:
    """
    Получить следующий вопрос в той же ветке
    """
    selected = await session.execute(
        select(Field)
        .where(
            (Field.branch == curr_field.branch) &
            (Field.id > curr_field.id) &
            (Field.status != FieldStatusEnum.INACTIVE)
        )
        .order_by(Field.id.asc())
        .limit(1)
    )
    return selected.scalar_one_or_none()