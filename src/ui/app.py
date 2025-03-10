from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.status import HTTP_401_UNAUTHORIZED

from src.ui.provider import provider
from src.ui.routers import (
    bot_status,
    field_branches,
    fields,
    groups,
    keyboard_keys,
    login,
    logs,
    minio,
    notifications,
    promocodes,
    replyable_condition_messages,
    settings,
    users,
)

description = """
UI сервис для управления ботами в коробках
"""

tags_metadata = [
    {
        "name": "status",
        "description": "Статус работы бота",
    },
    {
        "name": "users",
        "description": "Пользователи",
    },
    {
        "name": "minio",
        "description": "Прокси к minio",
    },
    {
        "name": "fields",
        "description": "Пользовательские поля",
    },
    {
        "name": "field_branches",
        "description": "Ветки полей",
    },
    {
        "name": "replyable_condition_messages",
        "description": "Сообщения с условиями и ответами",
    },
    {
        "name": "keybaord_keys",
        "description": "Клавиши клавиатуры",
    },
    {
        "name": "notifications",
        "description": "Уведомления",
    },
    {
        "name": "groups",
        "description": "Группы телеграм",
    },
    {
        "name": "settings",
        "description": "Настройки приложения",
    },
    {
        "name": "promocodes",
        "description": "Управление промокодами",
    },
    {
        "name": "logs",
        "description": "Логи работы бота",
    },
    {
        "name": "login",
        "description": "Вход в приложение",
    },
    {
        "name": "logout",
        "description": "Выход из приложения",
    },
    {
        "name": "healthz",
        "description": "Проверка того что приложение живо",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: ANN201
    """
    Асинхронная инциализация провайдера при старте приложения
    """
    await provider.async_init()
    yield


app = FastAPI(
    title="Box Bot Admin UI",
    description=description,
    openapi_tags=tags_metadata,
    version="0.0.1",
    redoc_url=f"{provider.config.path_prefix}/redoc",
    docs_url=f"{provider.config.path_prefix}/docs",
    openapi_url=f"{provider.config.path_prefix}/openapi.json",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def handle_httpexception(request: Request, e: HTTPException) -> JSONResponse | RedirectResponse:
    """
    Перенаправляет неавторизованного пользователя на страницу авторизации в случае ошибки 401

    Возвращает ошибку во всех остальных слачаях
    """
    if e.status_code == HTTP_401_UNAUTHORIZED:
        return login.refresh_token(request) or await login.redirect_to_login(request)
    logger.warning(str(e))
    return JSONResponse({"error": True, "detail": e.detail}, status_code=e.status_code)


@app.exception_handler(Exception)
async def handle_exception(_: Request, e: Exception) -> JSONResponse | RedirectResponse:
    """
    Возвращает ошибку запроса
    """
    logger.warning(str(e))
    return JSONResponse({"error": True}, status_code=500)


app.mount(
    f"{provider.config.path_prefix}/assets",
    StaticFiles(directory=f"{provider.config.app_home}/src/ui/assets"),
    name="assets",
)


@app.get(f"{provider.config.path_prefix}/healthz", tags=["healthz"])
async def healz() -> PlainTextResponse:
    """
    Возвращает состояние сервера
    """
    return PlainTextResponse("OK")


app.include_router(login.router)
app.include_router(minio.router)

app.include_router(bot_status.router)
app.include_router(users.router)
app.include_router(fields.router)
app.include_router(field_branches.router)
app.include_router(replyable_condition_messages.router)
app.include_router(keyboard_keys.router)
app.include_router(notifications.router)
app.include_router(groups.router)
app.include_router(settings.router)
app.include_router(promocodes.router)
app.include_router(logs.router)
