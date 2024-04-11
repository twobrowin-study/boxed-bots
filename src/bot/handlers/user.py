from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from sqlalchemy import insert, update as sql_udate

from loguru import logger

from io import BytesIO

from utils.db_model import (
    UserFieldValue
)

from bot.application import BBApplication

from bot.helpers.user import (
    get_user_by_chat_id_or_none,
    parse_start_help_commands_and_answer,
    create_new_user_and_answer,
    update_user_over_next_question_answer_and_get_curr_field
)
from bot.helpers.fields import (
    get_user_field_value_by_key,
)
from bot.helpers.keyboards import (
    answer_to_user_keyboard_key_hit
)

# CALLBACK_USER_SET_INACTIVE         = 'user_set_inactive'
# CALLBACK_USER_SET_ACTIVE           = 'user_set_active'
# CALLBACK_USER_ACTIVE_STATE_PATTERN = 'user_set_(in|)active'

# CALLBACK_USER_CHANGE_STATE_PREFIX   = 'user_change_'
# CALLBACK_USER_CHANGE_STATE_TEMPLATE = 'user_change_{state}'
# CALLBACK_USER_CHANGE_STATE_PATTERN  = 'user_change_.*'

async def user_start_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команд старта или помощи пользователя
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    async with app.provider.db_session() as session:
        user       = await get_user_by_chat_id_or_none(session, chat_id)
        settings   = await app.provider.get_settings(session)
        bot_status = await app.provider.get_bot_status(session)

        if not user and bot_status.is_registration_open == False:
            logger.warning(f"Got start/help command from new user {chat_id=} and {username=}, but registration is complete")
            return await update.message.reply_markdown(settings.registration_is_over)
        
        if not user:
            await create_new_user_and_answer(update, context, settings, session)
            return await session.commit()
        
        return await parse_start_help_commands_and_answer(update, context, user, settings, session)

async def user_message_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик текстовых сообщений пользователя
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    message_type = 'text'

    async with app.provider.db_session() as session:
        user     = await get_user_by_chat_id_or_none(session, chat_id)
        settings = await app.provider.get_settings(session)

        if not user:
            logger.warning(f"Got {message_type} message from unknown user {chat_id=} and {username=}... strange error")
            return await update.message.reply_markdown(settings.strange_user_error)

        user_curr_field = await update_user_over_next_question_answer_and_get_curr_field(update, context, user, settings, session, message_type)
        if user_curr_field:
            await session.execute(
                insert(UserFieldValue)
                .values(
                    user_id    = user.id,
                    field_id   = user_curr_field.id,
                    value      = update.message.text_markdown_urled,
                    message_id = update.message.id
                )
            )
            return await session.commit()

        if await answer_to_user_keyboard_key_hit(update, context, user, session):
            return

        logger.warning(f"Got unknown text message from user {chat_id=} and {username=}")

async def user_message_photo_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик сообщений пользователя с фото или документом
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    message_type = 'photo/document'

    async with app.provider.db_session() as session:
        user     = await get_user_by_chat_id_or_none(session, chat_id)
        settings = await app.provider.get_settings(session)

        if not user:
            logger.warning(f"Got {message_type} from unknown user {chat_id=} and {username=}... strange error")
            return await update.message.reply_markdown(settings.strange_user_error)
        
        user_curr_field = await update_user_over_next_question_answer_and_get_curr_field(update, context, user, settings, session, message_type)
        if user_curr_field:

            if update.message.document:
                file = await update.message.document.get_file()
            elif update.message.photo:
                file = await update.message.photo[-1].get_file()

            in_memory = BytesIO()
            await file.download_to_memory(in_memory)
            
            saved_filename = await get_user_field_value_by_key(session, user, settings.user_document_name_field)

            bucket = user_curr_field.document_bucket or user_curr_field.image_bucket

            full_filename = await app.provider.minio.upload_with_thumbnail_and_return_filename(
                bucket                = bucket,
                filename_wo_extension = saved_filename,
                bio                   = in_memory
            )

            await session.execute(
                insert(UserFieldValue)
                .values(
                    user_id    = user.id,
                    field_id   = user_curr_field.id,
                    value      = full_filename,
                    message_id = update.message.id
                )
            )
            
            return await session.commit()
        
        logger.warning(f"Got unknown message from user {chat_id=} and {username=}")