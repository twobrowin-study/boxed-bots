from fastapi import Request
from fastapi.security import OAuth2AuthorizationCodeBearer
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from src.ui.keycloak import Keycloak
from src.utils.bb_provider import BBProvider
from src.utils.custom_types import FieldBranchStatusEnum, FieldStatusEnum, FieldTypeEnum
from src.utils.db_model import (
    Base,
    BotStatus,
    Field,
    FieldBranch,
    Settings,
)


class OAuth2AuthorizationCodeBearerOrCookie(OAuth2AuthorizationCodeBearer):
    """Расширение стандартной зависимости OAuth2AuthorizationCodeBearer
    При наличии куки Authorization и отсутствии хедера Authorization,
    берет токен из куки.
    """

    async def __call__(self, request: Request) -> str | None:
        authorization_header = request.headers.get("Authorization")
        authorization_cookie = request.cookies.get("Authorization")

        if not authorization_header and authorization_cookie:
            logger.debug("No Authorization header, but cookie found - using Authorization cookie as Bearer token")
            return authorization_cookie

        logger.debug("Using default OAuth2AuthorizationCodeBearer behavior")
        return await super().__call__(request)


class Provider(BBProvider):
    """
    Класс, обеспечивающий работу приложения UI
    """

    def __init__(self) -> None:
        super().__init__()

        self.keycloak = Keycloak(
            server_url=self.config.keycloak_url,
            realm_name=self.config.keycloak_realm,
            client_id=self.config.keycloak_client,
            client_secret_key=self.config.keycloak_secret.get_secret_value(),
            verify=self.config.keycloak_verify,
        )

        self.oauth2_scheme = OAuth2AuthorizationCodeBearerOrCookie(
            authorizationUrl=f"{self.config.keycloak_url}/relams/{self.config.keycloak_realm}/protocol/openid-connect/auth",
            tokenUrl=f"{self.config.keycloak_url}/relams/{self.config.keycloak_realm}/protocol/openid-connect/token",
        )

    async def async_init(self) -> None:
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

    async def _async_init_bot_status(self) -> None:
        """
        Внутренняя функция для инициализации статуса бота
        """
        async with self.db_sessionmaker() as session:
            bot_statuses_all = await session.execute(select(BotStatus))
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

    async def _async_init_settings(self) -> None:
        """
        Внутренняя функция для инициализации настроек
        """
        async with self.db_sessionmaker() as session:
            settings_all = await session.execute(select(Settings))
            if settings_all.first():
                logger.success("Settings table already initialized... skipping")
                return

            await session.execute(insert(Settings).values(**(self.config.defaults.model_dump_values())))
            try:
                await session.commit()
                logger.success("Initialized Settings table...")
            except IntegrityError as err:
                logger.error(err)
                await session.rollback()
                logger.error("Did not initialize Settings table with default values...")

    async def _async_init_fields(self) -> None:
        """
        Внутренняя функция для инициализации полей
        """
        async with self.db_sessionmaker() as session:
            settings_all = await session.execute(
                select(FieldBranch, Field).where(Field.branch_id == FieldBranch.id).limit(1)
            )
            if settings_all.first():
                logger.success("FieldBranches and Fields tables already initialized... skipping")
                return

            settings = await self.settings

            user_first_field_branch_plain = await session.execute(
                insert(FieldBranch).values(
                    key=settings.user_first_field_branch_plain,
                    status=FieldBranchStatusEnum.NORMAL,
                    is_ui_editable=False,
                    is_bot_editable=True,
                    is_deferrable=False,
                )
            )

            first_field_branch_inserted_primary_key = user_first_field_branch_plain.inserted_primary_key
            if first_field_branch_inserted_primary_key is None:
                await session.rollback()
                logger.error("Did not initialize First Field Branch table with default values...")
                return

            first_field_branch_id: int = first_field_branch_inserted_primary_key.t[0]

            await session.execute(
                insert(Field).values(
                    [
                        {
                            "key": settings.user_name_field_plain,
                            "status": FieldStatusEnum.NORMAL,
                            "order_place": 1,
                            "branch_id": first_field_branch_id,
                            "question_markdown_or_j2_template": settings.user_name_field_plain,
                            "is_skippable": False,
                        },
                        {
                            "key": settings.user_pass_required_field_plain,
                            "status": FieldStatusEnum.NORMAL,
                            "order_place": 2,
                            "branch_id": first_field_branch_id,
                            "question_markdown_or_j2_template": settings.user_pass_required_field_plain,
                            "is_skippable": True,
                        },
                    ]
                )
            )

            pass_branch = await session.execute(
                insert(FieldBranch).values(
                    key=settings.user_pass_field_plain,
                    status=FieldBranchStatusEnum.NORMAL,
                    is_ui_editable=True,
                    is_bot_editable=False,
                    is_deferrable=False,
                )
            )

            pass_branch_inserted_primary_key = pass_branch.inserted_primary_key
            if pass_branch_inserted_primary_key is None:
                await session.rollback()
                logger.error("Did not initialize Pass Branch table with default values...")
                return

            pass_branch_id: int = pass_branch_inserted_primary_key.t[0]

            await session.execute(
                insert(Field).values(
                    [
                        {
                            "key": settings.user_pass_availability_field_plain,
                            "status": FieldStatusEnum.JINJA2_FROM_USER_ON_CREATE,
                            "type": FieldTypeEnum.BOOLEAN,
                            "order_place": 1,
                            "branch_id": pass_branch_id,
                            "question_markdown_or_j2_template": "true",
                        },
                        {
                            "key": settings.user_pass_field_plain,
                            "status": FieldStatusEnum.PERSONAL_NOTIFICATION,
                            "order_place": 2,
                            "branch_id": pass_branch_id,
                            "question_markdown_or_j2_template": None,
                        },
                    ]
                )
            )

            try:
                await session.commit()
                logger.success("FieldBranches and Fields tables with default values...")
            except IntegrityError as err:
                logger.error(err)
                await session.rollback()
                logger.error("Did not initialize FieldBranches and Fields tables...")

    def prepare_error_prefix(self, idx: str | int, prefix_name: str) -> str:
        return f"{prefix_name} {idx if idx != 'new' else provider.config.i18n.new_record}:"


provider = Provider()
