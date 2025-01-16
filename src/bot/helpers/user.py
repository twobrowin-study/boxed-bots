from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy import select, insert, update as sql_update, func

from io import BytesIO
from datetime import datetime
from loguru import logger

import re
from jinja2 import Template

from bot.application import BBApplication
from utils.db_model import (
    User, Field,
    UserFieldValue,
    Settings,
    KeyboardKey,
    ReplyableConditionMessage,
    NewsPost
)
from utils.custom_types import (
    UserStatusEnum,
    KeyboardKeyStatusEnum,
    UserFieldDataPrepared,
    ReplyTypeEnum,
    FieldStatusEnum,
    PassSubmitStatus,
)

from bot.helpers.promocodes import send_promocodes
from bot.handlers.group import group_send_to_all_admin_tasked

from bot.helpers.keyboards import (
    construct_keyboard_reply,
    get_keyboard_of_user,
    get_keyboard_key_by_key_text,
    get_awaliable_inline_keyboard_for_user
)
from bot.helpers.fields import (
    get_field_question_by_branch,
    get_next_field_question,
    get_user_field_value_by_key,
)

from bot.callback_constants import UserChangeFieldCallback, UserSubmitPassCallback, UserChangePassFieldCallback

async def insert_or_update_user_field_value(
        session: AsyncSession,
        user_id: int, field_id: int,
        value: str, message_id: int
    ) -> None:
    updated = await session.execute(
        sql_update(UserFieldValue)
        .where(
            (UserFieldValue.user_id  == user_id) &
            (UserFieldValue.field_id == field_id)
        )
        .values(
            user_id    = user_id,
            field_id   = field_id,
            value      = value,
            message_id = message_id
        )
    )

    if updated.rowcount == 0:
        await session.execute(
            insert(UserFieldValue)
            .values(
                user_id    = user_id,
                field_id   = field_id,
                value      = value,
                message_id = message_id
            )
        )

async def user_set_have_banned_bot(app: BBApplication, chat_id: int, have_banned_bot: bool) -> None:
    """
    Установить статус пользователя о бане бота
    """
    async with app.provider.db_session() as session:
        await session.execute(
            sql_update(User).
            where(User.chat_id == chat_id).
            values(have_banned_bot = have_banned_bot)
        )
        await session.commit()

async def get_user_by_chat_id_or_none(session: AsyncSession, chat_id: int) -> User|None:
    """
    Получить пользователя или ничего если пользователя не существует
    """
    selection = await session.execute(
        select(User).where(User.chat_id == chat_id)
    )
    return selection.scalar_one_or_none()

async def create_new_user_and_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, settings: Settings, session: AsyncSession) -> None:
    """
    Создаёт нового пользователя и оповещает его
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    logger.info(f"Got start/help command from new user {chat_id=} and {username=}")
    first_question = await get_field_question_by_branch(session, settings.first_field_branch)
    await update.message.reply_markdown(
        settings.start_template.format(
            template = first_question.question_markdown,
        ),
        reply_markup = construct_keyboard_reply(first_question, app)
    )
    user = await session.scalar(
        insert(User).values(
            timestamp     = datetime.now(),
            chat_id       = chat_id,
            username      = username,
            curr_field_id = first_question.id
        ).returning(User)
    )
    if not user:
        message = f"Was not able to create user {chat_id=} and {username=}"
        logger.error(message)
        raise Exception(message)
    
    fields_to_create = await session.scalars(
        select(Field)
        .where(Field.status == FieldStatusEnum.JINJA2_FROM_USER_ON_CREATE)
    )

    for field_to_create in fields_to_create:
        await session.execute(
            insert(UserFieldValue)
            .values(
                user_id = user.id,
                field_id = field_to_create.id,
                value = Template(field_to_create.question_markdown).render(user=user)
            )
        )

    logger.info(f"Creating new user {chat_id=} and {username=} with {user.id=}")

async def parse_start_help_commands_and_answer(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                               user: User, settings: Settings, session: AsyncSession) -> None:
    """
    Парсит различные варианты команд старта и помощи для уже зарегистрированных пользователей
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    for _,entity in update.message.parse_entities().items():
        curr_field: Field|None = user.curr_field

        if curr_field and entity.endswith(app.HELP_COMMAND):
            logger.info(f"Got help command from user {chat_id=} and {username=} with {curr_field.key=}")
            await update.message.reply_markdown(
                settings.help_user_template.format(
                    template = curr_field.question_markdown
                ),
                reply_markup = construct_keyboard_reply(curr_field, app, cancel_key=(user.change_field_message_id is not None))
            )
            return

        if curr_field and entity.endswith(app.START_COMMAND):
            logger.info(f"Got start command from user {chat_id=} and {username=} with {curr_field.key=}")
            await update.message.reply_markdown(
                settings.restart_user_template.format(
                    template = curr_field.question_markdown
                ),
                reply_markup = construct_keyboard_reply(curr_field, app, cancel_key=(user.change_field_message_id is not None))
            )
            return

        if not curr_field and entity.endswith(app.HELP_COMMAND):
            logger.info(f"Got help command from user {chat_id=} and {username=} without current field")
            await update.message.reply_markdown(
                settings.help_user_template.format(
                    template = settings.help_restart_on_registration_complete
                ),
                reply_markup = await get_keyboard_of_user(session, user)
            )
            return

        if not curr_field and entity.endswith(app.START_COMMAND):
            logger.info(f"Got start command from user {chat_id=} and {username=} without current field")
            await update.message.reply_markdown(
                settings.restart_user_template.format(
                    template = settings.help_restart_on_registration_complete
                ),
                reply_markup = await get_keyboard_of_user(session, user)
            )
            return

async def upload_telegram_file_to_minio_and_return_filename(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                                            user: User, field: Field, settings: Settings, session: AsyncSession) -> str:
    """
    Загружает файл из telegram в Minio и возвращает итоговое название файла для сохранения в БД
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    logger.info(f"Uploading file from user {chat_id=} {username=}")

    if update.message.document:
        file = await update.message.document.get_file()
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()

    in_memory = BytesIO()
    await file.download_to_memory(in_memory)
    
    saved_filename = await get_user_field_value_by_key(session, user, settings.user_document_name_field)

    bucket = field.document_bucket or field.image_bucket

    return await app.provider.minio.upload_with_thumbnail_and_return_filename(
        bucket                = bucket,
        filename_wo_extension = saved_filename,
        bio                   = in_memory
    )

async def update_user_over_next_question_answer_and_get_curr_and_next_fields(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                                    user: User, settings: Settings, session: AsyncSession,
                                                    message_type: str) -> tuple[Field|None, Field|None]:
    """
    Обновляет запись пользователя по логике получения следующего вопрос в ветке
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    curr_field: Field|None = user.curr_field

    if not curr_field:
        return None, None

    if update.message.text == app.provider.config.i18n.defer:
        await update.message.reply_markdown(
            app.provider.config.i18n.defered,
            reply_markup = await get_keyboard_of_user(session, user, always_add_defered_keys=True)
        )
        await session.execute(
            sql_update(User)
            .where(User.id == user.id)
            .values(
                deferred_field_id = curr_field.id,
                curr_field_id = None
            )
        )
        await session.commit()
        return None, None
    
    if message_type == 'text' and (curr_field.document_bucket or curr_field.image_bucket) and update.effective_message.text != app.provider.config.i18n.skip:
        await update.message.reply_markdown(
            curr_field.question_markdown,
            reply_markup = construct_keyboard_reply(curr_field, app)
        )
        logger.info((
            f"Got {message_type} answer from user {chat_id=} and {username=} "
            f"to question {curr_field.key=} with {curr_field.status=}, "
            f"but it was photo/document message and not skip button"
        ))
        return None, None
    
    if message_type == 'photo/document' and not (curr_field.document_bucket or curr_field.image_bucket):
        await update.message.reply_markdown(
            curr_field.question_markdown,
            reply_markup = construct_keyboard_reply(curr_field, app)
        )
        logger.info((
            f"Got {message_type} answer from user {chat_id=} and {username=} "
            f"to question {curr_field.key=} with {curr_field.status=}, "
            f"but it was text message and not skip button"
        ))
        return None, None
    
    curr_reply_message: ReplyableConditionMessage|None = user.curr_reply_message
    next_field = await get_next_field_question(session, curr_field) 

    if curr_reply_message and curr_reply_message.reply_type == ReplyTypeEnum.FULL_TEXT_ANSWER:
        logger.info((
            f"Got {message_type} answer from user {chat_id=} and {username=} "
            f"to question {curr_field.key=} with {curr_field.status=}, "
            f"for full text answer {curr_reply_message.id=}"
        ))
        await update.message.reply_markdown(
            curr_reply_message.reply_status_replies,
            reply_markup = await get_keyboard_of_user(session, user)
        )
        user_update = {
            'curr_field_id': None,
            'curr_reply_message_id': None
        }
    
    elif not next_field and curr_reply_message and curr_reply_message.reply_type == ReplyTypeEnum.BRANCH_START:
        logger.info((
            f"Got {message_type} answer from user {chat_id=} and {username=} "
            f"to question {curr_field.key=} with {curr_field.status=}, "
            f"for last question of branch id {curr_reply_message.id=}"
        ))
        await update.message.reply_markdown(
            curr_reply_message.reply_status_replies,
            reply_markup = await get_keyboard_of_user(session, user)
        )
        user_update = {
            'curr_field_id': None,
            'curr_reply_message_id': None
        }
    
    elif next_field:
        logger.info((
            f"Got {message_type} answer from user {chat_id=} and {username=} "
            f"to question {curr_field.key=} with {curr_field.status=}, "
            f"next question is {next_field.key=} with {next_field.status=}"
        ))
        await update.message.reply_markdown(
            next_field.question_markdown,
            reply_markup = construct_keyboard_reply(next_field, app)
        )
        user_update = {'curr_field_id': next_field.id}
    
    elif not next_field:
        logger.info((
            f"Got {message_type} answer from user {chat_id=} and {username=} "
            f"to last question {curr_field.key=} with {curr_field.status=}"
        ))
        await update.message.reply_markdown(
            settings.registration_complete,
            reply_markup = await get_keyboard_of_user(session, user)
        )
        
        user_update = {
            'curr_field_id': None,
            'status': UserStatusEnum.ACTIVE
        }

        try:
            user_count_selected = await session.execute(
                select(func.count())
                .where(User.status == UserStatusEnum.ACTIVE)
            )
            user_count = user_count_selected.scalar_one() + 1 # One new user was just activated
            if user_count % int(settings.report_send_every_x_active_users) == 0:
                logger.warning(f"Performing admin notification about number of active users {settings.report_send_every_x_active_users=} {user_count=}")
                await group_send_to_all_admin_tasked(
                    app     = app,
                    message = settings.report_currently_active_users_template.format(
                        count = user_count
                    ),
                    parse_mode = ParseMode.MARKDOWN
                )
        except Exception:
            logger.warning(f"Was not able to perform admin notification about number of active users {settings.report_send_every_x_active_users=}")

    await session.execute(
        sql_update(User)
        .where(User.id == user.id)
        .values(**user_update)
    )

    return curr_field, next_field

async def user_change_field_and_answer(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                        user: User, settings: Settings, session: AsyncSession,
                                        message_type: str, change_only_inline_keyboard: bool = False) -> bool:
    """
    Обновляет запись пользователя по логике изменения значения поля

    Если записи нет - создаёт, если есть - обновляет
    """
    app: BBApplication = context.application
    bot: Bot = app.bot
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    logger.info(f"Updating field of user {chat_id=} {username=} {user.curr_field_id=} in message {message_type=}")

    curr_field: Field|None = user.curr_field

    if not curr_field:
        logger.error(f"Could not found field to update user {chat_id=} {username=} {user.curr_field_id=}")
        await update.message.reply_markdown(settings.error_reply)
        return True

    if update.message.text == app.provider.config.i18n.cancel:
        await update.message.reply_markdown(
            app.provider.config.i18n.change_canceled,
            reply_markup = await get_keyboard_of_user(session, user)
        )
        await session.execute(
            sql_update(User)
            .where(User.id == user.id)
            .values(
                curr_field_id = None,
                change_field_message_id = None
            )
        )
        return False
    
    if message_type == 'text' and (curr_field.document_bucket or curr_field.image_bucket):
        await update.message.reply_markdown(curr_field.question_markdown)
        return True
    
    if message_type == 'photo/document' and not (curr_field.document_bucket or curr_field.image_bucket):
        await update.message.reply_markdown(curr_field.question_markdown)
        return True
    
    file_size: int|None = None
    if update.message.document:
        file_size = update.message.document.file_size
    elif update.message.photo:
        file_size = update.message.photo[-1].file_size
    
    if file_size and file_size >= 20_000_000:
        logger.info(f"Got too large file while updating field of user {chat_id=} {username=} {user.curr_field_id=} in message {message_type=}")
        return await update.message.reply_markdown(settings.file_too_large_reply)
    
    try:
        user_field_value_data = update.message.text_markdown_urled
    except Exception:
        user_field_value_data = escape_markdown(update.message.text)
        
    if curr_field.validation_regexp and curr_field.validation_error_markdown:
        validation_regexp = re.compile(curr_field.validation_regexp)
        if validation_regexp.match(user_field_value_data) is None:
            return await update.message.reply_markdown(curr_field.validation_error_markdown)
            
    if curr_field and curr_field.check_future_date:
        input_date = datetime.strptime(user_field_value_data, '%d.%m.%Y').date()
        today      = datetime.today().date()
        if input_date > today:
            return await update.message.reply_markdown(curr_field.validation_error_markdown)
    
    if curr_field and curr_field.check_future_year:
        input_year   = datetime.strptime(user_field_value_data, '%Y').year
        current_year = datetime.today().year
        if input_year > current_year:
            return await update.message.reply_markdown(curr_field.validation_error_markdown)
        
    if curr_field and curr_field.validation_remove_regexp:
        user_field_value_data = re.sub(re.compile(curr_field.validation_remove_regexp), "", user_field_value_data)
    
    if curr_field and curr_field.upper_before_save:
        user_field_value_data = user_field_value_data.upper()
    
    await update.message.reply_markdown(
        settings.user_change_message_reply_template.format(state = curr_field.key),
        reply_markup = await get_keyboard_of_user(session, user)
    )

    if message_type == 'photo/document':
        user_field_value_data = await upload_telegram_file_to_minio_and_return_filename(update, context, user, curr_field, settings, session)

    await insert_or_update_user_field_value(
        session    = session, 
        user_id    = user.id,
        field_id   = curr_field.id,
        value      = user_field_value_data,
        message_id = update.message.id
    )

    if change_only_inline_keyboard:
        try:
            await bot.edit_message_reply_markup(
                chat_id      = user.chat_id,
                message_id   = user.pass_change_field_message_id,
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        text=f"{app.provider.config.i18n.change if user_field_value_data else app.provider.config.i18n.append} {curr_field.key}",
                        callback_data=UserChangePassFieldCallback.TEMPLATE.format(field_id = curr_field.id)
                    )],
                    [InlineKeyboardButton(
                        text = app.provider.config.i18n.submit_pass,
                        callback_data = UserSubmitPassCallback.PATTERN
                    )],
                ]),
            )
        except Exception:
            logger.warning(f"Was not able to modify message after updating user {chat_id=} {username=} {user.curr_field_id=}")
    else:
        fields, user_fields = await get_user_me_fields(
            update, context,
            user, curr_field.branch_id,
            session, False
        )

        fields_text = "\n".join([
            f"*{field.key}*: `{user_fields[field.id].value if len(user_fields[field.id].value) <= 80 else user_fields[field.id].value[:81]+'...'}`"
            for field in fields
            if not user_fields[field.id].image_bucket and not user_fields[field.id].document_bucket
        ])

        try:
            await bot.edit_message_text(
                chat_id      = user.chat_id,
                message_id   = user.change_field_message_id,
                text         = fields_text,
                parse_mode   = ParseMode.MARKDOWN,
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        text=f"{app.provider.config.i18n.change if not user_fields[field.id].empty else app.provider.config.i18n.append} {field.key}",
                        callback_data=UserChangeFieldCallback.TEMPLATE.format(field_id = field.id)
                    )]
                    for field in fields
                ]),
            )
        except Exception:
            logger.warning(f"Was not able to modify message after updating user {chat_id=} {username=} {user.curr_field_id=}")
    
    await session.execute(
        sql_update(User)
        .where(User.id == user.id)
        .values(
            curr_field_id = None,
            change_field_message_id = None
        )
    )

    await user_set_fields_after_registration(update, context, user)

    return False


async def answer_to_user_keyboard_key_hit(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, session: AsyncSession) -> KeyboardKey:
    """
    Отвечает на пользовательский запрос на кнопку клавиатуры
    """
    app: BBApplication = context.application
    bot: Bot = app.bot
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    settings = await app.provider.settings

    keyboard_key = await get_keyboard_key_by_key_text(session, update.message.text)
    
    if not keyboard_key:
        return None
    
    logger.info(f"Got keyboard key heat from user {chat_id=} and {username=} {keyboard_key.key=}")

    if keyboard_key.status == KeyboardKeyStatusEnum.ME:
        await post_user_me_information(update, context, user, keyboard_key, session)
        return keyboard_key

    if keyboard_key.status == KeyboardKeyStatusEnum.ME_CHANGE:
        await send_user_change_information(update, context, user, keyboard_key, session)
        return keyboard_key

    if keyboard_key.status == KeyboardKeyStatusEnum.BACK:
        parent_key = await session.scalar(
            select(KeyboardKey).where(KeyboardKey.id == keyboard_key.parent_key_id)
        )
        await update.message.reply_markdown(
            keyboard_key.key,
            reply_markup = await get_keyboard_of_user(session, user, to_parent_key=parent_key)
        )
        return parent_key

    if keyboard_key.status == KeyboardKeyStatusEnum.DEFERRED:
        deferred_field: Field = user.deferred_field
        await update.message.reply_markdown(
            deferred_field.question_markdown,
            reply_markup = construct_keyboard_reply(deferred_field, app)
        )
        async with app.provider.db_session() as session:
            await session.execute(
                sql_update(User)
                .where(User.id == user.id)
                .values(
                    deferred_field_id = None,
                    curr_field_id     = deferred_field.id
                )
            )
            await session.commit()
        return keyboard_key

    if keyboard_key.status == KeyboardKeyStatusEnum.NEWS:
        async with app.provider.db_session() as session:
            news_select = select(NewsPost).order_by(NewsPost.id.desc()).limit(int(settings.number_of_last_news_to_show))
            if keyboard_key.news_tag:
                news_select = news_select.where(NewsPost.tags.icontains(keyboard_key.news_tag))
            news_posts = await session.scalars(news_select)
            for news_post in reversed(news_posts.all()):
                try:
                    await bot.forward_message(
                        chat_id=chat_id,
                        from_chat_id=news_post.chat_id,
                        message_id=news_post.message_id
                    )
                except Exception:
                    logger.warning(f"Was not able to forward message with {news_post.id=}")
        return keyboard_key

    if keyboard_key.status == KeyboardKeyStatusEnum.PASS:
        settings = await app.provider.settings
        async with app.provider.db_session() as session:
            pass_selected = await session.execute(
                select(UserFieldValue.value, Field.image_bucket)
                .where(Field.key == settings.pass_user_field)
                .where(UserFieldValue.user_id == user.id)
                .where(UserFieldValue.field_id == Field.id)
            )
            pass_row = pass_selected.one_or_none()
            pass_photo, pass_image_bucket = (None, None)
            if pass_row:
                pass_photo, pass_image_bucket = pass_row.t
            if not pass_photo and user.pass_status == PassSubmitStatus.NOT_SUBMITED:
                request_pass_field_value = await session.scalar(
                    select(UserFieldValue.value)
                    .where(Field.key == settings.user_field_to_request_pass)
                    .where(UserFieldValue.user_id == user.id)
                    .where(UserFieldValue.field_id == Field.id)
                )
                request_pass_field = await session.scalar(
                    select(Field)
                    .where(Field.key == settings.user_field_to_request_pass)
                )
                await update.message.reply_markdown(
                    settings.pass_hint_message,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            text=f"{app.provider.config.i18n.change if request_pass_field_value else app.provider.config.i18n.append} {request_pass_field.key}",
                            callback_data=UserChangePassFieldCallback.TEMPLATE.format(field_id = request_pass_field.id)
                        )],
                        [InlineKeyboardButton(
                            text = app.provider.config.i18n.submit_pass,
                            callback_data = UserSubmitPassCallback.PATTERN
                        )],
                    ])
                )
            elif not pass_photo and user.pass_status == PassSubmitStatus.SUBMITED:
                await update.message.reply_markdown(settings.pass_submitted_message)
            else:
                pass_photo_bio, _ = await app.provider.minio.download(pass_image_bucket, pass_photo)
                await update.message.reply_photo(
                    pass_photo_bio,
                    caption=settings.pass_message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=await get_keyboard_of_user(session, user, from_parent_key=keyboard_key)
                )
        return keyboard_key
    
    if keyboard_key.status == KeyboardKeyStatusEnum.PROMOCODES:
        await send_promocodes(update, context)
        return keyboard_key
    
    if keyboard_key.status == KeyboardKeyStatusEnum.NORMAL:
        reply_condition_message: ReplyableConditionMessage = keyboard_key.reply_condition_message

        reply_markup = (
            await get_awaliable_inline_keyboard_for_user(reply_condition_message, user, session)
        ) or (
            await get_keyboard_of_user(session, user, from_parent_key=keyboard_key)
        )

        if reply_condition_message.photo_link in [None, '']:
            await update.message.reply_markdown(
                reply_condition_message.text_markdown,
                reply_markup = reply_markup
            )
            return keyboard_key

        if reply_condition_message.photo_link not in [None, ''] and len(reply_condition_message.text_markdown) <= 1024:
            await update.message.reply_photo(
                reply_condition_message.photo_link,
                caption = reply_condition_message.text_markdown,
                reply_markup = reply_markup,
                parse_mode = ParseMode.MARKDOWN
            )
            return keyboard_key

        if reply_condition_message.photo_link not in [None, ''] and len(reply_condition_message.text_markdown) > 1024:
            await update.message.reply_photo(reply_condition_message.photo_link)
            await update.message.reply_markdown(
                reply_condition_message.text_markdown,
                reply_markup = reply_markup
            )
            return keyboard_key

    return None

async def get_user_me_fields(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 user: User, branch_id: int, session: AsyncSession,
                                 send_photos: bool = True, send_documents: bool = False) -> tuple[list[Field], dict[int, UserFieldDataPrepared]]:
    """Получает информацию о пользователе по нажатию кнопкии "Обо мне" или "Изменить профиль"""""
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    fields_selected = await session.execute(
        select(Field)
        .where(Field.branch_id == branch_id)
        .order_by(Field.order_place.asc())
    )
    fields = list(fields_selected.scalars())

    user_fields = user.prepare_fields()

    for field in fields:
        if field.id not in user_fields:
            user_fields[field.id] = UserFieldDataPrepared(
                value = app.provider.config.i18n.data_empty,
                document_bucket = field.document_bucket,
                image_bucket    = field.image_bucket,
                empty = True
            )
            continue
        
        if user_fields[field.id].document_bucket and send_documents:
            logger.info(f"Trying to send document on ME key hit to user {chat_id=} {username=} for field {field.id=}")
            
            if update.message:
                try:
                    filename = user_fields[field.id].value
                    bio, _ = await app.provider.minio.download(
                        user_fields[field.id].document_bucket,
                        filename
                    )
                    await update.message.reply_document(bio, filename=filename)
                except Exception:
                    logger.warning('Was not able to send document on ME key hit to user {chat_id=} {username=} for field {field.id=}')

            user_fields[field.id] = UserFieldDataPrepared(
                value = app.provider.config.i18n.document,
                document_bucket = user_fields[field.id].document_bucket,
                image_bucket    = user_fields[field.id].image_bucket
            )
            continue

        if user_fields[field.id].image_bucket and send_photos:
            logger.info(f"Trying to send image on ME key hit to user {chat_id=} {username=} for field {field.id=}")
            
            if update.message:
                try:
                    bio, _ = await app.provider.minio.download(
                        user_fields[field.id].image_bucket,
                        user_fields[field.id].value.replace('_thumbnail', '')
                    )
                    await update.message.reply_photo(bio)
                except Exception:
                    logger.warning(f'Was not able to send image on ME key hit to user {chat_id=} {username=} for field {field.id=}')

            user_fields[field.id] = UserFieldDataPrepared(
                value = app.provider.config.i18n.image,
                document_bucket = user_fields[field.id].document_bucket,
                image_bucket    = user_fields[field.id].image_bucket
            )
            continue
    
    return fields, user_fields

async def post_user_me_information(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   user: User, keyboard_key: KeyboardKey, session: AsyncSession) -> None:
    """
    Отправляет информацию о пользователе по нажатию кноки "Обо мне" по заданной в клавише ветке вопросов
    """
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    logger.info(f"Sending ME info to user {chat_id=} {username=} by branch {keyboard_key.branch_id=}")

    fields, user_fields = await get_user_me_fields(
        update, context,
        user, keyboard_key.branch_id,
        session
    )

    fields_text = "\n".join([
        f"*{field.key}*: `{user_fields[field.id].value if len(user_fields[field.id].value) <= 80 else user_fields[field.id].value[:81]+'...'}`"
        for field in fields
        if not user_fields[field.id].image_bucket and not user_fields[field.id].document_bucket
    ])

    await update.message.reply_markdown(
        fields_text,
        reply_markup = await get_keyboard_of_user(session, user, from_parent_key=keyboard_key)
    )

async def send_user_change_information(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       user: User, keyboard_key: KeyboardKey, session: AsyncSession) -> None:
    """
    Отправляет пользователю кнопки на исправление данных о себе по нажатой выше кнопке
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Sending ME_CHANGE keys to user {chat_id=} {username=} by branch {keyboard_key.branch_id=}")

    fields, user_fields = await get_user_me_fields(
        update, context,
        user, keyboard_key.branch_id,
        session
    )

    fields_text = "\n".join([
        f"*{field.key}*: `{user_fields[field.id].value if len(user_fields[field.id].value) <= 80 else user_fields[field.id].value[:81]+'...'}`"
        for field in fields
        if not user_fields[field.id].image_bucket and not user_fields[field.id].document_bucket
    ])

    await update.message.reply_markdown(
        fields_text,
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text=f"{app.provider.config.i18n.change if not user_fields[field.id].empty else app.provider.config.i18n.append} {field.key}",
                callback_data=UserChangeFieldCallback.TEMPLATE.format(field_id = field.id)
            )]
            for field in fields
        ])
    )

async def user_set_fields_after_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User) -> None:
    """Установить вычисляемые после регистрации пользователя поля"""
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Setting user after registration fields to user {chat_id=} {username=}")

    async with app.provider.db_session() as session:
        jinja2_after_user_registration_fields = await session.scalars(
            select(Field).where(Field.status == FieldStatusEnum.JINJA2_FROM_USER_AFTER_REGISTRATION)
        )

        user_dict = user.to_plain_dict()

        for field in jinja2_after_user_registration_fields:
            logger.info(f"Setting user after registration field {field.key=} to user {chat_id=} {username=}")

            field_value = Template(field.question_markdown).render(user = user_dict)

            if field.validation_remove_regexp:
                field_value = re.sub(re.compile(field.validation_remove_regexp), "", field_value)

            await insert_or_update_user_field_value(
                session=session,
                user_id = user.id,
                field_id = field.id,
                value = field_value,
                message_id = -1
            )
        
        await session.commit()
