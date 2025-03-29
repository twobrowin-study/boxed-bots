from sqlalchemy import select
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

from src.bot.helpers.replyable_condition_messages.conditions import (
    compound_select_user_awaliable_replyable_condition_messages,
)
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import KeyboardKeyStatusEnum
from src.utils.db_model import KeyboardKey, User


async def get_user_current_keyboard(app: BBApplication, user: User) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """Получить клавиатуру, доступную пользователю"""
    async with app.provider.db_sessionmaker() as session:
        keyboard_keys = list(
            await session.scalars(
                select(KeyboardKey)
                .where(
                    (
                        (KeyboardKey.status == KeyboardKeyStatusEnum.NORMAL)
                        & (
                            KeyboardKey.reply_condition_message_id.in_(
                                compound_select_user_awaliable_replyable_condition_messages(user)
                            )
                        )
                    )
                    | (
                        (KeyboardKey.status.in_([KeyboardKeyStatusEnum.ME, KeyboardKeyStatusEnum.ME_CHANGE]))
                        & (KeyboardKey.branch_id.is_not(None))
                    )
                    | (
                        (
                            KeyboardKey.status.in_(
                                [
                                    KeyboardKeyStatusEnum.NEWS,
                                    KeyboardKeyStatusEnum.PASS,
                                    KeyboardKeyStatusEnum.PROMOCODES,
                                ]
                            )
                        )
                        & (KeyboardKey.branch_id.is_(None))
                        & (KeyboardKey.reply_condition_message_id.is_(None))
                    )
                    | (
                        (KeyboardKey.status == KeyboardKeyStatusEnum.BACK)
                        & (KeyboardKey.branch_id.is_(None))
                        & (KeyboardKey.reply_condition_message_id.is_(None))
                        & (KeyboardKey.parent_key_id.is_not(None))
                    )
                    | (
                        (KeyboardKey.status == KeyboardKeyStatusEnum.DEFERRED)
                        & (KeyboardKey.branch_id.is_(None))
                        & (KeyboardKey.reply_condition_message_id.is_(None))
                        & (user.deferred_field_id is not None)  # type: ignore
                    )
                )
                .where(KeyboardKey.parent_key_id == user.curr_keyboard_key_parent_id)
                .order_by(KeyboardKey.id.asc())
            )
        )
    keyboard_keys_len = len(keyboard_keys)
    if keyboard_keys_len == 0:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        [[key.key for key in keyboard_keys[idx : idx + 2]] for idx in range(0, keyboard_keys_len, 2)]
        if keyboard_keys_len > 2
        else [[key.key] for key in keyboard_keys]
    )
