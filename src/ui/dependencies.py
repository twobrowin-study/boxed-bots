from typing import Annotated

from fastapi import Depends
from fastapi.exceptions import HTTPException
from loguru import logger
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from src.ui.keycloak import KeycloakUser
from src.ui.provider import provider


async def verify_token(token: Annotated[str, Depends(provider.oauth2_scheme)]) -> str:
    """Убедиться в корректности токена"""
    try:
        provider.keycloak.decode_token(token)
    except Exception as e:
        logger.debug(f"Bearer token could not be verified: {e}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=f"Bearer token could not be verified: {e}",
        ) from e
    return token


async def get_user(token: Annotated[str, Depends(verify_token)]) -> KeycloakUser:
    """Декодировать содержимое токена в Pydantic модель"""
    data = provider.keycloak.decode_token(token)
    user = KeycloakUser(**data)
    logger.debug(f"User authenticated as: '{user.preferred_username}'")
    return user


class RequireRoles:
    """Dependency для FastAPI, проверяющая, что у пользователя есть запрошенные роли
    Запроса к Keycloak не делается, информация берется из токена
    """

    def __init__(self, roles: list[str]) -> None:
        self.roles = roles

    async def __call__(
        self,
        token: Annotated[str, Depends(verify_token)],
        user: Annotated[KeycloakUser, Depends(get_user)],
    ) -> None:
        logger.debug(f"Checking if user '{user.preferred_username}' has roles: '{self.roles}'")
        token_data = provider.keycloak.decode_token(token)

        required_roles = self.roles
        realm_roles: list[str] = token_data.get("realm_access", {}).get("roles", [])
        client_roles: list[str] = (
            token_data.get("resource_access", {}).get(provider.config.keycloak_client, {}).get("roles", [])
        )

        if not set(required_roles).issubset(set(realm_roles + client_roles)):
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Resource forbidden")
