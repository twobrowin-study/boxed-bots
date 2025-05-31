from loguru import logger
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.helpers.users.passes import construct_pass_submit_inline_keyboard
from src.bot.telegram.application import BBApplication
from src.bot.telegram.callback_constants import (
    UserFastAnswerReplyCallback,
    UserFullTextAnswerReplyCallback,
    UserStartBranchReplyCallback,
)
from src.utils.custom_types import FieldTypeEnum, ReplyTypeEnum
from src.utils.db_model import Field, ReplyableConditionMessage, Settings, User, UserFieldValue


async def get_user_reply_condition_message_reply_keyboard(  # noqa: PLR0911
    app: BBApplication,
    user: User,
    reply_condition_message: ReplyableConditionMessage,
    settings: Settings,
) -> InlineKeyboardMarkup | None:
    """
    Получить inline-клавиатуру для сообщения с условием

    Параметры:
    * app: BBApplication - Приложение
    * user: User - Пользователь, для которого следует получить клавиатуру
    * reply_condition_message: ReplyableConditionMessage - Сообщение c условием
    * settings: Settings - Настройки
    """
    if reply_condition_message.reply_type == ReplyTypeEnum.PASS:
        return await construct_pass_submit_inline_keyboard(app, user, settings)

    if not reply_condition_message.reply_keyboard_keys:
        return None

    reply_condition = await _check_user_reply_condition_message_reply_condition(app, user, reply_condition_message)
    if not reply_condition:
        logger.debug(
            f"User {user.id=} cannot get Replyable Condition Message Reply Keyboard {reply_condition_message.id=}"
        )
        return None

    if reply_condition_message.reply_type == ReplyTypeEnum.BRANCH_START:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=reply_condition_message.reply_keyboard_keys,
                        callback_data=UserStartBranchReplyCallback.TEMPLATE.format(
                            reply_message_id=reply_condition_message.id,
                            branch_id=reply_condition_message.reply_answer_field_branch_id,
                        ),
                    )
                ]
            ]
        )

    if reply_condition_message.reply_type == ReplyTypeEnum.FULL_TEXT_ANSWER:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=reply_condition_message.reply_keyboard_keys,
                        callback_data=UserFullTextAnswerReplyCallback.TEMPLATE.format(
                            reply_message_id=reply_condition_message.id,
                            field_id=reply_condition_message.reply_answer_field_id,
                        ),
                    )
                ]
            ]
        )

    if reply_condition_message.reply_type in [ReplyTypeEnum.FAST_ANSWER, ReplyTypeEnum.FAST_ANSWER_WITH_NEXT]:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=answer,
                        callback_data=UserFastAnswerReplyCallback.TEMPLATE.format(
                            reply_message_id=reply_condition_message.id,
                            field_id=reply_condition_message.reply_answer_field_id,
                            answer_idx=answer_idx,
                        ),
                    )
                ]
                for answer_idx, answer in enumerate(reply_condition_message.reply_keyboard_keys.split("\n"))
            ]
        )

    return None


async def _check_user_reply_condition_message_reply_condition(
    app: BBApplication,
    user: User,
    reply_condition_message: ReplyableConditionMessage,
) -> bool:
    """
    Проверить доступность пользователю inline-клавиатуры для ответа на сообщение с условием

    Параметры:
    * app: BBApplication - Приложение
    * user: User - Пользователь, для которого проверяется условие
    * reply_condition_message: ReplyableConditionMessage - Сообщение c условием, для которого выполняется проверка
    """
    if reply_condition_message.reply_condition_bool_field is None:
        return True

    async with app.provider.db_sessionmaker() as session:
        condition = await session.scalar(
            select(ReplyableConditionMessage.id)
            .where(ReplyableConditionMessage.id == reply_condition_message.id)
            .where(Field.id == ReplyableConditionMessage.reply_condition_bool_field_id)
            .where(Field.type == FieldTypeEnum.BOOLEAN)
            .where(UserFieldValue.field_id == Field.id)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.value == "true")
        )
        return condition is not None
