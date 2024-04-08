from fastapi import Request, Depends
from fastapi.responses import (
    Response,
    PlainTextResponse,
    HTMLResponse,
    RedirectResponse,
    JSONResponse
)
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_302_FOUND

import base64

from sqlalchemy import select, insert, update
from sqlalchemy.exc import IntegrityError

from loguru import logger

from utils.db_model import (
    BotStatus,
    User,
    Field,
    Group,
    Settings,
    Log
)
from utils.custom_types import (
    BotStatusEnum,
    FieldStatusEnum,
    GroupStatusEnum,
)

from ui.setup import app, prefix_router, provider
from ui.helpers import (
    verify_token,
    template,
    get_request_data_or_responce,
    prepare_attrs_object_from_request,
)

app.mount(f"{provider.config.path_prefix}/assets", StaticFiles(directory=f"{provider.config.box_bot_home}/src/ui/assets"), name="assets")


####################################################################################################
# Bot status
####################################################################################################

@prefix_router.get("/", tags=['status'])
async def root() -> RedirectResponse:
    """
    Перенаправляет на статус бота
    """
    return RedirectResponse(url=f"{provider.config.path_prefix}/status", status_code=HTTP_302_FOUND)

@prefix_router.get("/status", tags=["status"])
async def status(request: Request) -> HTMLResponse:
    """
    Показывает текущий статус работы бота
    """
    bot_status = await provider.bot_status
    return template(
        request=request, template_name="status.j2.html",
        additional_context = {
            'title':         provider.config.i18n.bot_status,
            'BotStatusEnum': BotStatusEnum,
            'bot_status':    bot_status
        }
    )

@prefix_router.post("/status", tags=["status"], dependencies=[Depends(verify_token)])
async def status(action: str) -> JSONResponse:
    """
    Устанавливает статус работы бота
    """
    logger.success("Start set BotStatus...")
    async with provider.db_session() as session:
        if action == 'turn_off':
            await session.execute(update(BotStatus).values(bot_status = BotStatusEnum.OFF))
        elif action == 'turn_on':
            await session.execute(update(BotStatus).values(bot_status = BotStatusEnum.ON))
        elif action == 'restart':
            await session.execute(update(BotStatus).values(bot_status = BotStatusEnum.RESTART))
        elif action == 'service':
            await session.execute(update(BotStatus).values(bot_status = BotStatusEnum.SERVICE))
        elif action == 'activate_registration':
            await session.execute(update(BotStatus).values(is_registration_open = True))
        elif action == 'deactivate_registration':
            await session.execute(update(BotStatus).values(is_registration_open = False))
        else:
            logger.error("Found unknown bot status...")
            return JSONResponse({'error': True}, status_code=500)

        try:
            await session.commit()
            logger.success("Set BotStatus table...")
            return JSONResponse({'error': False})
        except IntegrityError as err:
            logger.error(err)
            await session.rollback()
            logger.error("Did not set BotStatus table...")
            return JSONResponse({'error': True}, status_code=500)


####################################################################################################
# Users
####################################################################################################

@prefix_router.get("/users", tags=["users"])
async def users(request: Request) -> HTMLResponse:
    """
    Показывает пользователей
    """
    async with provider.db_session() as session:
        fields_selected = await session.execute(
            select(Field)
            .where(Field.status == FieldStatusEnum.MAIN)
            .order_by(Field.id.asc())
        )
        fields = list(fields_selected.scalars())

        users_selected = await session.execute(
            select(User)
            .order_by(User.id.asc())
        )
        users = [ user.to_dict() for user in users_selected.scalars() ]
        
        return template(
            request=request, template_name="users.j2.html",
            additional_context = {
                'title': provider.config.i18n.users,
                'fields': fields,
                'users': users
            }
        )


####################################################################################################
# MINIO
####################################################################################################

@prefix_router.get("/minio/{bucket}/{filename}", tags=["minio"], dependencies=[Depends(verify_token)])
async def minio(bucket: str, filename: str) -> Response:
    """
    Прокси к minio
    """
    response = await provider.minio.proxy_content(bucket, filename)
    return Response(content=response.content, headers=response.headers, status_code=response.status_code)

@prefix_router.get("/minio/base64/{bucket}/{filename}", tags=["minio"], dependencies=[Depends(verify_token)])
async def minio(bucket: str, filename: str) -> Response:
    """
    Прокси к minio, который возвращает ответ в формате base64
    """
    response = await provider.minio.proxy_content(bucket, filename)
    return JSONResponse(content = {
        'image': base64.b64encode(response.content).decode(),
        'mime':  response.headers['content-type']
    })


####################################################################################################
# Groups
####################################################################################################

@prefix_router.get("/groups", tags=["groups"])
async def groups(request: Request) -> HTMLResponse:
    """
    Показывает все группы телеграм
    """
    async with provider.db_session() as session:
        groups_selected = await session.execute(
            select(Group).order_by(Group.id.asc())
        )

    groups = groups_selected.scalars().all()

    return template(
        request=request, template_name="groups.j2.html",
        additional_context = {
            'title':  provider.config.i18n.groups,
            'groups': groups,
            'group_status_enum': GroupStatusEnum
        }
    )

@prefix_router.post("/groups", tags=["groups"], dependencies=[Depends(verify_token)])
async def groups(request: Request) -> JSONResponse:
    """
    Изменяет настройки групп телеграм
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'groups')
    if bad_responce:
        return bad_responce

    logger.info(f"Got groups update reques with {request_data=}")

    groups_attrs, bad_responce = prepare_attrs_object_from_request(request_data, GroupStatusEnum, ['chat_id'])
    if bad_responce:
        return bad_responce

    async with provider.db_session() as session:
        for idx,group_obj in groups_attrs.items():
            if idx == 'new':
                await session.execute(
                    insert(Group).values(**group_obj)
                )
            else:
                await session.execute(
                    update(Group)
                    .where(Group.id == idx)
                    .values(**group_obj)
                )
        try:
            await session.commit()
            logger.success("Set Status table...")
            return JSONResponse({'error': False})
        except IntegrityError as err:
            logger.error(err)
            await session.rollback()
            logger.error("Did not set Status table...")
            return JSONResponse({'error': True}, status_code=500)


####################################################################################################
# Settings
####################################################################################################

@prefix_router.get("/settings", tags=["settings"])
async def settings(request: Request) -> HTMLResponse:
    """
    Показывает настройки бота
    """
    curr_settings = await provider.settings
    settings_with_description = [
        {
            'key': key,
            'description': default_dict['description'],
            'value': getattr(curr_settings, key)
        }
        for key,default_dict in provider.config.defaults.model_dump().items()
    ]
    return template(
        request=request, template_name="settings.j2.html",
        additional_context = {
            'title':    provider.config.i18n.settings,
            'settings': settings_with_description
        }
    )

@prefix_router.post("/settings", tags=["settings"], dependencies=[Depends(verify_token)])
async def settings(request: Request) -> JSONResponse:
    """
    Устанавливает настройки бота
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'settings')
    if bad_responce:
        return bad_responce

    logger.info(f"Got settings update reques with {request_data=}")

    settings_attrs = {
        key: value_dict['value']
        for key, value_dict in request_data.items()
        if isinstance(value_dict, dict) and 'value' in value_dict
    }

    async with provider.db_session() as session:
        await session.execute(
            update(Settings).values(**settings_attrs)
        )

        try:
            await session.commit()
            logger.success("Set Status table...")
            return JSONResponse({'error': False})
        except IntegrityError as err:
            logger.error(err)
            await session.rollback()
            logger.error("Did not set Status table...")
            return JSONResponse({'error': True}, status_code=500)


####################################################################################################
# Logs
####################################################################################################

@prefix_router.get("/logs", tags=["logs"])
async def logs(request: Request) -> HTMLResponse:
    """
    Показывает текущие логи работы бота
    """
    async with provider.db_session() as session:
        logs_selected = await session.execute(
            select(Log).order_by(Log.id.desc()).limit(1000)
        )

    logs = logs_selected.scalars().all()
    return template(
        request=request, template_name="logs.j2.html",
        additional_context = {
            'title': provider.config.i18n.logs,
            'logs':  logs
        }
    )


####################################################################################################
# Healthz
####################################################################################################

@prefix_router.get(f"/healthz", tags=["healthz"])
async def healz() -> PlainTextResponse:
    """
    Возвращает состояние сервера
    """
    return PlainTextResponse("OK")

app.include_router(prefix_router)