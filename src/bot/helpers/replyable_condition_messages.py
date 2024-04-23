from sqlalchemy import select, union, CompoundSelect
from sqlalchemy.ext.asyncio.session import AsyncSession

from utils.db_model import (
    User, ReplyableConditionMessage,
    Field, UserFieldValue
)

def select_awaliable_replyable_condition_messages_by_condition_bool_field_id(user: User) -> CompoundSelect:
    """Select запрос для получения доступных пользователю сообщений"""
    return union(
        select(ReplyableConditionMessage.id)
        .where(ReplyableConditionMessage.condition_bool_field_id == None),
        
        select(ReplyableConditionMessage.id)
        .where(
            (Field.id == ReplyableConditionMessage.condition_bool_field_id) &
            (Field.is_boolean == True) &
            (UserFieldValue.field_id == Field.id) &
            (UserFieldValue.user_id  == user.id) &
            (UserFieldValue.value    == 'true')
        )
    )

async def check_if_reply_condition_message_is_awaliable_by_reply_condition_bool_field_id(
        reply_condition_message: ReplyableConditionMessage,
        user: User, session: AsyncSession
    ) -> bool:
    """Select запрос для получения доступных пользователю ответов на сообщение"""
    selected = await session.execute(
        union(
            select(ReplyableConditionMessage.id)
            .where(
                (ReplyableConditionMessage.id == reply_condition_message.id) &
                (ReplyableConditionMessage.reply_condition_bool_field_id == None)
            ),
            
            select(ReplyableConditionMessage.id)
            .where(
                (ReplyableConditionMessage.id == reply_condition_message.id) &
                (Field.id == ReplyableConditionMessage.reply_condition_bool_field_id) &
                (Field.is_boolean == True) &
                (UserFieldValue.field_id == Field.id) &
                (UserFieldValue.user_id  == user.id) &
                (UserFieldValue.value    == 'true')
            )
        )
    )
    return selected.scalar_one_or_none() is not None