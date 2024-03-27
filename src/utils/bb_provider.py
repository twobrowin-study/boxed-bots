from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.ext.asyncio.session import AsyncSession

from sqlalchemy import select, Result

from utils.config_model import create_config
from utils.db_model import Settings, BotStatus

from utils.minio_client import MinIOClient

class BBProvider:
    """
    Класс, обеспечивающий работу бота в коробке
    """

    def __init__(self) -> None:
        self.config    = create_config()
        self.db_engine = create_async_engine(
                f"postgresql+asyncpg://{self.config.pg_user}:{self.config.pg_password}@localhost:5432/postgres", 
                echo=False,
                pool_size=10,
                max_overflow=2,
                pool_recycle=300,
                pool_pre_ping=True,
                pool_use_lifo=True
            )
        self.db_session = async_sessionmaker(bind = self.db_engine)
        self.minio = MinIOClient(self.config.minio_root_user, self.config.minio_root_password)
    
    async def _get_kv_object(self, session: AsyncSession, object_class: type[BotStatus|Settings]) -> BotStatus|Settings:
        """
        Получить объект ключ-значение из БД при существующей сессии
        """
        result: Result = await session.execute(
            select(object_class).add_columns(object_class.__table__.columns)
        )
        first: object_class = result.first()
        return first
    
    async def _get_kv_object_create_session(self, object_class: type[BotStatus|Settings]) -> BotStatus|Settings:
        """
        Получить объект ключ-значение из БД с созданием сессии
        """
        async with self.db_session() as session:
            return await self._get_kv_object(session, object_class)
    
    @property
    async def bot_status(self) -> BotStatus:
        """
        Получить текущий статус бота
        """
        return await self._get_kv_object_create_session(BotStatus)
    
    @property
    async def settings(self) -> Settings:
        """
        Получить текущие настройки бота
        """
        return await self._get_kv_object_create_session(Settings)
    
    async def get_bot_status(self, session: AsyncSession) -> BotStatus:
        """
        Получить текущий статус бота с существующей сессией
        """
        return await self._get_kv_object(session, BotStatus)
    
    async def get_settings(self, session: AsyncSession) -> Settings:
        """
        Получить текущие настройки бота с существующей сессией
        """
        return await self._get_kv_object(session, Settings)