from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.utils.config_model import create_config
from src.utils.db_model import BotStatus, Settings
from src.utils.exceptions import NoBotStatusError, NoSettingsError
from src.utils.minio_client import MinIOClient


class BBProvider:
    """
    Класс, обеспечивающий работу бота в коробке
    """

    def __init__(self) -> None:
        self.config = create_config()
        self.db_engine = create_async_engine(
            f"postgresql+asyncpg://{self.config.postgres_user}:{self.config.postgres_password.get_secret_value()}@{self.config.postgres_host}/{self.config.postgres_db}",
            echo=False,
            pool_size=10,
            max_overflow=2,
            pool_recycle=300,
            pool_pre_ping=True,
            pool_use_lifo=True,
        )
        self.db_sessionmaker = async_sessionmaker(bind=self.db_engine)
        self.minio = MinIOClient(
            self.config.minio_host,
            self.config.minio_secure,
            self.config.minio_access_key,
            self.config.minio_secret_key.get_secret_value(),
        )
        self.tz = ZoneInfo(self.config.tz)

    @property
    async def bot_status(self) -> BotStatus:
        """Получить текущий статус бота"""
        async with self.db_sessionmaker() as session:
            bot_status = await session.scalar(select(BotStatus).limit(1))
            if not bot_status:
                raise NoBotStatusError
        return bot_status

    @property
    async def settings(self) -> Settings:
        """Получить текущие настройки бота"""
        async with self.db_sessionmaker() as session:
            bot_status = await session.scalar(select(Settings).limit(1))
            if not bot_status:
                raise NoSettingsError
        return bot_status
