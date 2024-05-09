import uuid
from fastapi import Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

import jwcrypto.jwt
from typing import Annotated
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from loguru import logger

from ui.ui_keycloak import UIUser
from ui.setup import provider, app

LOGIN_URL  = f"{provider.config.path_prefix}/login"
LOGOUT_URL = f"{provider.config.path_prefix}/logout"

post_login_redirects: dict[str, str] = {}

async def verify_token(token: Annotated[str, Depends(provider.oauth2_scheme)]) -> UIUser:
    """
    Убедиться в корректности токена
    """
    logger.info(f"Received Bearer token with request")
    try:
        user_dict = provider.keycloak.decode_token(token)
        user = UIUser(
            token = token,
            name  = user_dict['name'],
            preferred_username = user_dict['preferred_username'],
        )
        logger.success(f"Request from user {user.preferred_username}")
        return user
    except jwcrypto.jwt.JWTInvalidClaimValue as e:
        msg = f"User does not have permission: {e}"
        logger.info(msg)
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=msg)
    except Exception as e:
        logger.info(f"Bearer token could not be verified: {e}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=f"Bearer token could not be verified: {e}")

@app.exception_handler(HTTPException)
async def handle_httpexception(request: Request, e: HTTPException):
    """Перенаправляет неавторизованного пользователя на страницу авторизации"""
    if e.status_code == HTTP_401_UNAUTHORIZED:
        return redirect_to_login(request)
    return PlainTextResponse(str(e), status_code=e.status_code)

def redirect_to_login(request: Request, redirect_url: str|None = None) -> RedirectResponse:
    """Перенаправляет неавторизованного пользователя в Keycloak"""
    logger.info("Redirecting anauthorized user to Keycloak")

    # Запоминаем URL, на который пытался попасть пользователь,
    # чтобы после логина перенаправить его обратно
    state = str(uuid.uuid4())
    post_login_redirects[state] = redirect_url or str(request.url)

    auth_url = provider.keycloak.keycloak_openid.auth_url(
        redirect_uri=f"{str(request.base_url)}/{LOGIN_URL}",
        scope="openid profile email",
        state=state,
    )
    return RedirectResponse(auth_url)

@app.get(LOGIN_URL)
async def login_response(code: str, state: str, request: Request) -> RedirectResponse:
    """Эндпоинт, в который перенаправит Keycloak после аутентификации
    Сохраняет access_token в куки и перенаправляет пользователя туда, куда он хотел попасть
    """
    logger.info("User authenticated - requesting token from Keycloak")
    auth_response = provider.keycloak.keycloak_openid.token(
        grant_type="authorization_code",
        code=code,
        redirect_uri=f"{str(request.base_url)}/{LOGIN_URL}",
    )

    post_login_redirect = post_login_redirects.pop(state)

    logger.info(
        f"Got token from Keycloak - setting a cookie and redirecting user to {post_login_redirect}"
    )

    response = RedirectResponse(post_login_redirect)
    response.set_cookie(
        key="Authorization",
        value=auth_response["access_token"],
        expires=int(auth_response["expires_in"]),
        secure=True
    )
    response.set_cookie(
        key="RefreshToken",
        value=auth_response["refresh_token"],
        expires=int(auth_response["refresh_expires_in"]),
        secure=True
    )
    return response

@app.get(LOGOUT_URL)
async def logout_responce(request: Request, user: Annotated[UIUser, Depends(verify_token)]) -> RedirectResponse:
    """Эндпоинт, в который нужно перейти чтобы выйти
    Удаляет access_token из кук и перенаправляет на домашнюю страницу
    """
    logger.info("User logout - removing token from coockies")
    provider.keycloak.keycloak_openid.logout(request.cookies.get("RefreshToken"))
    response = redirect_to_login(request, redirect_url=provider.config.path_prefix)
    response.delete_cookie(key="Authorization")
    response.delete_cookie(key="RefreshToken")
    return response