from loguru import logger
from sqlalchemy import select, update
from telegram import Message

from src.bot.exceptions import CouldNotSaveUserKeyboardKeyHitError
from src.bot.helpers.fields.deferred import user_restore_deferred_field
from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.news import reply_news_posts
from src.bot.helpers.promocodes import send_promocodes
from src.bot.helpers.replyable_condition_messages.sends import send_replyable_condition_message_to_user
from src.bot.helpers.telegram import shrink_text_up_to_80_symbols
from src.bot.helpers.users.me_information import user_send_me_information
from src.bot.helpers.users.passes import user_send_pass_information
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import KeyboardKeyStatusEnum
from src.utils.db_model import KeyboardKey, Settings, User


async def reply_keyboard_key_hit(app: BBApplication, user: User, message: Message, settings: Settings) -> None:
    """
    Обработать нажатие клавиатуры пользователя

    Содержит обработку нажатий на кнопки меню и возврата на меню выше, а затем - выполняет действие

    Сначала сохраняются данные в БД, а затем обрабатывается нажатие на клавиатуру

    Это делается для корректной обрабатки подменю при подготовке клавиатуры
    """
    log_message_text = shrink_text_up_to_80_symbols(message.text)
    async with app.provider.db_sessionmaker() as session:
        keyboard_key = await session.scalar(select(KeyboardKey).where(KeyboardKey.key == message.text))

        if not keyboard_key:
            logger.debug(f"User {user.chat_id=} hit unknown key with text {log_message_text}")
            return

        logger.debug(f"Got keyboard key hit {keyboard_key.id=} from user {user.id=}")

        updated_user = await session.scalar(
            update(User)
            .where(User.id == user.id)
            .values(curr_keyboard_key_parent_id=await _get_next_parent_keyboard_key(app, keyboard_key))
            .returning(User)
        )
        if not updated_user:
            raise CouldNotSaveUserKeyboardKeyHitError

        session.expunge_all()
        await session.commit()

    await _perform_key_hit_action(app, updated_user, keyboard_key, message, settings)


async def _get_next_parent_keyboard_key(app: BBApplication, keyboard_key: KeyboardKey) -> int | None:
    """
    Получить значение родительской кнопки пользователя

    Если нажата кнопка возврата - перейти выше

    Если кнопка имеет дочерние - перейти ниже

    Если кнопка не имеет дочерних - остаться на том же уровне
    """
    async with app.provider.db_sessionmaker() as session:
        if keyboard_key.status == KeyboardKeyStatusEnum.BACK:
            parent_keyboard_key = await session.scalar(
                select(KeyboardKey).where(KeyboardKey.id == keyboard_key.parent_key_id)
            )
            return parent_keyboard_key.parent_key_id if parent_keyboard_key else None

        keyboard_key_child = await session.scalar(
            select(KeyboardKey).where(KeyboardKey.parent_key_id == keyboard_key.id).limit(1)
        )
        if keyboard_key_child is not None:
            return keyboard_key.id

        return keyboard_key.parent_key_id


async def _perform_key_hit_action(
    app: BBApplication, user: User, keyboard_key: KeyboardKey, message: Message, settings: Settings
) -> None:
    """Обработать событие нажатия на клавиатуру"""
    if keyboard_key.status == KeyboardKeyStatusEnum.NORMAL and keyboard_key.reply_condition_message:
        await send_replyable_condition_message_to_user(app, user, keyboard_key.reply_condition_message)

    elif keyboard_key.status == KeyboardKeyStatusEnum.BACK:
        await message.reply_markdown(keyboard_key.key, reply_markup=await get_user_current_keyboard(app, user))

    elif keyboard_key.status == KeyboardKeyStatusEnum.DEFERRED:
        await user_restore_deferred_field(app, user, message, settings)

    elif keyboard_key.status == KeyboardKeyStatusEnum.NEWS:
        await reply_news_posts(app, user, keyboard_key, settings)

    elif keyboard_key.status == KeyboardKeyStatusEnum.PROMOCODES:
        await send_promocodes(app, user, message, settings)

    elif keyboard_key.status == KeyboardKeyStatusEnum.ME:
        await user_send_me_information(app, user, keyboard_key.branch_id, message, "me_plain")

    elif keyboard_key.status == KeyboardKeyStatusEnum.ME_CHANGE:
        await user_send_me_information(app, user, keyboard_key.branch_id, message, "me_change")

    elif keyboard_key.status == KeyboardKeyStatusEnum.PASS:
        await user_send_pass_information(app, user, message, settings)

    else:
        logger.warning(f"Unknown state of keyboard key {keyboard_key.id=} send by user {user.chat_id=}")
