from typing import Coroutine, Any
from telegram import (
    Bot,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup
)
from telegram.constants import ParseMode
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio.session import AsyncSession

from bot.application import BBApplication
from utils.db_model import Group, User

async def _get_set_to_all_corutines_sessioned(
        app: BBApplication, table: type[Group|User], selector: ColumnElement[bool],
        session: AsyncSession,
        message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None
    ) -> list[Coroutine[Any, Any, Any]]:
    bot: Bot = app.bot
    selection = await session.execute(
        select(table).where(selector)
    )
    return [
        bot.send_message(chat_id=obj.chat_id, text=message, parse_mode=parse_mode, reply_markup=reply_markup)
        for obj in selection.scalars()
    ]

async def _get_send_to_all_coroutines(
        app: BBApplication, table: type[Group|User], selector: ColumnElement[bool],
        message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None,
        session: AsyncSession | None = None
    ) -> list[Coroutine[Any, Any, Any]]:
    """
    Получить корутины для отправки всем пользователям или группам по заданному селектору
    """
    if session:
        return await _get_set_to_all_corutines_sessioned(
            app=app, table=table, selector=selector,
            session=session,
            message=message, parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    async with app.provider.db_session() as session:
        return await _get_set_to_all_corutines_sessioned(
            app=app, table=table, selector=selector,
            session=session,
            message=message, parse_mode=parse_mode,
            reply_markup=reply_markup
        )

async def send_to_all_coroutines_awaited(
        app: BBApplication, table: type[Group|User], selector: ColumnElement[bool],
        message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None,
        session: AsyncSession | None = None
    ):
    """
    Отправить всем пользователям или группам по заданному селектору с ожиданием
    """
    for coroutine in await _get_send_to_all_coroutines(
        app=app, table=table, selector=selector,
        message=message, parse_mode=parse_mode,
        reply_markup=reply_markup,
        session=session
    ):
        await coroutine

async def send_to_all_coroutines_tasked(
        app: BBApplication, table: type[Group|User], selector: ColumnElement[bool],
        message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None,
        session: AsyncSession | None = None,
        update: dict|None = None
    ):
    """
    Отправить всем пользователям или группам по заданному селектору в виде параллельной задачи
    """
    for coroutine in await _get_send_to_all_coroutines(
        app=app, table=table, selector=selector,
        message=message, parse_mode=parse_mode,
        reply_markup=reply_markup,
        session=session
    ):
        app.create_task(coroutine=coroutine, update=update)