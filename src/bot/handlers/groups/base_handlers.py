from jinja2 import Template
from loguru import logger
from sqlalchemy import insert, select
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.bot.helpers.groups import get_group_default_keyboard, get_group_message_data
from src.utils.custom_types import GroupStatusEnum
from src.utils.db_model import NewsPost, User


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды помощи для группы
    """
    _, group, message, settings = await get_group_message_data(update, context, "start/help command")

    reply_markup = get_group_default_keyboard(group, settings)

    if group.status == GroupStatusEnum.NORMAL:
        await message.reply_markdown(
            settings.group_normal_help_message_plain,
            reply_markup=reply_markup,
        )
        return ConversationHandler.END

    if group.status == GroupStatusEnum.ADMIN:
        await message.reply_markdown(
            settings.group_admin_help_message_plain,
            reply_markup=reply_markup,
        )
        return ConversationHandler.END

    if group.status == GroupStatusEnum.SUPER_ADMIN:
        await message.reply_markdown(
            settings.group_superadmin_help_message_plain,
            reply_markup=reply_markup,
        )
        return ConversationHandler.END

    return ConversationHandler.END


async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды на получение отчёта для групп администраторов или суперадминистраторов
    """
    app, group, message, settings = await get_group_message_data(update, context, "report command")

    if not group or group.status not in [
        GroupStatusEnum.ADMIN,
        GroupStatusEnum.SUPER_ADMIN,
    ]:
        logger.debug(f"Got report command from group {group.chat_id=} as {group.status=}... ignoring")
        return

    async with app.provider.db_sessionmaker() as session:
        users = [user.to_plain_dict() for user in await session.scalars(select(User))]

    await message.reply_markdown(
        await Template(settings.group_admin_status_report_message_j2_template, enable_async=True).render_async(
            users=users
        )
    )


async def channel_publication_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик публикации в канале новостей
    """
    app, group, message, _ = await get_group_message_data(update, context, "publication")

    if group.status != GroupStatusEnum.NEWS_CHANNEL:
        logger.warning(f"Got publication from group {group.chat_id=} as {group.status=}... ignoring")
        return

    if message.text is None and message.caption is None:
        logger.warning(
            f"Got publication from group {group.chat_id=} as {group.status=} without text, so it is propably is on of previuos post photo... ignoring"
        )
        return

    text = ""
    if message.text:
        text = message.text
    if message.caption:
        text = message.caption
    tags = " ".join(filter(lambda s: s.startswith("#"), text.split()))

    message_id = message.id
    async with app.provider.db_sessionmaker() as session:
        await session.execute(insert(NewsPost).values(chat_id=group.chat_id, message_id=message_id, tags=tags))
        await session.commit()
        logger.debug(f"Added new news publication from {group.chat_id=} with {message_id=}")
        return
