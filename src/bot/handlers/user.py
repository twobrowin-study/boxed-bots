from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from sqlalchemy import select, insert, update as sql_udate

from loguru import logger

from utils.db_model import (
    User, Field,
    UserFieldValue
)

from bot.application import BBApplication

from bot.helpers.user import (
    get_user_by_chat_id_or_none,
    parse_start_help_commands_and_answer,
    create_new_user_and_answer,
    update_user_over_next_question_answer_and_get_curr_field,
    answer_to_user_keyboard_key_hit,
    user_change_field_and_answer,
    upload_telegram_file_to_minio_and_return_filename
)
from bot.helpers.keyboards import (
    construct_keyboard_reply
)

from bot.callback_constants import UserChangeFieldCallback

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
        
        if user.change_field_message_id:
            user_change_err = await user_change_field_and_answer(update, context, user, settings, session, message_type)
            if user_change_err:
                return
            return await session.commit()

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
        
        if user.change_field_message_id:
            user_change_err = await user_change_field_and_answer(update, context, user, settings, session, message_type)
            if user_change_err:
                return
            return await session.commit()
        
        user_curr_field = await update_user_over_next_question_answer_and_get_curr_field(update, context, user, settings, session, message_type)
        if user_curr_field:
            
            full_filename = await upload_telegram_file_to_minio_and_return_filename(update, context, user, user_curr_field, settings, session)

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

async def user_change_state_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает нажатие на кнопку изменения поля на инлайн клавиатуре
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    await update.callback_query.answer()

    changing_field_id = int(update.callback_query.data.removeprefix(UserChangeFieldCallback.PREFIX))

    logger.info(f"Got change field callback from user {chat_id=} {username=} for field {changing_field_id=}")

    async with app.provider.db_session() as session:
        user = await get_user_by_chat_id_or_none(session, chat_id)

        if not user:
            return logger.warning(f"Got change field callback from unknown user {chat_id=} {username=} for field {changing_field_id=}")

        changing_field_selected = await session.execute(
            select(Field)
            .where(Field.id == changing_field_id)
        )
        changing_field = changing_field_selected.scalar_one_or_none()

        if not changing_field:
            return logger.warning(f"Got change field callback from user {chat_id=} {username=} for unknown field {changing_field_id=}")
        
        await update.effective_message.reply_markdown(
            text = changing_field.question_markdown,
            reply_markup = construct_keyboard_reply(changing_field.answer_options)
        )

        await session.execute(
            sql_udate(User)
            .where(User.id == user.id)
            .values(
                curr_field_id = changing_field.id,
                change_field_message_id = update.effective_message.id
            )
        )

        await session.commit()