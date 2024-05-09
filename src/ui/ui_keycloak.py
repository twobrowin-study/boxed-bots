from typing import Any
from keycloak import KeycloakOpenID

from pydantic import BaseModel

class UIUser(BaseModel, extra="forbid"):
    token: str
    name:  str
    preferred_username: str

class UIKeycloak:
    """
    Прослойка над Keycloak библиотекой для питона, предназначенная для удобного использования с FastAPI
    """

    def __init__(self,
                 server_url: str,
                 realm_name: str,
                 client_id: str,
                 client_secret_key: str|None = None) -> None:
        self.keycloak_openid = KeycloakOpenID(
            server_url=server_url,
            realm_name=realm_name,
            client_id=client_id,
            client_secret_key=client_secret_key
        )
        self.public_key = ("-----BEGIN PUBLIC KEY-----\n" +
                           self.keycloak_openid.public_key() +
                           "\n-----END PUBLIC KEY-----")

    def decode_token(self, token: str) -> dict[str, Any]:
        """Декодировать JWT токен в словарь
        Если токен некорретный (истек срок жизни, некорректная подпись и т.п.) - будет поднято исключение
        Запроса к Keycloak при этом не происходит, всё делается локально.
        """
        return self.keycloak_openid.decode_token(token, key=self.public_key)

    def has_access(self, user: UIUser, permissions: str) -> bool:
        """Проверить, что у токена есть доступ к запрошенным ресурсам

        Примеры строки permissions:
        `Resource A#Scope A`, `Resource A#Scope A, Scope B, Scope C`, `Resource A`, `#Scope A`

        Полное описание происходящего: https://www.keycloak.org/docs/23.0.6/authorization_services/#_service_obtaining_permissions
        """
        auth_status = self.keycloak_openid.has_uma_access(user.token, permissions)
        return auth_status.is_authorized
