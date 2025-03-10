import io
from typing import Literal

from telegram import Bot
from telegram.constants import ParseMode

from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.telegram.application import BBApplication
from src.utils.db_model import User


async def send_message_and_return_file_id(
    app: BBApplication,
    user: User,
    text: str | None,
    file: str | io.BytesIO | None,
    file_type: Literal["image", "document"] | None,
    filename: str | None,
) -> str | None:
    bot: Bot = app.bot
    reply_keyboard = await get_user_current_keyboard(app, user)
    if not file_type or not file:
        await bot.send_message(
            user.chat_id,
            text if text else "",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_keyboard,
        )
        return None

    if file_type == "image":
        send_message = await bot.send_photo(
            user.chat_id,
            file,
            filename=filename,
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_keyboard,
        )
        return send_message.photo[-1].file_id if send_message.photo else None

    if file_type == "document":
        send_message = await bot.send_document(
            user.chat_id,
            file,
            filename=filename,
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_keyboard,
        )
        return send_message.document.file_id if send_message.document else None

    return None
