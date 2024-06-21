from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from sqlalchemy import select, update as sql_udate

from loguru import logger

from utils.db_model import (
    User, Field,
    FieldBranch,
    ReplyableConditionMessage
)

from bot.application import BBApplication

from bot.helpers.user import (
    get_user_by_chat_id_or_none,
    parse_start_help_commands_and_answer,
    create_new_user_and_answer,
    update_user_over_next_question_answer_and_get_curr_field,
    answer_to_user_keyboard_key_hit,
    user_change_field_and_answer,
    upload_telegram_file_to_minio_and_return_filename,
    get_field_question_by_branch,
    insert_or_update_user_field_value
)
from bot.helpers.keyboards import (
    construct_keyboard_reply,
    get_keyboard_of_user
)

from bot.callback_constants import (
    UserChangeFieldCallback,
    UserStartBranchReplyCallback,
    UserFullTextAnswerReplyCallback,
    UserFastAnswerReplyCallback
)

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
        
        try:
            field_value = update.message.text_markdown_urled
        except Exception:
            field_value = escape_markdown(update.message.text)

        user_curr_field = await update_user_over_next_question_answer_and_get_curr_field(update, context, user, settings, session, message_type)
        if user_curr_field:
            await insert_or_update_user_field_value(
                session    = session,
                user_id    = user.id,
                field_id   = user_curr_field.id,
                value      = field_value,
                message_id = update.message.id
            )
            return await session.commit()

        keyboard_key = await answer_to_user_keyboard_key_hit(update, context, user, session)
        if keyboard_key:
            await session.execute(
                sql_udate(User)
                .where(User.id == user.id)
                .values(curr_keyboard_key_parent_id = keyboard_key.parent_key_id)
            )
            return await session.commit()

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

            await insert_or_update_user_field_value(
                session    = session, 
                user_id    = user.id,
                field_id   = user_curr_field.id,
                value      = full_filename,
                message_id = update.message.id
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
            reply_markup = construct_keyboard_reply(changing_field, app, deferable_key=False)
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

async def branch_start_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка обратного вызова начала ветки вопроса"""
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    
    await update.callback_query.answer()

    reply_message_id, branch_id = map(int, update.callback_query.data.removeprefix(
        UserStartBranchReplyCallback.PREFIX
    ).split(
        UserStartBranchReplyCallback.SPLIT
    ))

    logger.info(f"Got change field callback from user {chat_id=} {username=} by reply {reply_message_id=} for branch {branch_id=}")

    async with app.provider.db_session() as session:
        user = await get_user_by_chat_id_or_none(session, chat_id)

        if not user:
            return logger.warning(f"Got change field callback from unknown user {chat_id=} {username=} by reply {reply_message_id=} for branch {branch_id=}")

        branch_selected = await session.execute(
            select(FieldBranch)
            .where(FieldBranch.id == branch_id)
        )
        branch = branch_selected.scalar_one_or_none()

        if not branch:
            return logger.warning(f"Got change field callback from user {chat_id=} {username=} by reply {reply_message_id=} for unknown branch {branch_id=}")
    
        field = await get_field_question_by_branch(session, branch.key)

        if not field:
            return logger.warning(f"Got change field callback from user {chat_id=} {username=} by reply {reply_message_id=} with unknown first field {branch_id=}")
        
        await update.effective_message.reply_markdown(
            text = field.question_markdown,
            reply_markup = construct_keyboard_reply(field, app)
        )

        await session.execute(
            sql_udate(User)
            .where(User.id == user.id)
            .values(
                curr_field_id = field.id,
                curr_reply_message_id = reply_message_id
            )
        )

        await session.commit()

async def full_text_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка обратного вызова начала ветки вопроса"""
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    
    await update.callback_query.answer()

    reply_message_id, field_id = map(int, update.callback_query.data.removeprefix(
        UserFullTextAnswerReplyCallback.PREFIX
    ).split(
        UserFullTextAnswerReplyCallback.SPLIT
    ))

    logger.info(f"Got change field callback from user {chat_id=} {username=} by reply {reply_message_id=} for field {field_id=}")

    async with app.provider.db_session() as session:
        user = await get_user_by_chat_id_or_none(session, chat_id)

        if not user:
            return logger.warning(f"Got change field callback from unknown user {chat_id=} {username=} by reply {reply_message_id=} for field {field_id=}")

        field_selected = await session.execute(
            select(Field)
            .where(Field.id == field_id)
        )
        field = field_selected.scalar_one_or_none()

        if not field:
            return logger.warning(f"Got change field callback from user {chat_id=} {username=} by reply {reply_message_id=} for unknown field {field_id=}")
    
        await update.effective_message.reply_markdown(
            text = field.question_markdown,
            reply_markup = construct_keyboard_reply(field, app)
        )

        await session.execute(
            sql_udate(User)
            .where(User.id == user.id)
            .values(
                curr_field_id = field.id,
                curr_reply_message_id = reply_message_id
            )
        )

        await session.commit()

async def fast_answer_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка обратного вызова начала ветки вопроса"""
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    
    await update.callback_query.answer()

    reply_message_id, field_id, answer_idx = map(int, update.callback_query.data.removeprefix(
        UserFastAnswerReplyCallback.PREFIX
    ).split(
        UserFastAnswerReplyCallback.SPLIT
    ))

    logger.info(f"Got change field callback from user {chat_id=} {username=} by reply {reply_message_id=} for field {field_id=} with idx {answer_idx=}")

    async with app.provider.db_session() as session:
        user = await get_user_by_chat_id_or_none(session, chat_id)

        if not user:
            return logger.warning(f"Got change field callback from unknown user {chat_id=} {username=} by reply {reply_message_id=} for field {field_id=} with idx {answer_idx=}")

        reply_message_selected = await session.execute(
            select(ReplyableConditionMessage)
            .where(ReplyableConditionMessage.id == reply_message_id)
        )
        reply_message = reply_message_selected.scalar_one_or_none()

        if not reply_message:
            return logger.warning(f"Got change field callback from user {chat_id=} {username=} by unknown reply {reply_message_id=} for field {field_id=} with idx {answer_idx=}")
    
        await update.effective_message.reply_markdown(
            text = reply_message.reply_status_replies.split('\n')[answer_idx],
            reply_markup = await get_keyboard_of_user(session, user)
        )

        await insert_or_update_user_field_value(
            session    = session, 
            user_id    = user.id,
            field_id   = field_id,
            value      = reply_message.reply_keyboard_keys.split('\n')[answer_idx],
            message_id = update.effective_message.id
        )

        await session.commit()
