from datetime import datetime

from jinja2 import Template
from loguru import logger
from sqlalchemy import select
from sqlalchemy import update as sql_update
from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from src.bot.telegram.application import BBApplication
from src.utils.custom_types import GroupStatusEnum, PromocodeStatusEnum
from src.utils.db_model import Group, Promocode


async def job(context: CallbackContext) -> None:  # type: ignore
    """Обновляет просроченные промокоды и уведомляет об этом администраторам"""
    app: BBApplication = context.application  # type: ignore
    bot: Bot = app.bot
    settings = await app.provider.settings

    logger.debug("Start check expired promocodes")

    async with app.provider.db_sessionmaker() as session:
        expired_promocodes = list(
            await session.scalars(
                select(Promocode)
                .where(Promocode.expire_at <= datetime.now())  # noqa: DTZ005
                .where(Promocode.status == PromocodeStatusEnum.ACTIVE)
            )
        )

        if not expired_promocodes:
            logger.debug("There is no expired promocodes")
            return

        await session.execute(
            sql_update(Promocode)
            .where(Promocode.id.in_([expired_promocode.id for expired_promocode in expired_promocodes]))
            .values(status=PromocodeStatusEnum.EXPIRED)
        )

        admin_groups = await session.scalars(
            select(Group).where(Group.status.in_([GroupStatusEnum.ADMIN, GroupStatusEnum.SUPER_ADMIN]))
        )

        logger.debug("Sending messages about expired promocodes to admins")

        message = await Template(
            settings.group_superadmin_expired_promocodes_message_j2_template, enable_async=True
        ).render_async(promocodes=expired_promocodes)

        for admin_group in admin_groups:
            await bot.send_message(chat_id=admin_group.chat_id, text=message, parse_mode=ParseMode.MARKDOWN)

        logger.success("Send expired promocodes to superadmin groups")

        await session.commit()

    logger.debug("Done check expired promocodes")
