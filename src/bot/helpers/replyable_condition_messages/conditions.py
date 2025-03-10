from sqlalchemy import CompoundSelect, Select, select, union

from src.utils.custom_types import FieldTypeEnum
from src.utils.db_model import Field, ReplyableConditionMessage, User, UserFieldValue


def compound_select_user_awaliable_replyable_condition_messages(
    user: User,
) -> CompoundSelect:
    """
    Select запрос для получения доступных пользователю сообщений с условием отправки

    Параметры:
    * user: User - пользователь для которого вычисляются условия
    """
    return union(
        select(ReplyableConditionMessage.id).where(ReplyableConditionMessage.condition_bool_field_id.is_(None)),
        select_user_replyable_condition_message_condition(user),
    )


def select_user_replyable_condition_message_condition(
    user: User,
    reply_condition_message: ReplyableConditionMessage | None = None,
) -> Select[tuple[int]]:
    """
    Select запрос вычисляющий условие отправки сообщения с условием

    Параметры:
    * user: User - пользователь для которого вычисляются условия
    * reply_condition_message: ReplyableConditionMessage | None = None - Собщение с условием для которого вычисляется условие (если Nonе, то вычисляется для всех)
    """
    if reply_condition_message:
        show_condition = Field.id == reply_condition_message.condition_bool_field_id
    else:
        show_condition = Field.id == ReplyableConditionMessage.condition_bool_field_id
    return (
        select(ReplyableConditionMessage.id)
        .where(show_condition)
        .where(Field.type == FieldTypeEnum.BOOLEAN)
        .where(UserFieldValue.field_id == Field.id)
        .where(UserFieldValue.user_id == user.id)
        .where(UserFieldValue.value == "true")
    )
