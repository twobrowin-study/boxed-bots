from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio.session import AsyncSession

from utils.db_model import (
    User, KeyboardKey,
    Field, FieldBranch,
    ReplyableConditionMessage
)
from utils.custom_types import KeyboardKeyStatusEnum, ReplyTypeEnum

from bot.application import BBApplication
from bot.helpers.replyable_condition_messages import (
    select_awaliable_replyable_condition_messages_by_condition_bool_field_id,
    check_if_reply_condition_message_is_awaliable_by_reply_condition_bool_field_id
)
from bot.callback_constants import (
    UserStartBranchReplyCallback,
    UserFullTextAnswerReplyCallback,
    UserFastAnswerReplyCallback
)

def construct_keyboard_reply(field: Field, app: BBApplication, deferable_key: bool = True, cancel_key: bool = False) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """
    Получить клавиатуру по строке вариантов ответов
    """
    branch: FieldBranch = field.branch

    bottom_buttons = [
        [app.provider.config.i18n.defer] if branch.is_deferrable and deferable_key else [],
        [app.provider.config.i18n.skip] if field.is_skippable and not cancel_key else [],
        [app.provider.config.i18n.cancel] if cancel_key else []
    ]

    if field.answer_options in [None, '']:
        return ReplyKeyboardMarkup(bottom_buttons)

    return ReplyKeyboardMarkup([
        [key] for key in field.answer_options.split('\n')
    ] + bottom_buttons)

async def get_keyboard_of_user(
        session: AsyncSession, user: User,
        always_add_defered_keys: bool = False,
        from_parent_key: KeyboardKey = None,
        to_parent_key: KeyboardKey = None,
    ) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """
    Получить клавиатуру, доступную пользователю
    """
    awaliable_rcm = select_awaliable_replyable_condition_messages_by_condition_bool_field_id(user)
    select_parent_key_id: int|None = None

    if user.curr_keyboard_key_parent_id:
        select_parent_key_id = user.curr_keyboard_key_parent_id

    if from_parent_key:
        child_key_example = await session.scalar(
            select(KeyboardKey.id)
            .where(KeyboardKey.parent_key_id == from_parent_key.id)
        )
        if child_key_example:
            select_parent_key_id = from_parent_key.id
        else:
            select_parent_key_id = from_parent_key.parent_key_id
    
    if to_parent_key:
        select_parent_key_id = to_parent_key.parent_key_id
    
    selected = await session.execute(
        select(KeyboardKey)
        .where(
            (
                (KeyboardKey.status == KeyboardKeyStatusEnum.NORMAL) &
                (KeyboardKey.reply_condition_message_id.in_(awaliable_rcm))
            ) |
            (
                (KeyboardKey.status.in_([
                    KeyboardKeyStatusEnum.ME,
                    KeyboardKeyStatusEnum.ME_CHANGE
                ])) &
                (KeyboardKey.branch_id != None)
            ) |
            (
                (KeyboardKey.status.in_([
                    KeyboardKeyStatusEnum.NEWS,
                    KeyboardKeyStatusEnum.QR,
                    KeyboardKeyStatusEnum.PROMOCODES
                ])) &
                (KeyboardKey.branch_id == None) &
                (KeyboardKey.reply_condition_message_id == None)
            ) |
            (
                (KeyboardKey.status == KeyboardKeyStatusEnum.BACK) &
                (KeyboardKey.branch_id == None) &
                (KeyboardKey.reply_condition_message_id == None) &
                (KeyboardKey.parent_key_id != None)
            ) |
            (
                (KeyboardKey.status == KeyboardKeyStatusEnum.DEFERRED) &
                (KeyboardKey.branch_id == None) &
                (KeyboardKey.reply_condition_message_id == None) &
                (user.deferred_field_id is not None or always_add_defered_keys)
            )
        )
        .where(KeyboardKey.parent_key_id == select_parent_key_id)
        .order_by(KeyboardKey.id.asc())
    )
    keyboard_keys     = list(selected.scalars())
    keyboard_keys_len = len(keyboard_keys)
    if keyboard_keys_len == 0:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        [
            [ key.key for key in keyboard_keys[idx:idx+2] ]
            for idx in range(0,keyboard_keys_len,2)
        ] if keyboard_keys_len > 2 \
            else [
                [ key.key ] for key in keyboard_keys
            ]
    )

async def get_keyboard_key_by_key_text(session: AsyncSession, key: str) -> KeyboardKey | None:
    """
    Получить полный объект кнопки клавиатуры по названию клавиши
    """
    selected = await session.execute(
        select(KeyboardKey)
        .where(KeyboardKey.key == key)
    )
    keyboard_key = selected.scalar_one_or_none()
    return keyboard_key

async def get_awaliable_inline_keyboard_for_user(
    reply_condition_message: ReplyableConditionMessage,
    user: User,
    session: AsyncSession
    ) -> InlineKeyboardMarkup|None:
    """Получить Inline клавиатуру с вариантами ответов для сообщения"""
    
    if not await check_if_reply_condition_message_is_awaliable_by_reply_condition_bool_field_id(
        reply_condition_message, user, session
    ):
        return None
    
    if reply_condition_message.reply_type == ReplyTypeEnum.BRANCH_START:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(
                text=reply_condition_message.reply_keyboard_keys,
                callback_data=UserStartBranchReplyCallback.TEMPLATE.format(
                    reply_message_id=reply_condition_message.id,
                    branch_id=reply_condition_message.reply_answer_field_branch_id
                )
            )
        ]])
    
    if reply_condition_message.reply_type == ReplyTypeEnum.FULL_TEXT_ANSWER:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(
                text=reply_condition_message.reply_keyboard_keys,
                callback_data=UserFullTextAnswerReplyCallback.TEMPLATE.format(
                    reply_message_id=reply_condition_message.id,
                    field_id=reply_condition_message.reply_answer_field_id
                )
            )
        ]])
    
    if reply_condition_message.reply_type == ReplyTypeEnum.FAST_ANSWER:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=answer,
                    callback_data=UserFastAnswerReplyCallback.TEMPLATE.format(
                        reply_message_id=reply_condition_message.id,
                        field_id=reply_condition_message.reply_answer_field_id,
                        answer_idx=answer_idx
                    )
                )
            ]
            for answer_idx,answer in enumerate(reply_condition_message.reply_keyboard_keys.split('\n'))
        ])

    return None