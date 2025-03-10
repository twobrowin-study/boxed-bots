from datetime import datetime

from jinja2 import Template
from loguru import logger
from sqlalchemy import insert, select
from telegram import Chat, Message, Update
from telegram import User as TelegramUser
from telegram.ext import ContextTypes, ConversationHandler

from src.bot.exceptions import CouldNotCreateUserError, CouldNotSendFirstFieldQuestionError
from src.bot.helpers.fields.keyboards import construct_field_reply_keyboard_markup
from src.bot.helpers.fields.transitions import get_first_field_of_branch
from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.users import get_user_message_data_return_none
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import FieldStatusEnum
from src.utils.db_model import Field, Settings, User, UserFieldValue


async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команд старта или помощи пользователя
    """
    handler = "start/help command"

    app, user, chat, message, telegram_user, settings = await get_user_message_data_return_none(
        update, context, handler
    )

    bot_status = await app.provider.bot_status

    if not user and bot_status.is_registration_open is False:
        logger.warning(
            f"Got {handler} from new user {chat.id=} and {telegram_user.username=}, but registration is complete"
        )
        await message.reply_markdown(settings.user_registration_is_over_message_plain)
        return ConversationHandler.END

    if not user:
        await _create_new_user_and_reply_first_field_question(app, chat, message, telegram_user, settings)
        return ConversationHandler.END

    await _reply_start_help_command(app, user, message, settings)
    return ConversationHandler.END


async def _create_new_user_and_reply_first_field_question(
    app: BBApplication, chat: Chat, message: Message, telegram_user: TelegramUser, settings: Settings
) -> None:
    """
    Создаёт нового пользователя и отвечает ему сообщением
    """
    logger.debug(f"Creating new user {chat.id=}")

    first_field = await get_first_field_of_branch(app, settings.user_first_field_branch_plain)

    if not first_field.question_markdown_or_j2_template:
        raise CouldNotSendFirstFieldQuestionError

    start_message_text = await Template(settings.user_start_message_j2_template, enable_async=True).render_async(
        first_question=first_field.question_markdown_or_j2_template,
    )

    await message.reply_markdown(
        start_message_text,
        reply_markup=construct_field_reply_keyboard_markup(first_field, settings, context="full_text_answer"),
    )

    async with app.provider.db_sessionmaker() as session:
        user = await session.scalar(
            insert(User)
            .values(
                timestamp=datetime.now(),  # noqa: DTZ005
                chat_id=chat.id,
                username=telegram_user.username,
                curr_field_id=first_field.id,
            )
            .returning(User)
        )

        if not user:
            raise CouldNotCreateUserError

        fields_to_create = await session.scalars(
            select(Field).where(Field.status == FieldStatusEnum.JINJA2_FROM_USER_ON_CREATE)
        )

        for field_to_create in fields_to_create:
            if not field_to_create.question_markdown_or_j2_template:
                continue

            await session.execute(
                insert(UserFieldValue).values(
                    user_id=user.id,
                    field_id=field_to_create.id,
                    value=await Template(
                        field_to_create.question_markdown_or_j2_template, enable_async=True
                    ).render_async(user=user),
                )
            )

        logger.debug(f"Created new user {user.id=} with {chat.id=}")

        await session.commit()


async def _reply_start_help_command(app: BBApplication, user: User, message: Message, settings: Settings) -> None:
    """
    Парсит различные варианты команд старта и помощи для уже зарегистрированных пользователей
    """
    for command in message.parse_entities().values():
        message_template: Template | None = None
        command_action = "unknown"
        if command.endswith(app.START_COMMAND):
            message_template = Template(settings.user_restart_message_j2_template, enable_async=True)
            command_action = "help"
        if command.endswith(app.HELP_COMMAND):
            message_template = Template(settings.user_help_message_j2_template, enable_async=True)
            command_action = "restart"

        logger.debug(
            f"Got {command_action} command from user {user.chat_id=} and {user.username=} with {user.curr_field_id=}"
        )

        if user.curr_field and message_template:
            await message.reply_markdown(
                await message_template.render_async(
                    current_question_or_help_text=user.curr_field.question_markdown_or_j2_template
                ),
                reply_markup=construct_field_reply_keyboard_markup(
                    user.curr_field, settings, context="full_text_answer"
                ),
            )
            return

        if not user.curr_field and message_template:
            await message.reply_markdown(
                await message_template.render_async(
                    current_question_or_help_text=settings.user_registered_help_or_restart_message_plain
                ),
                reply_markup=await get_user_current_keyboard(app, user),
            )
            return
