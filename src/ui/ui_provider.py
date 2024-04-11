from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError

from fastapi.security import OAuth2AuthorizationCodeBearer

from loguru import logger

from utils.bb_provider import BBProvider
from utils.db_model import (
    Base,
    Settings,
    BotStatus,
    FieldBranch,
    Field,
)
from utils.custom_types import (
    FieldBranchStatusEnum,
    FieldStatusEnum
)

from ui.api_keycloak import APIKeycloak

class UIProvider(BBProvider):
    """
    Класс, обеспечивающий работу приложения UI
    """

    def __init__(self) -> None:
        super().__init__()

        self.keycloak = APIKeycloak(
            server_url        = self.config.keycloak.url,
            realm_name        = self.config.keycloak.realm,
            client_id         = self.config.keycloak.api_client,
            client_secret_key = self.config.keycloak.api_secret
        )
        
        self.oauth2_scheme = OAuth2AuthorizationCodeBearer(
            authorizationUrl = f"{self.config.keycloak.url}/relams/{self.config.keycloak.realm}/protocol/openid-connect/auth",
            tokenUrl         = f"{self.config.keycloak.url}/relams/{self.config.keycloak.realm}/protocol/openid-connect/token",
        )

    async def async_init(self):
        """
        Асинхронная инциализация
        """
        logger.info("Async initializing...")

        logger.info("Initializing DB...")
        async with self.db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Initializing BotStatus table...")
        await self._async_init_bot_status()

        logger.info("Initializing Settings table...")
        await self._async_init_settings()

        logger.info("Initializing FieldBranches and Fields tables...")
        await self._async_init_fields()

        logger.info("Done async initialize...")
    
    async def _async_init_bot_status(self):
        """
        Внутренняя функция для инициализации статуса бота
        """
        async with self.db_session() as session:
            bot_statuses_all = await session.execute(
                select(BotStatus)
            )
            if bot_statuses_all.first():
                logger.success("BotStatus table already initialized... skipping")
                return

            await session.execute(insert(BotStatus))
            try:
                await session.commit()
                logger.success("Initialized BotStatus table...")
            except IntegrityError as err:
                logger.error(err)
                await session.rollback()
                logger.error("Did not initialize BotStatus table with default values...")
    
    async def _async_init_settings(self):
        """
        Внутренняя функция для инициализации настроек
        """
        async with self.db_session() as session:
            settings_all = await session.execute(
                select(Settings)
            )
            if settings_all.first():
                logger.success("Settings table already initialized... skipping")
                return

            await session.execute(
                insert(Settings).values(
                    **(self.config.defaults.model_dump_values())
                )
            )
            try:
                await session.commit()
                logger.success("Initialized Settings table...")
            except IntegrityError as err:
                logger.error(err)
                await session.rollback()
                logger.error("Did not initialize Settings table with default values...")
    
    async def _async_init_fields(self):
        """
        Внутренняя функция для инициализации полей
        """
        async with self.db_session() as session:
            settings_all = await session.execute(
                select(FieldBranch, Field)
                .where(Field.branch_id == FieldBranch.id)
                .limit(1)
            )
            if settings_all.first():
                logger.success("FieldBranches and Fields tables already initialized... skipping")
                return
            
            settings = await self.settings 

            field_branch_new = await session.execute(
                insert(FieldBranch).values(
                    key    = settings.first_field_branch,
                    status = FieldBranchStatusEnum.NORMAL,
                    is_ui_edditable  = False,
                    is_bot_edditable = True,
                    is_deferrable    = False,
                )
            )

            field_branch_new_id: int = field_branch_new.inserted_primary_key.t[0]

            await session.execute(
                insert(Field).values(
                    key    = settings.user_document_name_field,
                    status = FieldStatusEnum.NORMAL,
                    order_place = 0,
                    branch_id   = field_branch_new_id,
                    question_markdown = settings.user_document_name_field
                )
            )

            try:
                await session.commit()
                logger.success("FieldBranches and Fields tables with default values...")
            except IntegrityError as err:
                logger.error(err)
                await session.rollback()
                logger.error("Did not initialize FieldBranches and Fields tables...")