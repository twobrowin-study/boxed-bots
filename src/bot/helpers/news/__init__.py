from loguru import logger
from sqlalchemy import select
from telegram import Bot

from src.bot.telegram.application import BBApplication
from src.utils.db_model import KeyboardKey, NewsPost, Settings, User


async def reply_news_posts(app: BBApplication, user: User, keyboard_key: KeyboardKey, settings: Settings) -> None:
    """Отправить новостные посты"""
    bot: Bot = app.bot
    logger.debug(f"Sending news post to user {user.id=}")
    async with app.provider.db_sessionmaker() as session:
        news_select = (
            select(NewsPost).order_by(NewsPost.id.desc()).limit(int(settings.user_number_of_last_news_to_show_int))
        )
        if keyboard_key.news_tag:
            news_select = news_select.where(NewsPost.tags.icontains(keyboard_key.news_tag))
        news_posts = list(await session.scalars(news_select))
        for news_post in reversed(news_posts):
            try:
                await bot.forward_message(
                    chat_id=user.chat_id,
                    from_chat_id=news_post.chat_id,
                    message_id=news_post.message_id,
                )
            except Exception:
                logger.warning(f"Was not able to forward message with {news_post.id=}")
