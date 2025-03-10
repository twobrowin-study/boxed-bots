from loguru import logger
from sqlalchemy import update
from telegram import Message

from src.bot.exceptions import CouldNotRestoreDeferredFieldError
from src.bot.helpers.fields.keyboards import construct_field_reply_keyboard_markup
from src.bot.helpers.users.registration import update_user_registration_and_send_message
from src.bot.telegram.application import BBApplication
from src.utils.db_model import Settings, User


async def user_defer_field(app: BBApplication, user: User, message: Message, settings: Settings) -> None:
    """
    Отложить заполнение на текущем вопросе

    Сначала сохраняются данные в БД, а затем высылается результат

    Это делается для корректной обрабатки наличия отложенного вопроса при подготовке клавиатуры
    """
    logger.debug(f"User {user.id=} has deferred field {user.curr_field_id=}")
    await update_user_registration_and_send_message(
        app=app,
        user=user,
        message=message,
        text=settings.user_defered_message_plain,
        settings=settings,
        curr_field_id=None,
        curr_reply_message_id=None,
        deferred_field_id=user.curr_field_id,
        deferred_reply_message_id=user.curr_reply_message_id,
    )


async def user_restore_deferred_field(app: BBApplication, user: User, message: Message, settings: Settings) -> None:
    """Восстановить отложенный вопрос"""
    async with app.provider.db_sessionmaker() as session:
        if not user.deferred_field or not user.deferred_field.question_markdown_or_j2_template:
            raise CouldNotRestoreDeferredFieldError

        await message.reply_markdown(
            user.deferred_field.question_markdown_or_j2_template,
            reply_markup=construct_field_reply_keyboard_markup(user.deferred_field, settings, "full_text_answer"),
        )

        logger.debug(f"User {user.id=} has restored deferred field {user.deferred_field_id=}")

        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(
                deferred_field_id=None,
                deferred_reply_message_id=None,
                curr_field_id=user.deferred_field_id,
                curr_reply_message_id=user.deferred_reply_message_id,
            )
        )
        await session.commit()
