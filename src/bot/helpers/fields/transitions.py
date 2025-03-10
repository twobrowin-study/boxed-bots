from jinja2 import Template
from loguru import logger
from sqlalchemy import Column, select
from telegram import Bot, Message
from telegram.constants import ParseMode

from src.bot.exceptions import (
    CouldNotSendNextFieldQuestionError,
    CouldNotSendReplyMessageReplyStatusRepliesError,
    FirstFieldOfBranchNotFoundError,
    UserAfterChangeNotFoundError,
)
from src.bot.helpers.fields.keyboards import construct_field_reply_keyboard_markup
from src.bot.helpers.fields.values.prepare import user_prepare_field_value_or_answer_type_validation_error
from src.bot.helpers.fields.values.upsert import (
    upload_telegram_file_to_minio,
    user_upsert_field_value_and_return_file_to_save,
)
from src.bot.helpers.users.me_information import prepare_me_information_message_documents_photos_text_and_reply_keyboard
from src.bot.helpers.users.passes import construct_pass_submit_inline_keyboard
from src.bot.helpers.users.registration import update_user_registration_and_send_message
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import FieldStatusEnum, FieldTypeEnum, ReplyTypeEnum
from src.utils.db_model import Field, FieldBranch, Settings, User


async def get_first_field_of_branch(app: BBApplication, field_branch_key: str) -> Field:
    """
    Получить первое пользовательское поле, который нужно задать пользователю при регистрации
    """
    async with app.provider.db_sessionmaker() as session:
        field = await session.scalar(
            select(Field)
            .where(FieldBranch.key == field_branch_key)
            .where(Field.branch_id == FieldBranch.id)
            .order_by(Field.order_place.asc())
            .limit(1)
        )
        if not field:
            raise FirstFieldOfBranchNotFoundError
        return field


async def user_upsert_field_value_and_send_next_question_or_final(
    app: BBApplication, user: User, field: Field, message: Message, settings: Settings
) -> None:
    """
    Сохранить переданное значение поля пользователя и выслать следующий вопрос или финал пользовательских ответов

    Если пользователь ответил на все вопросы - активировать его и отправить сообщение об успешной регистрации

    Если пользователь отвечает на полнотекстовый вопрос - отправить финальное сообщение

    Если пользователь отвечает на все вопросы ветки вопросов по кнопке - отправить финальное сообщение

    Если пользователь отправил файл для вопроса, то он будет сохранён после ответа пользователю
    """
    # Подготовить значение поля
    field_value = await user_prepare_field_value_or_answer_type_validation_error(app, user, field, message, settings)
    if not field_value:
        return

    # Сохранить значение поля в БД
    file = await user_upsert_field_value_and_return_file_to_save(app, user, field, message, field_value, settings)

    # Обновить пользователя
    await user_set_next_field_and_send_next_question_or_final(app, user, field, message, settings)

    # Сохранить файл  если он был отправлен
    if file:
        await upload_telegram_file_to_minio(app, user, field, file, settings)


async def user_upsert_changed_field_value_and_send_complete(
    app: BBApplication, user: User, field: Field, message: Message, settings: Settings
) -> None:
    """
    Сохранить переданное значение изменяемого поля пользователя и выслать подтверждение об изменении

    Также пытается изменить сообщение и клавиатуру этого сообщения
    """
    # Подготовить значение поля
    field_value = await user_prepare_field_value_or_answer_type_validation_error(app, user, field, message, settings)
    if not field_value:
        return

    # Сохранить значение поля в БД
    file = await user_upsert_field_value_and_return_file_to_save(app, user, field, message, field_value, settings)

    # Обновить пользователя и выслать подтверждение об изменении поля
    changed_field_text = await Template(settings.user_change_reply_message_j2_template, enable_async=True).render_async(
        state=field.key
    )
    await update_user_registration_and_send_message(
        app=app,
        user=user,
        message=message,
        text=changed_field_text,
        settings=settings,
        curr_field_id=None,
        change_field_message_id=None,
        pass_field_change=False,
    )

    # Сохранить файл  если он был отправлен
    if file:
        await upload_telegram_file_to_minio(app, user, field, file, settings)

    # Обновление текста и клавиатуры сообщения с данными пользователя
    try:
        await _change_user_information_on_change_message(app, user, field, settings)
    except Exception as e:
        logger.warning(
            f"Was not able to update message {user.change_field_message_id=} for user {user.id=} after field {field.id=} change with {user.pass_field_change=} for error {e}"
        )


async def _change_user_information_on_change_message(
    app: BBApplication, user: User, field: Field, settings: Settings
) -> None:
    """Обновить текст и клавиатуру сообщения с данными пользователя после изменения значений"""
    bot: Bot = app.bot

    # Изменение было при формировании запроса на пропуск, следует обновить клавиатуру
    if user.pass_field_change:
        await bot.edit_message_reply_markup(
            user.chat_id,
            user.change_field_message_id,
            reply_markup=await construct_pass_submit_inline_keyboard(app, user, settings),
        )
        return

    # Полное обновление текста сообщения вместе с клавиатурой
    field_branch_id: Column[int | None] = field.branch_id  # type: ignore

    async with app.provider.db_sessionmaker() as session:
        updated_user = await session.scalar(select(User).where(User.id == user.id))
        if not updated_user:
            raise UserAfterChangeNotFoundError

    _, message_text, reply_keyboard = await prepare_me_information_message_documents_photos_text_and_reply_keyboard(
        app, updated_user, field_branch_id
    )

    await bot.edit_message_text(
        chat_id=user.chat_id,
        message_id=user.change_field_message_id,
        text=message_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_keyboard,
    )


async def user_set_next_field_and_send_next_question_or_final(
    app: BBApplication, user: User, field: Field, message: Message, settings: Settings
) -> None:
    """
    Усвоить пользователю следующее поле и отправить вопрос этого поля или финал пользовательских ответов

    Если пользователь ответил на все вопросы - активировать его и отправить сообщение об успешной регистрации

    Если пользователь отвечает на полнотекстовый вопрос - отправить финальное сообщение

    Если пользователь отвечает на все вопросы ветки вопросов по кнопке - отправить финальное сообщение
    """
    next_field = await _user_get_next_field(app, user, field)

    # Если есть следующее поле - выслать это поле
    if next_field:
        if not next_field.question_markdown_or_j2_template:
            raise CouldNotSendNextFieldQuestionError
        await update_user_registration_and_send_message(
            app=app,
            user=user,
            message=message,
            text=next_field.question_markdown_or_j2_template,
            settings=settings,
            reply_keyboad_override=construct_field_reply_keyboard_markup(next_field, settings, "full_text_answer"),
            curr_field_id=next_field.id,
        )
        return

    # Если пользователь отвечал на сообщение и нет следующего поля -
    #   удаляем контекст ответа на сообщение и отправляем сообщение об окончании заполнения
    #  1. Если это был ответ на ветку вопросов - то значит что ветка окончена
    #  2. Если это был ответ на один вопрос - то следуюшего поля и не будет
    if user.curr_reply_message and not next_field:
        if not user.curr_reply_message.reply_status_replies:
            raise CouldNotSendReplyMessageReplyStatusRepliesError
        await update_user_registration_and_send_message(
            app=app,
            user=user,
            message=message,
            text=user.curr_reply_message.reply_status_replies,
            settings=settings,
            curr_field_id=None,
            curr_reply_message_id=None,
        )
        return

    # Если нет следующего поля (и пользователь не отвечал на сообщение) - выслать оповещение об успешной регистрации
    if not next_field:
        await update_user_registration_and_send_message(
            app=app,
            user=user,
            message=message,
            text=settings.user_registration_complete_message_plain,
            settings=settings,
            curr_field_id=None,
        )
        return


async def _user_get_next_field(app: BBApplication, user: User, field: Field) -> Field | None:
    """
    Получить следующий вопрос в той же ветке или первый вопрос следующей ветке если она есть для пользователя

    Если пользователь отвечал на полнотекстовый вопрос - следующее поле не высылается
    """
    if user.curr_reply_message and user.curr_reply_message.reply_type == ReplyTypeEnum.FULL_TEXT_ANSWER:
        return None

    async with app.provider.db_sessionmaker() as session:
        next_field = await session.scalar(
            select(Field)
            .where(Field.branch_id == field.branch_id)
            .where(Field.order_place > field.order_place)
            .where(Field.status == FieldStatusEnum.NORMAL)
            .where(Field.type != FieldTypeEnum.BOOLEAN)
            .order_by(Field.order_place.asc())
            .limit(1)
        )
        if next_field:
            return next_field

        next_branch = await session.scalar(select(FieldBranch).where(FieldBranch.id == field.branch.next_branch_id))
        if next_branch:
            return await get_first_field_of_branch(app, next_branch.key)

        return None
