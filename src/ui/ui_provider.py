from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError

from fastapi import Request
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

from ui.ui_keycloak import UIKeycloak

class OAuth2AuthorizationCodeBearerOrCookie(OAuth2AuthorizationCodeBearer):
    """Расширение стандартной зависимости OAuth2AuthorizationCodeBearer
    При наличии куки Authorization и отсутствии хедера Authorization,
    берет токен из куки.
    """

    async def __call__(self, request: Request) -> str | None:
        authorization_header = request.headers.get("Authorization")
        authorization_cookie = request.cookies.get("Authorization")

        if not authorization_header and authorization_cookie:
            logger.info(
                "No Authorization header, but cookie found - using Authorization cookie as Bearer token"
            )
            return authorization_cookie
        else:
            logger.info("Using default OAuth2AuthorizationCodeBearer behavior")
            return await super().__call__(request)


class UIProvider(BBProvider):
    """
    Класс, обеспечивающий работу приложения UI
    """

    def __init__(self) -> None:
        super().__init__()

        self.keycloak = UIKeycloak(
            server_url        = self.config.keycloak.url,
            realm_name        = self.config.keycloak.realm,
            client_id         = self.config.keycloak.client,
            client_secret_key = self.config.keycloak.secret.get_secret_value(),
            verify            = self.config.keycloak.verify
        )
        
        self.oauth2_scheme = OAuth2AuthorizationCodeBearerOrCookie(
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

            first_field_branch = await session.execute(
                insert(FieldBranch).values(
                    key    = settings.first_field_branch,
                    status = FieldBranchStatusEnum.NORMAL,
                    is_ui_editable  = False,
                    is_bot_editable = True,
                    is_deferrable   = False,
                )
            )

            first_field_branch_id: int = first_field_branch.inserted_primary_key.t[0]

            await session.execute(
                insert(Field).values([
                    {
                        "key": settings.user_document_name_field,
                        "status": FieldStatusEnum.NORMAL,
                        "order_place": 0,
                        "branch_id": first_field_branch_id,
                        "question_markdown": settings.user_document_name_field
                    },
                    {
                        "key": settings.user_field_to_request_pass,
                        "status": FieldStatusEnum.NORMAL,
                        "order_place": 1,
                        "branch_id": first_field_branch_id,
                        "question_markdown": settings.user_field_to_request_pass,
                        "is_skippable": True
                    }
                ])
            )

            pass_branch = await session.execute(
                insert(FieldBranch).values(
                    key    = settings.pass_user_field,
                    status = FieldBranchStatusEnum.NORMAL,
                    is_ui_editable  = True,
                    is_bot_editable = False,
                    is_deferrable   = False,
                )
            )

            pass_branch_id: int = pass_branch.inserted_primary_key.t[0]

            await session.execute(
                insert(Field).values(
                    key    = settings.pass_user_field,
                    status = FieldStatusEnum.PERSONAL_NOTIFICATION,
                    order_place = 0,
                    branch_id   = pass_branch_id
                )
            )

            try:
                await session.commit()
                logger.success("FieldBranches and Fields tables with default values...")
            except IntegrityError as err:
                logger.error(err)
                await session.rollback()
                logger.error("Did not initialize FieldBranches and Fields tables...")