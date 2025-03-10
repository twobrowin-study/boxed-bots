from jinja2 import Template
from loguru import logger
from sqlalchemy import select
from telegram import Message

from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import PromocodeStatusEnum
from src.utils.db_model import Promocode, Settings, User


async def send_promocodes(app: BBApplication, user: User, message: Message, settings: Settings) -> None:
    """Посылает доступные промокоды"""
    logger.debug(f"Sending promocodes to user {user.id=}")
    async with app.provider.db_sessionmaker() as session:
        promocodes = list(
            await session.scalars(select(Promocode).where(Promocode.status == PromocodeStatusEnum.ACTIVE))
        )
        await message.reply_markdown(
            await Template(settings.user_avaliable_promocodes_message_j2_template, enable_async=True).render_async(
                promocodes=promocodes
            ),
            reply_markup=await get_user_current_keyboard(app, user),
        )
