from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from sqlalchemy import insert, update as sql_udate

from datetime import datetime
from loguru import logger

from io import BytesIO

from utils.db_model import (
    User,
    Field,
    UserFieldValue
)
from utils.custom_types import (
    UserStatusEnum,
    FieldStatusEnum,
    KeyboardKeyStatusEnum
)

from bot.application import BBApplication

from bot.helpers.user import (
    get_user_by_chat_id_or_none
)
from bot.helpers.fields import (
    get_first_field_question,
    get_next_field_question_in_branch,
    get_user_field_value_by_key,
)
from bot.helpers.keyboards import (
    construct_keyboard_reply,
    get_keyboard_of_user,
    get_keyboard_key_by_key_text
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

        if not user and not bot_status.is_registration_open:
            logger.warning(f"Got start/help command from new user {chat_id=} and {username=}, but registration is complete")
            return await update.message.reply_markdown(settings.registration_is_over)
        
        if not user:
            logger.info(f"Got start/help command from new user {chat_id=} and {username=}")
            first_question = await get_first_field_question(session, settings)
            await update.message.reply_markdown(
                settings.start_template.format(
                    template = first_question.question_markdown
                )
            )
            await session.execute(
                insert(User).values(
                    timestamp     = datetime.now(),
                    chat_id       = chat_id,
                    username      = username,
                    curr_field_id = first_question.id
                )
            )
            logger.info(f"Creating new user {chat_id=} and {username=}")
            return await session.commit()

        for _,entity in update.message.parse_entities().items():

            curr_field: Field|None = user.curr_field

            if curr_field and entity.endswith(app.HELP_COMMAND):
                logger.info(f"Got help command from user {chat_id=} and {username=} with {curr_field.key=}")
                return await update.message.reply_markdown(
                    settings.help_user_template.format(
                        template = curr_field.question_markdown
                    ),
                    reply_markup = construct_keyboard_reply(curr_field.answer_options)
                )

            if curr_field and entity.endswith(app.START_COMMAND):
                logger.info(f"Got start command from user {chat_id=} and {username=} with {curr_field.key=}")
                return await update.message.reply_markdown(
                    settings.restart_user_template.format(
                        template = curr_field.question_markdown
                    ),
                    reply_markup = construct_keyboard_reply(curr_field.answer_options)
                )

            if not curr_field and entity.endswith(app.HELP_COMMAND):
                logger.info(f"Got help command from user {chat_id=} and {username=} without current field")
                return await update.message.reply_markdown(
                    settings.help_user_template.format(
                        template = settings.help_restart_on_registration_complete
                    ),
                    reply_markup = await get_keyboard_of_user(session, user)
                )

            if not curr_field and entity.endswith(app.START_COMMAND):
                logger.info(f"Got start command from user {chat_id=} and {username=} without current field")
                return await update.message.reply_markdown(
                    settings.restart_user_template.format(
                        template = settings.help_restart_on_registration_complete
                    ),
                    reply_markup = await get_keyboard_of_user(session, user)
                )

async def user_message_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик текстовых сообщений пользователя
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    async with app.provider.db_session() as session:
        user     = await get_user_by_chat_id_or_none(session, chat_id)
        settings = await app.provider.get_settings(session)

        if not user:
            logger.warning(f"Got text message from unknown user {chat_id=} and {username=}... strange error")
            return await update.message.reply_markdown(settings.strange_user_error)
        
        curr_field: Field|None = user.curr_field

        if curr_field:
            if curr_field.document_bucket or curr_field.image_bucket:
                return await update.message.reply_markdown(curr_field.question_markdown)

            # TODO: Научится получать вопрос из следующей ветки
            # TODO: Научится учитывать неотображаемые вопросы для того
            #       чтобы можно было до их заполнения проставить активность пользователя
            next_field = await get_next_field_question_in_branch(session, curr_field)

            if next_field:
                logger.info((
                    f"Got text answer from user {chat_id=} and {username=} "
                    f"to question {curr_field.key=} with {curr_field.status=}, "
                    f"next question is {next_field.key=} with {next_field.status=}"
                ))
                await update.message.reply_markdown(
                    next_field.question_markdown,
                    reply_markup = construct_keyboard_reply(next_field.answer_options)
                )
                
                user_update = {'curr_field_id': next_field.id}
            
            elif not next_field:
                logger.info((
                    f"Got text answer from user {chat_id=} and {username=} "
                    f"to last question {curr_field.key=} with {curr_field.status=}"
                ))
                await update.message.reply_markdown(
                    settings.registration_complete,
                    reply_markup = await get_keyboard_of_user(session, user)
                )
                
                user_update = {
                    'curr_field_id': None,
                    'status':        UserStatusEnum.ACTIVE
                }
                
            await session.execute(
                sql_udate(User)
                .where(User.id == user.id)
                .values(**user_update)
            )

            await session.execute(
                insert(UserFieldValue)
                .values(
                    user_id    = user.id,
                    field_id   = curr_field.id,
                    value      = update.message.text_markdown_urled,
                    message_id = update.message.id
                )
            )
            
            return await session.commit()

        keyboard_key = await get_keyboard_key_by_key_text(session, update.message.text)
        
        if keyboard_key:
            logger.info(f"Got keyboard key heat from user {chat_id=} and {username=} {keyboard_key.key=}")

            # if keyboard_key.status == KeyboardKeyStatusEnum.ME:
            #     users_field_values = {
            #         field_value.field_id: {
            #             'key':   field_value.field.key,
            #             'value': field_value.value
            #         }
            #         for field_value in user.fields_values
            #     }
            #     print(sorted(users_field_values))

            print(f"{keyboard_key.photo_link=}")

            if keyboard_key.photo_link in [None, '']:
                return await update.message.reply_markdown(
                    keyboard_key.text_markdown,
                    reply_markup = await get_keyboard_of_user(session, user)
                )
            elif keyboard_key.photo_link not in [None, ''] and len(keyboard_key.text_markdown) <= 1024:
                return await update.message.reply_photo(
                    keyboard_key.photo_link,
                    caption = keyboard_key.text_markdown,
                    reply_markup = await get_keyboard_of_user(session, user),
                    parse_mode = ParseMode.MARKDOWN
                )
            elif keyboard_key.photo_link not in [None, ''] and len(keyboard_key.text_markdown) > 1024:
                await update.message.reply_photo(keyboard_key.photo_link)
                return await update.message.reply_markdown(
                    keyboard_key.text_markdown,
                    reply_markup = await get_keyboard_of_user(session, user)
                )
        
        logger.warning(f"Got unknown text message from user {chat_id=} and {username=}")

async def user_message_photo_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик сообщений пользователя с фото или документом
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    if update.edited_message:
        settings = await app.provider.settings
        return await update.effective_message.reply_markdown(settings.edited_message_reply)

    async with app.provider.db_session() as session:
        user     = await get_user_by_chat_id_or_none(session, chat_id)
        settings = await app.provider.get_settings(session)

        if not user:
            logger.warning(f"Got photo/document from unknown user {chat_id=} and {username=}... strange error")
            return await update.message.reply_markdown(settings.strange_user_error)
        
        curr_field: Field|None = user.curr_field

        if curr_field:
            if not (curr_field.document_bucket or curr_field.image_bucket):
                return await update.message.reply_markdown(curr_field.question_markdown)

            next_field = await get_next_field_question_in_branch(session, curr_field)

            if next_field:
                logger.info((
                    f"Got photo/document answer from user {chat_id=} and {username=} "
                    f"to question {curr_field.key=} with {curr_field.status=}, "
                    f"next question is {next_field.key=} with {next_field.status=}"
                ))
                await update.message.reply_markdown(
                    next_field.question_markdown,
                    reply_markup = construct_keyboard_reply(next_field.answer_options)
                )
                
                user_update = {'curr_field_id': next_field.id}
            
            elif not next_field:
                logger.info((
                    f"Got photo/document answer from user {chat_id=} and {username=} "
                    f"to last question {curr_field.key=} with {curr_field.status=}"
                ))
                await update.message.reply_markdown(
                    settings.registration_complete,
                    reply_markup = await get_keyboard_of_user(session, user)
                )
                
                user_update = {
                    'curr_field_id': None,
                    'status':        UserStatusEnum.ACTIVE
                }
                
            await session.execute(
                sql_udate(User)
                .where(User.id == user.id)
                .values(**user_update)
            )

            if update.message.document:
                file = await update.message.document.get_file()
            elif update.message.photo:
                file = await update.message.photo[-1].get_file()

            in_memory = BytesIO()
            await file.download_to_memory(in_memory)
            
            saved_filename = await get_user_field_value_by_key(session, user, settings.user_document_name_field)

            bucket = curr_field.document_bucket or curr_field.image_bucket

            full_filename = await app.provider.minio.upload_with_thumbnail_and_return_filename(
                bucket                = bucket,
                filename_wo_extension = saved_filename,
                bio                   = in_memory
            )

            await session.execute(
                insert(UserFieldValue)
                .values(
                    user_id    = user.id,
                    field_id   = curr_field.id,
                    value      = full_filename,
                    message_id = update.message.id
                )
            )
            
            return await session.commit()
        
        logger.warning(f"Got unknown message from user {chat_id=} and {username=}")