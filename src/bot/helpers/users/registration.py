from typing import Any

from jinja2 import Template
from loguru import logger
from sqlalchemy import func, select, update
from telegram import Bot, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode

from src.bot.exceptions import CouldNotUpdateUserRegistrationError
from src.bot.helpers.fields.values.calculate import user_calculate_after_registration_fields
from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import GroupStatusEnum, UserStatusEnum
from src.utils.db_model import Group, Settings, User


async def update_user_registration_and_send_message(
    app: BBApplication,
    user: User,
    message: Message,
    text: str,
    settings: Settings,
    reply_keyboad_override: ReplyKeyboardRemove | ReplyKeyboardMarkup | InlineKeyboardMarkup | None = None,
    **user_update_values: Any,
) -> None:
    """Обновить запись пользователя и выслать сообщение"""
    async with app.provider.db_sessionmaker() as session:
        # Пользователь закончил регистрацию если:
        #  1. Он не активен
        #  2. Нет следующего поля
        #  3. Нет сообщения, на котое он отвечал бы
        if (
            user.status == UserStatusEnum.INACTIVE
            and not user_update_values.get("curr_field_id")
            and not user.curr_reply_message
        ):
            user_update_values["status"] = UserStatusEnum.ACTIVE
            logger.debug(f"Activating user {user.id=}")

        updated_user = await session.scalar(
            update(User).where(User.id == user.id).values(**user_update_values).returning(User)
        )
        if not updated_user:
            raise CouldNotUpdateUserRegistrationError

        reply_markup = reply_keyboad_override or await get_user_current_keyboard(app, updated_user)
        await message.reply_markdown(text, reply_markup=reply_markup)

        # Расчитать поля пользователя если он закончил регистрацию или был удалён контекст ответа на вопрос
        if (
            user_update_values.get("status") == UserStatusEnum.ACTIVE
            or user_update_values.get("curr_reply_message_id", -1) is None
            or user_update_values.get("change_field_message_id", -1) is None
        ):
            await user_calculate_after_registration_fields(app, updated_user)

        await session.commit()

    # Посчитать количество зарегистрированных пользователей если пользователь был активирован
    if user_update_values.get("status") == UserStatusEnum.ACTIVE:
        await _count_registered_users_and_send_message_to_all_admins(app, settings)


async def _count_registered_users_and_send_message_to_all_admins(app: BBApplication, settings: Settings) -> None:
    """Посчитать количество зарегистрированных пользователей и выслать сообщение всем администраторм"""
    bot: Bot = app.bot
    async with app.provider.db_sessionmaker() as session:
        user_count = await session.scalar(select(func.count()).where(User.status == UserStatusEnum.ACTIVE))
        if user_count and user_count % int(settings.group_admin_report_every_x_active_users_int) == 0:
            logger.debug(f"Performing admins notification about counted users {user_count=}")
            admin_groups = await session.scalars(
                select(Group).where(Group.status.in_([GroupStatusEnum.ADMIN, GroupStatusEnum.SUPER_ADMIN]))
            )
            admin_group_text = await Template(
                settings.group_admin_report_currently_active_users_message_j2_template, enable_async=True
            ).render_async(count=user_count)
            for admin_group in admin_groups:
                await bot.send_message(
                    chat_id=admin_group.chat_id, text=admin_group_text, parse_mode=ParseMode.MARKDOWN
                )
