import json
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger
from starlette.datastructures import URL
from starlette.status import HTTP_307_TEMPORARY_REDIRECT

from src.ui.dependencies import verify_token
from src.ui.keycloak import KeycloakUser
from src.ui.provider import provider

MAKE_POST_LOGIN_DATA_AVAILABLE_METHODS = ["POST"]


@dataclass
class PostLoginData:
    query_params: dict[str, str]
    body: bytes


@dataclass
class PostLoginRedirect:
    url: str
    data: PostLoginData | None


post_login_redirects: dict[str, PostLoginRedirect] = {}
post_login_datas: dict[str, PostLoginData] = {}

router = APIRouter(prefix=provider.config.path_prefix)


def make_url_secure(url: URL) -> URL:
    return url if not provider.config.path_secure else url.replace(scheme="https")


async def redirect_to_login(request: Request, redirect_url: str | None = None) -> RedirectResponse | JSONResponse:
    """Перенаправляет неавторизованного пользователя в Keycloak"""
    logger.debug(f"Redirecting anauthorized user to Keycloak and saving method data {request.method}")

    # Запоминаем URL, на который пытался попасть пользователь,
    # чтобы после логина перенаправить его обратно
    state = str(uuid.uuid4())

    post_login_data = None
    if request.method in MAKE_POST_LOGIN_DATA_AVAILABLE_METHODS:
        post_login_data = PostLoginData(query_params=dict(request.query_params), body=await request.body())
        logger.debug(f"Saved post login body: {post_login_data}")

    post_login_redirects[state] = PostLoginRedirect(
        url=redirect_url or str(make_url_secure(request.url)),
        data=post_login_data,
    )

    auth_url = provider.keycloak.keycloak_openid.auth_url(
        redirect_uri=f"{make_url_secure(request.base_url)!s}login",
        scope="openid profile email",
        state=state,
    )
    if request.method != "GET":
        return JSONResponse({"auth_url": auth_url}, status_code=HTTP_307_TEMPORARY_REDIRECT)
    return RedirectResponse(auth_url)


def refresh_token(request: Request) -> RedirectResponse | None:
    """Пытается обновить токен пользователя"""
    refresh_token = request.cookies.get("RefreshToken")

    if not refresh_token:
        return None

    logger.debug("Refreshing with refresh token")
    refresh_response = provider.keycloak.keycloak_openid.refresh_token(refresh_token)

    response = RedirectResponse(make_url_secure(request.url))
    response.set_cookie(
        key="Authorization",
        value=refresh_response["access_token"],
        expires=int(refresh_response["expires_in"]),
        secure=True,
    )
    response.set_cookie(
        key="RefreshToken",
        value=refresh_response["refresh_token"],
        expires=int(refresh_response["refresh_expires_in"]),
        secure=True,
    )
    return response


@router.get("/login")
async def login_response(code: str, state: str, request: Request) -> RedirectResponse:
    """Эндпоинт, в который перенаправит Keycloak после аутентификации
    Сохраняет access_token в куки и перенаправляет пользователя туда, куда он хотел попасть
    """
    logger.debug("User authenticated - requesting token from Keycloak")
    auth_response = provider.keycloak.keycloak_openid.token(
        grant_type="authorization_code",
        code=code,
        redirect_uri=f"{make_url_secure(request.base_url)!s}login",
    )

    post_login_redirect = post_login_redirects.pop(state)

    logger.debug(f"Got token from Keycloak - setting a cookie and redirecting user to {post_login_redirect.url}")

    headers: dict[str, str] = {}

    response = RedirectResponse(post_login_redirect.url, headers=headers)

    if post_login_redirect.data:
        post_login_data_state = str(uuid.uuid4())
        post_login_datas[post_login_data_state] = post_login_redirect.data
        response.set_cookie(
            key="PostLoginBodyState",
            value=post_login_data_state,
            expires=30,
            secure=True,
        )

    response.set_cookie(
        key="Authorization",
        value=auth_response["access_token"],
        expires=int(auth_response["expires_in"]),
        secure=True,
    )
    response.set_cookie(
        key="RefreshToken",
        value=auth_response["refresh_token"],
        expires=int(auth_response["refresh_expires_in"]),
        secure=True,
    )
    return response


@router.get("/login/restore/{state}")
async def login_restore(state: str, _: Annotated[KeycloakUser, Depends(verify_token)]) -> JSONResponse:
    """Получить данные последнего запроса по идентификатору сессии"""
    post_login_data = post_login_datas.pop(state)
    responce_body = {
        "query_params": post_login_data.query_params,
        "body": json.loads(post_login_data.body) if post_login_data.body else None,
    }
    logger.debug(f"Restoring post login data by state {state}: {responce_body}")
    responce = JSONResponse(responce_body)
    responce.delete_cookie("PostLoginBodyState")
    return responce


@router.get("/logout")
async def logout_responce(request: Request, _: Annotated[KeycloakUser, Depends(verify_token)]) -> RedirectResponse:
    """Эндпоинт, в который нужно перейти чтобы выйти
    Удаляет access_token из кук и перенаправляет на домашнюю страницу
    """
    logger.debug("User logout - removing token from coockies")
    provider.keycloak.keycloak_openid.logout(request.cookies.get("RefreshToken"))
    response = await redirect_to_login(request, redirect_url=f"{provider.config.path_prefix}/")
    if type(response) is not RedirectResponse:
        raise HTTPException(500, provider.config.i18n.error_logout_not_by_get_method_it_mus_be_impossible)
    response.delete_cookie(key="Authorization")
    response.delete_cookie(key="RefreshToken")
    return response
