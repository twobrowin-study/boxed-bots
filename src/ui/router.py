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
    FieldBranch,
    KeyboardKey,
    Group,
    Settings,
    Log
)
from utils.custom_types import (
    BotStatusEnum,
    FieldStatusEnum,
    FieldBranchStatusEnum,
    KeyboardKeyStatusEnum,
    GroupStatusEnum,
)

from ui.setup import app, prefix_router, provider
from ui.helpers import (
    verify_token,
    template,
    get_request_data_or_responce,
    prepare_attrs_object_from_request,
    try_to_save_attrs
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

@prefix_router.get("/users", tags=['users'])
async def users() -> RedirectResponse:
    """
    Перенаправляет на страницу пользователей с самой первой веткой полей
    """
    settings = await provider.settings
    async with provider.db_session() as session:
        users_branches_selected = await session.execute(
            select(FieldBranch)
            .where(FieldBranch.key == settings.first_field_branch)
        )
    first_field_branch_id = users_branches_selected.scalar_one().id
    return RedirectResponse(url=f"{provider.config.path_prefix}/users/branch/{first_field_branch_id}", status_code=HTTP_302_FOUND)

@prefix_router.get("/users/branch/{branch_id}", tags=["users"])
async def users(branch_id: int, request: Request) -> HTMLResponse:
    """
    Показывает пользователей
    """
    async with provider.db_session() as session:
        field_branches_selected = await session.execute(
            select(FieldBranch).order_by(FieldBranch.id.asc())
        )
        fields_selected = await session.execute(
            select(Field).where(Field.branch_id == branch_id)
            .order_by(Field.order_place.asc())
        )
        users_selected = await session.execute(
            select(User)
            .order_by(User.id.asc())
        )

        field_branches = list(field_branches_selected.scalars().all())
        fields          = list(fields_selected.scalars().all())
        users = [ user.prepare() for user in users_selected.scalars() ]

        return template(
            request=request, template_name="users.j2.html",
            additional_context = {
                'title':           provider.config.i18n.users,
                'field_branch_id': branch_id,
                'field_branches':  field_branches,
                'fields':          fields,
                'users':           users
            }
        )


####################################################################################################
# MINIO
####################################################################################################

@prefix_router.get("/minio/base64/{bucket}/{filename}", tags=["minio"], dependencies=[Depends(verify_token)])
async def minio(bucket: str, filename: str) -> Response:
    """
    Прокси к minio, который возвращает ответ в формате base64
    """
    bio, content_type = await provider.minio.download(bucket, filename)
    if not bio:
        return JSONResponse({'error': True}, status_code=500)
    bio.seek(0)
    return JSONResponse(content = {
        'image': base64.b64encode(bio.getvalue()).decode(),
        'mime':  content_type
    })


####################################################################################################
# Fields
####################################################################################################

@prefix_router.get("/fields", tags=['fields'])
async def fields() -> RedirectResponse:
    """
    Перенаправляет на страницу полей с самой первой веткой полей
    """
    settings = await provider.settings
    async with provider.db_session() as session:
        field_branches_selected = await session.execute(
            select(FieldBranch)
            .where(FieldBranch.key == settings.first_field_branch)
        )
    first_field_branch_id = field_branches_selected.scalar_one().id
    return RedirectResponse(url=f"{provider.config.path_prefix}/fields/{first_field_branch_id}", status_code=HTTP_302_FOUND)

@prefix_router.get("/fields/{branch_id}", tags=["fields"])
async def fields(branch_id: int, request: Request) -> HTMLResponse:
    """
    Показывает пользовательские поля
    """
    async with provider.db_session() as session:
        field_branches_selected = await session.execute(
            select(FieldBranch).order_by(FieldBranch.id.asc())
        )
        fields_selected = await session.execute(
            select(Field).where(Field.branch_id == branch_id)
            .order_by(Field.order_place.asc())
        )

    field_branches = list(field_branches_selected.scalars().all())
    fields          = list(fields_selected.scalars().all())

    return template(
        request=request, template_name="fields.j2.html",
        additional_context = {
            'title':             provider.config.i18n.fields,
            'field_branch_id':   branch_id,
            'field_branches':    field_branches,
            'fields':            fields,
            'field_status_enum': FieldStatusEnum
        }
    )

@prefix_router.post("/fields/{branch_id}", tags=["fields"], dependencies=[Depends(verify_token)])
async def fields(branch_id: int, request: Request) -> JSONResponse:
    """
    Изменяет настройки веток пользовательских полей
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'fields')
    if bad_responce:
        return bad_responce

    logger.info(f"Got fields update request on branch {branch_id=} with {request_data=}")

    fields_attrs, bad_responce = prepare_attrs_object_from_request(request_data, FieldStatusEnum, ['order_place'])
    if bad_responce:
        return bad_responce
    
    for _,field in fields_attrs.items():
        if 'document_bucket' in field and 'image_bucket' in field:
            if field['document_bucket'] and field['image_bucket']:
                logger.error("Trying to save image and document buckets at the same time")
                return JSONResponse({'error': True}, status_code=500)

    return await try_to_save_attrs(Field, fields_attrs)


####################################################################################################
# Field branches
####################################################################################################

@prefix_router.get("/field_branches", tags=["field_branches"])
async def field_branches(request: Request) -> HTMLResponse:
    """
    Показывает ветки пользовательскх полей
    """
    async with provider.db_session() as session:
        field_branches_selected = await session.execute(
            select(FieldBranch).order_by(FieldBranch.id.asc())
        )

    field_branches = list(field_branches_selected.scalars().all())

    return template(
        request=request, template_name="field_branches.j2.html",
        additional_context = {
            'title':  provider.config.i18n.field_branches,
            'field_branches': field_branches,
            'field_branch_status_enum': FieldBranchStatusEnum
        }
    )

@prefix_router.post("/field_branches", tags=["field_branches"], dependencies=[Depends(verify_token)])
async def field_branches(request: Request) -> JSONResponse:
    """
    Изменяет настройки веток пользовательских полей
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'field_branches')
    if bad_responce:
        return bad_responce

    logger.info(f"Got field_branches update request with {request_data=}")

    field_branches_attrs, bad_responce = prepare_attrs_object_from_request(request_data, FieldBranchStatusEnum)
    if bad_responce:
        return bad_responce
    
    return await try_to_save_attrs(FieldBranch, field_branches_attrs)


####################################################################################################
# Keyboard keys
####################################################################################################

@prefix_router.get("/keyboard_keys", tags=["keyboard_keys"])
async def keyboard_keys(request: Request) -> HTMLResponse:
    """
    Показывает кнопки клавиатуры
    """
    async with provider.db_session() as session:
        field_branches_selected = await session.execute(
            select(FieldBranch).order_by(FieldBranch.id.asc())
        )
        keyboard_keys_selected = await session.execute(
            select(KeyboardKey).order_by(KeyboardKey.id.asc())
        )

    field_branches = list(field_branches_selected.scalars().all())
    keyboard_keys = keyboard_keys_selected.scalars().all()

    return template(
        request=request, template_name="keyboard_keys.j2.html",
        additional_context = {
            'title':  provider.config.i18n.keyboard_keys,
            'keyboard_keys':            keyboard_keys,
            'keyboard_key_status_enum': KeyboardKeyStatusEnum,
            'field_branches':           field_branches
        }
    )

@prefix_router.post("/keyboard_keys", tags=["keyboard_keys"], dependencies=[Depends(verify_token)])
async def keyboard_keys(request: Request) -> JSONResponse:
    """
    Изменяет настройки клавиш клавиатуры
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'keyboard_keys')
    if bad_responce:
        return bad_responce

    logger.info(f"Got keyboard_keys update request with {request_data=}")

    keyboard_keys_attrs, bad_responce = prepare_attrs_object_from_request(request_data, KeyboardKeyStatusEnum)
    if bad_responce:
        return bad_responce
    
    for _,keyboard_keys_attr in keyboard_keys_attrs.items():
        if 'status' in keyboard_keys_attr:
            if keyboard_keys_attr['status'] in [KeyboardKeyStatusEnum.ME, KeyboardKeyStatusEnum.DEFERRED]:
                if 'branch_id' not in keyboard_keys_attr or not keyboard_keys_attr['branch_id']:
                    logger.warning(f"Did not found branch_id in keyboard_key object while status is ME or DEFERRED")
                    return JSONResponse({'error': True}, status_code=500)
                
            if keyboard_keys_attr['status'] in [KeyboardKeyStatusEnum.NORMAL, KeyboardKeyStatusEnum.DEFERRED]:
                if 'text_markdown' not in keyboard_keys_attr or not keyboard_keys_attr['text_markdown']:
                    logger.warning(f"Did not found text_markdown in keyboard_key object while status is NORMAL or DEFERRED")
                    return JSONResponse({'error': True}, status_code=500)
    
    return await try_to_save_attrs(KeyboardKey, keyboard_keys_attrs)


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

    logger.info(f"Got groups update request with {request_data=}")

    groups_attrs, bad_responce = prepare_attrs_object_from_request(request_data, GroupStatusEnum, ['chat_id'])
    if bad_responce:
        return bad_responce
    
    return await try_to_save_attrs(Group, groups_attrs)


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

    logger.info(f"Got settings update request with {request_data=}")

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