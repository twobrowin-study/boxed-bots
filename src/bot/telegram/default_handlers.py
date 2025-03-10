import html
import json
import traceback

from loguru import logger
from sqlalchemy import select
from sqlalchemy import update as sql_update
from telegram import Bot, Chat, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.bot.exceptions import ChatMemberIsEmptyError, UserNotFoundError
from src.bot.helpers.telegram import get_base_message_data
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import GroupStatusEnum
from src.utils.db_model import Group, User


async def service_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Единый обработчик событий, используемый в сервисном режиме
    """
    _, _, message, settings = await get_base_message_data(update, context)
    await message.reply_markdown(settings.user_service_mode_message_plain)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик ошибки:

    * Возвращает пользователю сообщение об ошибке

    * Отправляет сообщение об ошибке во все группы суперадминистраторов
    """
    app: BBApplication = context.application  # type: ignore
    bot: Bot = app.bot
    settings = await app.provider.settings

    if type(context.error) is UserNotFoundError:
        return

    try:
        if (
            type(update) is Update
            and update.effective_chat
            and update.effective_chat.type in [Chat.PRIVATE, Chat.GROUP, Chat.SUPERGROUP]
        ):
            bot: Bot = context.bot
            if update.effective_chat:
                await bot.send_message(
                    update.effective_chat.id,
                    settings.user_error_message_plain,
                    parse_mode=ParseMode.MARKDOWN,
                )
    except Exception:
        logger.error("Was not able to retrun user error message")

    if not context.error:
        logger.error("Context error is empty")
        return

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    logger.error(f"Exception while handling an update:\n{tb_string}")
    await _send_error_message_to_superadmins(app, update, context, tb_string)


async def _send_error_message_to_superadmins(
    app: BBApplication,
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
    tb_string: str,
) -> None:
    bot: Bot = app.bot
    update_str = update.to_dict() if isinstance(update, Update) else update if isinstance(update, dict) else str(update)
    messages_parts = [
        "An exception was raised while handling an update",
        f"update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}",
        f"context.chat_data = {html.escape(str(context.chat_data))}",
        f"context.user_data = {html.escape(str(context.user_data))}",
        f"{html.escape(tb_string)}",
    ]
    messages = []
    for idx, message_part in enumerate(messages_parts):
        curr_len = len(message_part)
        template = "<pre>{message_part}</pre>\n\n" if idx > 0 else "{message_part}\n"
        if len(messages) > 0 and (len(messages[-1]) + curr_len <= 4096):
            messages[-1] += template.format(message_part=message_part)
        elif curr_len <= 4096:
            messages.append(template.format(message_part=message_part))
        else:
            messages += [
                template.format(message_part=message_part[idx : idx + 4096]) for idx in range(0, curr_len, 4096)
            ]

    async with app.provider.db_sessionmaker() as session:
        admin_groups = await session.scalars(select(Group).where(Group.status == GroupStatusEnum.SUPER_ADMIN))
    for admin_group in admin_groups:
        for message in messages:
            await bot.send_message(chat_id=admin_group.chat_id, text=message, parse_mode=ParseMode.HTML)


async def chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик событий изменения причастности бота к чатам (группам или приватным)

    Для приватных чатов устанавливает статус бана бота для пользователя
    """
    app, chat, _, _ = await get_base_message_data(update, context)

    if not update.my_chat_member:
        raise ChatMemberIsEmptyError

    logger.debug(f"Chat member event \n{update.my_chat_member=}\n")

    message = None
    if chat.type in [Chat.GROUP, Chat.SUPERGROUP, Chat.CHANNEL]:
        message = (
            f"{update.my_chat_member.new_chat_member.status.title()} event in "
            f"{chat.type} with title `{chat.title}` id `{chat.id}`"
        )

    elif chat.type == Chat.PRIVATE:
        user_ban_status = None
        if update.my_chat_member.new_chat_member.status == update.my_chat_member.new_chat_member.BANNED:
            user_ban_status = True
            message = f"I was banned by private user `{chat.id=}`"

        elif update.my_chat_member.new_chat_member.status == update.my_chat_member.new_chat_member.MEMBER:
            user_ban_status = False
            message = f"I was unbanned by private user `{chat.id=}`"

        if user_ban_status is not None:
            async with app.provider.db_sessionmaker() as session:
                await session.execute(
                    sql_update(User).where(User.chat_id == chat.id).values(have_banned_bot=user_ban_status)
                )
                await session.commit()

    if message:
        logger.debug(message)
        await app.write_log(message)

    logger.debug(f"Other chat member event in {chat.type=} {chat.id=}")


async def eddited_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик изменённых сообщений - вовращает стандартную ошибку
    """
    if update.edited_channel_post:
        logger.warning("Got eddited channel post... ignoring")
        return
    _, chat, message, settings = await get_base_message_data(update, context)
    logger.warning(f"Got eddited message request from {chat.id=}")
    await message.reply_markdown(settings.user_message_edited_reply_message_plain)
