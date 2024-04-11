from telegram import Update
from telegram.ext import ContextTypes

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy import select, insert, update as sql_udate

from datetime import datetime
from loguru import logger

from bot.application import BBApplication
from utils.db_model import User, Field, Settings
from utils.custom_types import UserStatusEnum

from bot.helpers.keyboards import construct_keyboard_reply, get_keyboard_of_user
from bot.helpers.fields import get_first_field_question, get_next_field_question_in_branch

async def user_set_have_banned_bot(app: BBApplication, chat_id: int, have_banned_bot: bool) -> None:
    """
    Установить статус пользователя о бане бота
    """
    async with app.provider.db_session() as session:
        await session.execute(
            sql_udate(User).
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
    chat_id  = update.effective_user.id
    username = update.effective_user.username

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
                reply_markup = construct_keyboard_reply(curr_field.answer_options)
            )
            return

        if curr_field and entity.endswith(app.START_COMMAND):
            logger.info(f"Got start command from user {chat_id=} and {username=} with {curr_field.key=}")
            await update.message.reply_markdown(
                settings.restart_user_template.format(
                    template = curr_field.question_markdown
                ),
                reply_markup = construct_keyboard_reply(curr_field.answer_options)
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

async def update_user_over_next_question_answer_and_get_curr_field(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                                    user: User, settings: Settings, session: AsyncSession,
                                                    message_type: str) -> Field|None:
    """
    Обновляет запись пользователя по логике получения следующего вопрос в ветке
    """
    app: BBApplication = context.application
    chat_id  = update.effective_user.id
    username = update.effective_user.username

    curr_field: Field|None = user.curr_field

    if not curr_field:
        return None
    
    if message_type == 'text' and (curr_field.document_bucket or curr_field.image_bucket):
        await update.message.reply_markdown(curr_field.question_markdown)
        return None
    
    if message_type == 'photo/document' and not (curr_field.document_bucket or curr_field.image_bucket):
        await update.message.reply_markdown(curr_field.question_markdown)
        return None

    # TODO: Научится получать вопрос из следующей ветки
    # TODO: Научится учитывать неотображаемые вопросы для того
    #       чтобы можно было до их заполнения проставить активность пользователя
    next_field = await get_next_field_question_in_branch(session, curr_field)

    if next_field:
        logger.info((
            f"Got {message_type} answer from user {chat_id=} and {username=} "
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
        
    await session.execute(
        sql_udate(User)
        .where(User.id == user.id)
        .values(**user_update)
    )

    return curr_field