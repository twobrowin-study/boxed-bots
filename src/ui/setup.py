from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse

from contextlib import asynccontextmanager

from ui.ui_provider import UIProvider

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
        "name": "logs",
        "description": "Логи работы бота",
    },
    {
        "name": "healthz",
        "description": "Проверка того что приложение живо",
    },
]

provider = UIProvider()

@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Асинхронная инциализация провайдера при старте приложения
    """
    await provider.async_init()
    yield

app = FastAPI(
    title        = "Box Bot Admin UI",
    description  = description,
    openapi_tags = tags_metadata,
    version      = "0.0.1",
    redoc_url    = f"{provider.config.path_prefix}/redoc",
    docs_url     = f"{provider.config.path_prefix}/docs",
    openapi_url  = f"{provider.config.path_prefix}/openapi.json",
    lifespan     = lifespan
)

app.mount(f"{provider.config.path_prefix}/assets", StaticFiles(directory=f"{provider.config.box_bot_home}/src/ui/assets"), name="assets")

@app.get(f"{provider.config.path_prefix}/healthz", tags=["healthz"])
async def healz() -> PlainTextResponse:
    """
    Возвращает состояние сервера
    """
    return PlainTextResponse("OK")