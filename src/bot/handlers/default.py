import traceback
import html
import json

from telegram import Bot, Update, Chat
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.application import BBApplication
from bot.handlers.group import group_send_to_all_superadmin_awaited
from bot.helpers.user import user_set_have_banned_bot

from loguru import logger

async def service_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Единый обработчик событий, используемый в сервисном режиме
    """
    app: BBApplication = context.application
    settings = await app.provider.settings
    await update.message.reply_markdown(settings.service_mode_message)

async def error_handler(update: Update|dict, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик ошибки:

    * Возвращает пользователю сообщение об ошибке

    * Отправляет сообщение об ошибке во все группы суперадминистраторов
    """
    app: BBApplication = context.application
    settings = await app.provider.settings

    try:
        if isinstance(update, Update):
            bot: Bot = context.bot
            await bot.send_message(update.effective_chat.id, settings.error_reply, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        logger.error("Was not able to retrun user error message")

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    logger.error(f"Exception while handling an update:\n{tb_string}")

    update_str = update.to_dict() if isinstance(update, Update) else update if isinstance(update, dict) else str(update)
    messages_parts = [
        f"An exception was raised while handling an update",
        f"update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}",
        f"context.chat_data = {html.escape(str(context.chat_data))}",
        f"context.user_data = {html.escape(str(context.user_data))}",
        f"{html.escape(tb_string)}",
    ]
    messages = []
    for idx,message_part in enumerate(messages_parts):
        curr_len = len(message_part)
        template = "<pre>{message_part}</pre>\n\n" if idx > 0 else "{message_part}\n"
        if len(messages) > 0 and (len(messages[-1]) + curr_len <= 4096):
            messages[-1] += template.format(message_part=message_part)
        elif curr_len <= 4096:
            messages.append(template.format(message_part=message_part))
        else:
            for idx in range(0,curr_len,4096):
                messages.append(template.format(message_part=message_part[idx:idx+4096]))

    for message in messages:
        await group_send_to_all_superadmin_awaited(app, message,  ParseMode.HTML)

async def chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик событий изменения причастности бота к чатам (группам или приватным)

    Для приватных чатов устанавливает статус бана бота для пользователя
    """
    app: BBApplication = context.application

    logger.debug(f"Chat member event \n{update.my_chat_member}\n")
    if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP, Chat.CHANNEL]:
        message = (
            f"{update.my_chat_member.new_chat_member['status'].title()} event in "
            f"{update.effective_chat.type} with title `{update.effective_chat.title}` id `{update.effective_chat.id}`"
        )
        logger.info(message)
        await app.write_log(message)
        return
    
    elif update.effective_chat.type == Chat.PRIVATE:
        if update.my_chat_member.new_chat_member['status'] == update.my_chat_member.new_chat_member.BANNED:
            await user_set_have_banned_bot(app, update.effective_chat.id, have_banned_bot=True)
            message = f"I was banned by private user `{update.effective_chat.id}`"
            logger.info(message)
            await app.write_log(message)
            return
        
        elif update.my_chat_member.new_chat_member['status'] == update.my_chat_member.new_chat_member.MEMBER:
            await user_set_have_banned_bot(app, update.effective_chat.id, have_banned_bot=False)
            message = f"I was unbanned by private user `{update.effective_chat.id}`"
            logger.info(message)
            await app.write_log(message)
            return
    logger.info(f"Other chat member event in {update.effective_chat.type} {update.effective_chat.id}")

async def eddited_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик изменённых сообщений - вовращает стандартную ошибку
    """
    app: BBApplication = context.application
    settings = await app.provider.settings
    await update.effective_message.reply_markdown(settings.edited_message_reply)