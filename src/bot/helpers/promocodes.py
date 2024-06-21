from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from telegram.constants import ParseMode

from sqlalchemy import select, update as sql_update

from loguru import logger
from datetime import datetime
from jinja2 import Template

from bot.application import BBApplication
from utils.db_model import (
    Promocode
)
from utils.custom_types import (
    PromocodeStatusEnum
)

from bot.handlers.group import group_send_to_all_superadmin_tasked

async def check_expired_promocodes(context: CallbackContext) -> None:
    """Обновляет просроченные промокоды и уведомляет об этом суперадминистраторов"""
    app: BBApplication = context.application
    settings = await app.provider.settings

    logger.info("Start job to check expired promocodes")

    async with app.provider.db_session() as session:
        expired_promocodes_sel = await session.execute(
            select(Promocode)
            .where(Promocode.expire_at <= datetime.now())
            .where(Promocode.status == PromocodeStatusEnum.ACTIVE)
        )
        expired_promocodes = list(expired_promocodes_sel.scalars())

        if len(expired_promocodes) == 0:
            return logger.info(f"There is no expired promocodes")

        for expired_promocode in expired_promocodes:
            await session.execute(
                sql_update(Promocode)
                .where(Promocode.id == expired_promocode.id)
                .values(status = PromocodeStatusEnum.EXPIRED)
            )

        await group_send_to_all_superadmin_tasked(
            app = app,
            message = Template(settings.expired_promocodes_jinja_template)
                        .render(promocodes = expired_promocodes),
            parse_mode = ParseMode.MARKDOWN
        )

        logger.success(f"Send expired promocodes to superadmin groups")
        
        await session.commit()

async def send_promocodes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Посылает доступные промокоды"""
    app: BBApplication = context.application
    settings = await app.provider.settings

    async with app.provider.db_session() as session:
        promocodes_sel = await session.execute(
            select(Promocode)
            .where(Promocode.status == PromocodeStatusEnum.ACTIVE)
        )
        promocodes = list(promocodes_sel.scalars())
        await update.message.reply_markdown(
            Template(settings.avaliable_promocodes_jinja_template)
            .render(promocodes = promocodes)
        )