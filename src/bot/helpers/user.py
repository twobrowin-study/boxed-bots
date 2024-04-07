from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy import select, update

from bot.application import BBApplication
from utils.db_model import User

async def user_set_have_banned_bot(app: BBApplication, chat_id: int, have_banned_bot: bool) -> None:
    """
    Установить статус пользователя о бане бота
    """
    async with app.provider.db_session() as session:
        await session.execute(
            update(User).
            where(User.chat_id == chat_id).
            values(have_banned_bot = have_banned_bot)
        )
        await session.commit()

async def get_user_by_chat_id_or_none(session: AsyncSession, chat_id: int) -> User|None:
    """
    Получить пользователя или ничего если пользователя не существует
    """
    selection = await session.execute(
        select(User).where(User.chat_id == chat_id)
    )
    return selection.scalar_one_or_none()