from jinja2 import Template
from loguru import logger
from sqlalchemy import select, update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.exceptions import NoFieldToRequestPassIsFoundError, NoPassFieldIsFoundError
from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.telegram.prepare_field_file_value_and_type import prepare_field_file_value_and_type
from src.bot.helpers.telegram.send_message_and_return_file_id import send_message_and_return_file_id
from src.bot.telegram.application import BBApplication
from src.bot.telegram.callback_constants import UserChangePassFieldCallback, UserSubmitPassCallback
from src.utils.custom_types import PassSubmitStatusEnum
from src.utils.db_model import Field, Settings, User, UserFieldValue


async def user_send_pass_information(app: BBApplication, user: User, message: Message, settings: Settings) -> None:
    """Выслать пользователю ткущий статус пропуска"""
    logger.debug(f"Sending pass status info to user {user.id=}")

    async with app.provider.db_sessionmaker() as session:
        user_pass_availability_field_value = await session.scalar(
            select(UserFieldValue)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.field_id == Field.id)
            .where(Field.key == settings.user_pass_availability_field_plain)
        )

    if not user_pass_availability_field_value or user_pass_availability_field_value.value != "true":
        await message.reply_markdown(
            text=settings.user_pass_unavailable_message_plain, reply_markup=await get_user_current_keyboard(app, user)
        )
        return

    if user.pass_status == PassSubmitStatusEnum.NOT_SUBMITED:
        await message.reply_markdown(
            settings.user_pass_hint_message_plain,
            reply_markup=await construct_pass_submit_inline_keyboard(app, user, settings),
        )
        return

    if user.pass_status == PassSubmitStatusEnum.SUBMITED:
        await message.reply_markdown(
            text=settings.user_pass_submitted_message_plain, reply_markup=await get_user_current_keyboard(app, user)
        )
        return

    if user.pass_status == PassSubmitStatusEnum.APPROVED:
        await _send_approved_pass(app, user, settings)
        return


async def construct_pass_submit_inline_keyboard(
    app: BBApplication, user: User, settings: Settings
) -> InlineKeyboardMarkup:
    async with app.provider.db_sessionmaker() as session:
        field_to_request_pass = await session.scalar(
            select(Field).where(Field.key == settings.user_pass_required_field_plain)
        )
        if not field_to_request_pass:
            raise NoFieldToRequestPassIsFoundError

        user_pass_required_field_value = await session.scalar(
            select(UserFieldValue)
            .where(Field.key == settings.user_pass_required_field_plain)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.field_id == Field.id)
        )
    field_to_request_pass_action = (
        app.provider.config.i18n.change if user_pass_required_field_value else app.provider.config.i18n.append
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=f"{field_to_request_pass_action} {field_to_request_pass.key}",
                    callback_data=UserChangePassFieldCallback.TEMPLATE.format(field_id=field_to_request_pass.id),
                )
            ],
            [
                InlineKeyboardButton(
                    text=settings.user_pass_submit_button_plain,
                    callback_data=UserSubmitPassCallback.PATTERN,
                )
            ],
        ]
    )


async def _send_approved_pass(app: BBApplication, user: User, settings: Settings) -> None:
    async with app.provider.db_sessionmaker() as session:
        pass_field = await session.scalar(select(Field).where(Field.key == settings.user_pass_field_plain).limit(1))
        if not pass_field:
            raise NoPassFieldIsFoundError

        pass_user_field_value = await session.scalar(
            select(UserFieldValue)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.field_id == pass_field.id)
            .limit(1)
        )

        if pass_user_field_value:
            file, file_type = await prepare_field_file_value_and_type(app, pass_field, pass_user_field_value)
        else:
            file = None
            file_type = None

        message_text = await Template(settings.user_pass_message_j2_template, enable_async=True).render_async(
            user=user.to_plain_dict()
        )

        file_id = await send_message_and_return_file_id(
            app=app,
            user=user,
            text=message_text,
            file=file,
            file_type=file_type,
            filename=pass_user_field_value.value if pass_user_field_value else None,
        )

        if pass_user_field_value and file_id and type(file) is not str:
            await session.execute(
                update(UserFieldValue)
                .where(UserFieldValue.id == pass_user_field_value.id)
                .values(value_file_id=file_id)
            )

        await session.commit()
