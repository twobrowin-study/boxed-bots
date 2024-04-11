from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from sqlalchemy import select

from loguru import logger

from utils.db_model import Group
from utils.custom_types import GroupStatusEnum

from bot.application import BBApplication
from bot.helpers.send_to_all import (
    send_to_all_coroutines_awaited,
    send_to_all_coroutines_tasked
)

async def group_send_to_all_superadmin_awaited(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем суперадминам с ожиданием окончания отправки
    """
    await send_to_all_coroutines_awaited(
        app=app, table=Group,
        selector=(Group.status == GroupStatusEnum.SUPER_ADMIN),
        message=message, parse_mode=parse_mode
    )

async def group_send_to_all_superadmin_tasked(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем суперадминам в виде параллельной задачи
    """
    await send_to_all_coroutines_tasked(
        app=app, table=Group,
        selector=(Group.status == GroupStatusEnum.SUPER_ADMIN),
        message=message, parse_mode=parse_mode,
        update={'update': 'group_send_to_all_superadmins_tasked', 'message': message}
    )

async def group_send_to_all_admin_tasked(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем админам и суперадминам в виде параллельной задачи
    """
    await send_to_all_coroutines_tasked(
        app=app, table=Group,
        selector=((Group.status == GroupStatusEnum.ADMIN) | (Group.status == GroupStatusEnum.SUPER_ADMIN)) ,
        message=message, parse_mode=parse_mode,
        update={'update': 'group_send_to_all_admins_tasked', 'message': message}
    )

async def group_send_to_all_normal_tasked(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем обычным группам в виде параллельно задачи
    """
    await send_to_all_coroutines_tasked(
        app=app, table=Group,
        selector=(Group.status == GroupStatusEnum.NORMAL),
        message=message, parse_mode=parse_mode,
        update={'update': 'group_send_to_all_normal_tasked', 'message': message}
    )

async def _get_group_by_chat_id_or_none(app: BBApplication, chat_id: int) -> Group|None:
    """
    Найти группу по заданносу ИД чата
    """
    async with app.provider.db_session() as session:
        selected = await session.execute(
            select(Group)
            .where(
                (Group.chat_id == chat_id) &
                (Group.status  != GroupStatusEnum.INACTIVE)
            )
            .limit(1)
        )
        return selected.scalar_one_or_none()

async def group_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды помощи для группы
    """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)
    if not group:
        return logger.info(f"Got start/help command from unknown group {chat_id=} and {group_name=}")

    settings = await app.provider.settings

    logger.info(f"Got start/help command from group {chat_id=} and {group_name=} as {group.status=}")
    
    if group.status == GroupStatusEnum.NORMAL:
        return await update.message.reply_markdown(settings.help_normal_group)
    
    if group.status == GroupStatusEnum.ADMIN:
        return await update.message.reply_markdown(settings.help_admin_group)
    
    if group.status == GroupStatusEnum.SUPER_ADMIN:
        return await update.message.reply_markdown(settings.help_superadmin_group)

async def group_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды на получение отчёта для групп администраторов или суперадминистраторов
    """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)

    if not group:
        return logger.info(f"Got report command from unknown group {chat_id=} and {group_name=}")
    
    if not group or group.status not in [GroupStatusEnum.ADMIN, GroupStatusEnum.SUPER_ADMIN]:
        return logger.info(f"Got report command from group {chat_id=} and {group_name=} as {group.status=}... ignoring")
    
    logger.info(f"Got report command from group {chat_id=} and {group_name=} as {group.status=}")
    
    await update.message.reply_markdown("Here will be kinda report")