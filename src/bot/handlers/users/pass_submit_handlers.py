from jinja2 import Template
from sqlalchemy import select
from telegram import Bot, ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from src.bot.exceptions import PassFieldToChangeNoQuestionError, PassFieldToChangeNotFoundError
from src.bot.helpers.fields.keyboards import construct_field_reply_keyboard_markup
from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.users import (
    get_user_callback_query_data_send_strange_error_and_rise,
    get_user_message_data_send_strange_error_and_rise,
)
from src.bot.helpers.users.passes import user_send_pass_information
from src.bot.helpers.users.registration import update_user_registration_and_send_message
from src.bot.telegram.callback_constants import UserChangePassFieldCallback, UserSubmitPassCallback
from src.utils.custom_types import GroupStatusEnum, PassSubmitStatusEnum
from src.utils.db_model import Field, Group, UserFieldValue


async def start_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает нажатие на кнопку начала подтверждения заявки на пропуск"""
    handler = "pass submit"

    (
        app,
        user,
        _,
        callback_query_message,
        settings,
    ) = await get_user_callback_query_data_send_strange_error_and_rise(update, context, handler)

    async with app.provider.db_sessionmaker() as session:
        user_pass_required_field_value = await session.scalar(
            select(UserFieldValue)
            .where(Field.key == settings.user_pass_required_field_plain)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.field_id == Field.id)
        )
        user_pass_availability_field_value = await session.scalar(
            select(UserFieldValue)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.field_id == Field.id)
            .where(Field.key == settings.user_pass_availability_field_plain)
        )

    # Пользователь уже запросил пропуск или уже его получил или не имеет возможности его запросить
    if (
        user.pass_status != PassSubmitStatusEnum.NOT_SUBMITED
        or not user_pass_availability_field_value
        or user_pass_availability_field_value.value != "true"
    ):
        await user_send_pass_information(app, user, callback_query_message, settings)
        return ConversationHandler.END

    # У пользователя не заполнено необходимое поле для запроса пропуска
    if not user_pass_required_field_value:
        await callback_query_message.reply_markdown(
            settings.user_pass_add_request_field_value_message_plain,
            reply_markup=await get_user_current_keyboard(app, user),
        )
        return ConversationHandler.END

    # Отправка сообщения с заявкой на пропуск
    await callback_query_message.reply_markdown(
        settings.user_pass_submit_message_plain,
        reply_markup=ReplyKeyboardMarkup(
            [
                [settings.user_pass_confirm_button_plain],
                [settings.user_or_group_cancel_button_plain],
            ]
        ),
    )
    return UserSubmitPassCallback.STATE_SUBMIT_AWAIT


async def approve_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка нажатия на кнопки подтверждения или отказа отправки заявки на пропуск"""
    app, user, message, settings = await get_user_message_data_send_strange_error_and_rise(
        update, context, handler="pass submit/cancel approve"
    )
    bot: Bot = app.bot

    # Отказ отправки заявки на пропуск в случае нажатия на кнопку или ввода произвольного текста
    if (
        message.text == settings.user_or_group_cancel_button_plain
        or message.text != settings.user_pass_confirm_button_plain
    ):
        await message.reply_markdown(
            settings.user_pass_submit_canceled_message_plain,
            reply_markup=await get_user_current_keyboard(app, user),
        )
        return ConversationHandler.END

    # Сохранение заявки на пропуск
    await update_user_registration_and_send_message(
        app=app,
        user=user,
        message=message,
        text=settings.user_pass_submitted_message_plain,
        settings=settings,
        pass_status=PassSubmitStatusEnum.SUBMITED,
    )

    # Отправка всем администраторам данных о запросе пропуска
    async with app.provider.db_sessionmaker() as session:
        admin_groups = await session.scalars(
            select(Group).where(Group.status.in_([GroupStatusEnum.ADMIN, GroupStatusEnum.SUPER_ADMIN]))
        )
    admin_group_text = await Template(
        settings.group_superadmin_pass_submited_superadmin_message_j2_template, enable_async=True
    ).render_async(user=user.to_plain_dict())
    admin_group_reply_keyboard = ReplyKeyboardMarkup(
        [
            [settings.group_superadmin_pass_download_submited_button_plain],
            [settings.group_superadmin_pass_send_approved_button_plain],
        ]
    )

    for admin_group in admin_groups:
        await bot.send_message(
            chat_id=admin_group.chat_id,
            text=admin_group_text,
            reply_markup=admin_group_reply_keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )
    return ConversationHandler.END


async def change_field_value_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку изменения значения поля, необходимого для получения пропуска"""
    handler = "pass user field value change"

    (
        app,
        user,
        callback_query_data,
        callback_query_message,
        settings,
    ) = await get_user_callback_query_data_send_strange_error_and_rise(update, context, handler)

    changing_field_id = int(callback_query_data.removeprefix(UserChangePassFieldCallback.PREFIX))

    async with app.provider.db_sessionmaker() as session:
        changing_field = await session.scalar(select(Field).where(Field.id == changing_field_id))
        if not changing_field:
            raise PassFieldToChangeNotFoundError
        if not changing_field.question_markdown_or_j2_template:
            raise PassFieldToChangeNoQuestionError

    await update_user_registration_and_send_message(
        app=app,
        user=user,
        message=callback_query_message,
        text=changing_field.question_markdown_or_j2_template,
        settings=settings,
        reply_keyboad_override=construct_field_reply_keyboard_markup(
            changing_field, settings, "change_user_field_value"
        ),
        curr_field_id=changing_field.id,
        change_field_message_id=callback_query_message.id,
        pass_field_change=True,
    )
