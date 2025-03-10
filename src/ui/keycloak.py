from typing import Any

from fastapi import Request
from fastapi.security import OAuth2AuthorizationCodeBearer
from keycloak import KeycloakOpenID
from loguru import logger
from pydantic import BaseModel

KEYCLOAK_ROLE = "ui-user"


class KeycloakUser(BaseModel):
    name: str
    preferred_username: str


class Keycloak:
    """
    Прослойка над Keycloak библиотекой для питона, предназначенная для удобного использования с FastAPI
    """

    def __init__(
        self,
        server_url: str,
        realm_name: str,
        client_id: str,
        client_secret_key: str | None = None,
        verify: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        self.keycloak_openid = KeycloakOpenID(
            server_url=server_url,
            realm_name=realm_name,
            client_id=client_id,
            client_secret_key=client_secret_key,
            verify=verify,
        )
        self.public_key = (
            "-----BEGIN PUBLIC KEY-----\n" + self.keycloak_openid.public_key() + "\n-----END PUBLIC KEY-----"
        )

    def decode_token(self, token: str) -> dict[str, Any]:
        """Декодировать JWT токен в словарь
        Если токен некорретный (истек срок жизни, некорректная подпись и т.п.) - будет поднято исключение
        Запроса к Keycloak при этом не происходит, всё делается локально.
        """
        return self.keycloak_openid.decode_token(token, key=self.public_key)


class OAuth2AuthorizationCodeBearerOrCookie(OAuth2AuthorizationCodeBearer):
    """Расширение стандартной зависимости OAuth2AuthorizationCodeBearer
    При наличии куки Authorization и отсутствии хедера Authorization,
    берет токен из куки.
    """

    async def __call__(self, request: Request) -> str | None:
        authorization_header = request.headers.get("Authorization")
        authorization_cookie = request.cookies.get("Authorization")

        if not authorization_header and authorization_cookie:
            logger.warning("No Authorization header, but cookie found - using Authorization cookie as Bearer token")
            return authorization_cookie
        logger.debug("Using default OAuth2AuthorizationCodeBearer behavior")
        return await super().__call__(request)
