from loguru import logger
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.exceptions import (
    BranchStartNoBranchError,
    BranchStartNoBranchFirstFieldQuestionError,
    BranchStartNoReplyableConditionMessageError,
)
from src.bot.helpers.fields.keyboards import construct_field_reply_keyboard_markup
from src.bot.helpers.fields.transitions import get_first_field_of_branch
from src.bot.helpers.users import get_user_callback_query_data_send_strange_error_and_rise
from src.bot.helpers.users.registration import update_user_registration_and_send_message
from src.bot.telegram.callback_constants import UserStartBranchReplyCallback
from src.utils.db_model import FieldBranch, ReplyableConditionMessage


async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопки начала ответа на ветку вопросов"""
    handler = "branch start"

    (
        app,
        user,
        callback_query_data,
        callback_query_message,
        settings,
    ) = await get_user_callback_query_data_send_strange_error_and_rise(update, context, handler)

    reply_message_id, branch_id = map(
        int,
        callback_query_data.removeprefix(UserStartBranchReplyCallback.PREFIX).split(UserStartBranchReplyCallback.SPLIT),
    )

    logger.debug(f"Got {handler} from user {user.id=} to reply message {reply_message_id=} for branch {branch_id=}")

    async with app.provider.db_sessionmaker() as session:
        reply_message = await session.scalar(
            select(ReplyableConditionMessage).where(ReplyableConditionMessage.id == reply_message_id)
        )
        branch = await session.scalar(select(FieldBranch).where(FieldBranch.id == branch_id))

    # Проверка наличия сообщения с условием и ответом, поля и вопроса поля
    if not reply_message:
        raise BranchStartNoReplyableConditionMessageError
    if not branch:
        raise BranchStartNoBranchError

    # Получение первого вопроса из ветки
    field = await get_first_field_of_branch(app, branch.key)
    if not field.question_markdown_or_j2_template:
        raise BranchStartNoBranchFirstFieldQuestionError

    # Отправить пользователю вопрос и усвоить этот вопрос в качестве текущего
    await update_user_registration_and_send_message(
        app=app,
        user=user,
        message=callback_query_message,
        text=field.question_markdown_or_j2_template,
        settings=settings,
        reply_keyboad_override=construct_field_reply_keyboard_markup(field, settings, "full_text_answer"),
        curr_field_id=field.id,
        curr_reply_message_id=reply_message.id,
    )
