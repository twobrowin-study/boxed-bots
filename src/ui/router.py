from fastapi import Request, Depends
from fastapi.responses import (
    Response,
    PlainTextResponse,
    HTMLResponse,
    RedirectResponse,
    JSONResponse,
    StreamingResponse
)
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_302_FOUND, HTTP_404_NOT_FOUND

import io
import base64
import pandas as pd
from datetime import datetime
from xlsxwriter.worksheet import Worksheet

from sqlalchemy import select, update, insert
from sqlalchemy.exc import IntegrityError

from loguru import logger

from utils.db_model import (
    BotStatus,
    User,
    Field,
    UserFieldValue,
    FieldBranch,
    KeyboardKey,
    ReplyableConditionMessage,
    Notification,
    Group,
    Settings,
    Log
)
from utils.custom_types import (
    BotStatusEnum,
    FieldStatusEnum,
    FieldBranchStatusEnum,
    KeyboardKeyStatusEnum,
    NotificationStatusEnum,
    GroupStatusEnum,
    ReplyTypeEnum
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
        curr_field_branch_selected = await session.execute(
            select(FieldBranch).where(FieldBranch.id == branch_id)
        )
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

        curr_field_branch = curr_field_branch_selected.scalar_one_or_none()
        if not curr_field_branch:
            return HTTP_404_NOT_FOUND
        
        field_branches    = list(field_branches_selected.scalars().all())
        fields            = list(fields_selected.scalars().all())
        users = [ user.prepare() for user in users_selected.scalars() ]

        return template(
            request=request, template_name="users.j2.html",
            additional_context = {
                'title':             provider.config.i18n.users,
                'curr_field_branch': curr_field_branch,
                'field_branches':    field_branches,
                'fields':            fields,
                'users':             users
            }
        )

@prefix_router.post("/users/branch/{branch_id}", tags=["users"])
async def users(branch_id: int, request: Request) -> HTMLResponse:
    """
    Устанавливает значения полей для пользователей
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'users')
    if bad_responce:
        return bad_responce

    logger.info(f"Got fields update request on branch {branch_id=} with {request_data=}")

    async with provider.db_session() as session:
        for user_id, fields_dict in request_data.items():
            if not user_id.isnumeric():
                message = f"User id {user_id=} is not numeric"
                logger.warning(message)
                return JSONResponse({'error': True, 'message': message}, status_code=500)
            user_id = int(user_id)

            fields_request: dict[str, dict[str, str]] = fields_dict['fields']
            if not isinstance(fields_request, dict):
                message = f"Fields request {fields_request=} is not dict"
                logger.warning(message)
                return JSONResponse({'error': True, 'message': message}, status_code=500)

            for field_id, field_value in fields_request.items():
                if not field_id.isnumeric():
                    message = f"Field id {field_id=} is not numeric"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)
                field_id = int(field_id)

                if not isinstance(field_value, dict):
                    message = f"Field value {field_value=} is not dict"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)

                if 'value' not in field_value:
                    message = f"Value not in field value {field_value=}"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)
                value = field_value['value']

                updated = await session.execute(
                    update(UserFieldValue)
                    .where(
                        (UserFieldValue.user_id  == user_id) &
                        (UserFieldValue.field_id == field_id)
                    )
                    .values(value = value)
                )

                if updated.rowcount == 0:
                    await session.execute(
                        insert(UserFieldValue)
                        .values(
                            user_id  = user_id,
                            field_id = field_id,
                            value    = value
                        )
                    )
        
        await session.commit()
        return JSONResponse({'error': False}, status_code=200)

@prefix_router.get("/users/report/xslx", tags=["users"], dependencies=[Depends(verify_token)])
async def users(request: Request) -> Response:
    """
    Возвращает отчёт по пользователям в формате xlsx
    """
    logger.info("Starting prepare of users full report")

    async with provider.db_session() as session:
        users_selected = await session.execute(
            select(User)
            .order_by(User.id.asc())
        )
        users_df = pd.DataFrame([
            user.to_plain_dict(i18n=provider.config.i18n)
            for user in users_selected.scalars()
        ])

        logger.debug(f"Users df:\n{users_df}")
        
        filename = f"{datetime.now().strftime('%Y_%m_%d__%H_%M_%S')}__{provider.config.path_prefix.replace('/', '')}_report.xlsx"
        headers = {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition': f'attachment; filename="{filename}"'
        }

        sheet_name = provider.config.i18n.download_users_report
        
        report_bio = io.BytesIO()
        with pd.ExcelWriter(report_bio) as writer:
            users_df.to_excel(writer, startrow=0, merge_cells=False, sheet_name=sheet_name, index=False)

            worksheet: Worksheet = writer.sheets[sheet_name]
            row_count    = len(users_df.index)
            column_count = len(users_df.columns)
            
            worksheet.autofilter(0, 0, row_count-1, column_count-1)  
            
            for idx, col in enumerate(users_df):
                series = users_df[col]
                max_len = max((
                    series.astype(str).map(len).max(),
                    len(str(series.name))
                    )) + 5
                worksheet.set_column(idx, idx, max_len)

        report_bio.seek(0)
        return StreamingResponse(report_bio, headers=headers, media_type=headers['Content-Type'])


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

@prefix_router.get("/minio/{bucket}/{filename}", tags=["minio"], dependencies=[Depends(verify_token)])
async def minio(bucket: str, filename: str) -> Response:
    """
    Прокси к minio, который возвращает файл
    """
    bio, _ = await provider.minio.download(bucket, filename)
    if not bio:
        return JSONResponse({'error': True}, status_code=500)
    bio.seek(0)
    return StreamingResponse(bio)


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
# Replyable condition messages
####################################################################################################

@prefix_router.get("/replyable_condition_messages", tags=["replyable_condition_messages"])
async def replyable_condition_messages(request: Request) -> HTMLResponse:
    """
    Показывает сообщения с условиями и ответами
    """
    async with provider.db_session() as session:
        replyable_condition_messages_selected = await session.execute(
            select(ReplyableConditionMessage).order_by(ReplyableConditionMessage.id.asc())
        )
        fields_selected = await session.execute(
            select(Field).order_by(Field.id.asc())
        )
        field_branches_selected = await session.execute(
            select(FieldBranch).order_by(FieldBranch.id.asc())
        )

    replyable_condition_messages = list(replyable_condition_messages_selected.scalars().all())
    fields                       = list(fields_selected.scalars().all())
    field_branches               = list(field_branches_selected.scalars().all())

    return template(
        request=request, template_name="replyable_condition_messages.j2.html",
        additional_context = {
            'title': provider.config.i18n.replyable_condition_messages,
            'replyable_condition_messages': replyable_condition_messages,
            'reply_type_enum':              ReplyTypeEnum,
            'fields':                       fields,
            'field_branches':               field_branches
        }
    )

@prefix_router.post("/replyable_condition_messages", tags=["replyable_condition_messages"], dependencies=[Depends(verify_token)])
async def replyable_condition_messages(request: Request) -> JSONResponse:
    """
    Изменяет настройки сообщений с условиями и ответами
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'replyable_condition_messages')
    if bad_responce:
        return bad_responce

    logger.info(f"Got replyable_condition_messages update request with {request_data=}")

    replyable_condition_messages_attrs, bad_responce = prepare_attrs_object_from_request(request_data, ReplyTypeEnum)
    if bad_responce:
        return bad_responce
    
    for _,replyable_condition_messages_attr in replyable_condition_messages_attrs.items():
        if 'reply_type' in replyable_condition_messages_attr:
            if replyable_condition_messages_attr['reply_type'] == ReplyTypeEnum.BRANCH_START:
                if 'reply_answer_field_branch_id' not in replyable_condition_messages_attr or not replyable_condition_messages_attr['reply_answer_field_branch_id']:
                    message = f"Did not found reply_answer_field_branch_id in replyable_condition_message object while status is BRANCH_START"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)
                
            if replyable_condition_messages_attr['reply_type'] in [ReplyTypeEnum.FULL_TEXT_ANSWER, ReplyTypeEnum.FAST_ANSWER]:
                if 'reply_answer_field_id' not in replyable_condition_messages_attr or not replyable_condition_messages_attr['reply_answer_field_id']:
                    message = f"Did not found reply_answer_field_id in replyable_condition_message object while status is FULL_TEXT_ANSWER or FAST_ANSWER"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)
                
            if replyable_condition_messages_attr['reply_type'] in [ReplyTypeEnum.FULL_TEXT_ANSWER, ReplyTypeEnum.BRANCH_START]:
                if 'reply_keyboard_keys' in replyable_condition_messages_attr and '\n' in replyable_condition_messages_attr['reply_keyboard_keys']:
                    message = f"New lines found in reply_keyboard_keys in replyable_condition_message object while status is FULL_TEXT_ANSWER or BRANCH_START"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)
    
    return await try_to_save_attrs(ReplyableConditionMessage, replyable_condition_messages_attrs)


####################################################################################################
# Keyboard keys
####################################################################################################

@prefix_router.get("/keyboard_keys", tags=["keyboard_keys"])
async def keyboard_keys(request: Request) -> HTMLResponse:
    """
    Показывает кнопки клавиатуры
    """
    async with provider.db_session() as session:
        keyboard_keys_selected = await session.execute(
            select(KeyboardKey).order_by(KeyboardKey.id.asc())
        )
        replyable_condition_messages_selected = await session.execute(
            select(ReplyableConditionMessage).order_by(ReplyableConditionMessage.id.asc())
        )
        field_branches_selected = await session.execute(
            select(FieldBranch).order_by(FieldBranch.id.asc())
        )

    keyboard_keys                = list(keyboard_keys_selected.scalars().all())
    replyable_condition_messages = list(replyable_condition_messages_selected.scalars().all())
    field_branches               = list(field_branches_selected.scalars().all())

    return template(
        request=request, template_name="keyboard_keys.j2.html",
        additional_context = {
            'title': provider.config.i18n.keyboard_keys,
            'keyboard_keys':                keyboard_keys,
            'keyboard_key_status_enum':     KeyboardKeyStatusEnum,
            'replyable_condition_messages': replyable_condition_messages,
            'field_branches':               field_branches
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
            if keyboard_keys_attr['status'] == KeyboardKeyStatusEnum.NORMAL:
                if 'reply_condition_message_id' not in keyboard_keys_attr or not keyboard_keys_attr['reply_condition_message_id']:
                    message = f"Did not found reply_condition_message_id in keyboard_key object while status is NORMAL"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)
                
            if keyboard_keys_attr['status'] == KeyboardKeyStatusEnum.ME:
                if 'branch_id' not in keyboard_keys_attr or not keyboard_keys_attr['branch_id']:
                    message = f"Did not found branch_id in keyboard_key object while status is ME"
                    logger.warning(message)
                    return JSONResponse({'error': True, 'message': message}, status_code=500)
    
    return await try_to_save_attrs(KeyboardKey, keyboard_keys_attrs)


####################################################################################################
# Notifications
####################################################################################################

@prefix_router.get("/notifications", tags=["notifications"])
async def notifications(request: Request) -> HTMLResponse:
    """
    Показывает уведомления
    """
    async with provider.db_session() as session:
        notifications_selected = await session.execute(
            select(Notification).order_by(Notification.id.asc())
        )
        replyable_condition_messages_selected = await session.execute(
            select(ReplyableConditionMessage).order_by(ReplyableConditionMessage.id.asc())
        )

    notifications                = list(notifications_selected.scalars().all())
    replyable_condition_messages = list(replyable_condition_messages_selected.scalars().all())

    return template(
        request=request, template_name="notifications.j2.html",
        additional_context = {
            'title': provider.config.i18n.notifications,
            'notifications':                notifications,
            'notification_status_enum':     NotificationStatusEnum,
            'replyable_condition_messages': replyable_condition_messages
        }
    )

@prefix_router.post("/notifications", tags=["notifications"], dependencies=[Depends(verify_token)])
async def notifications(request: Request) -> JSONResponse:
    """
    Изменяет настройки уведомлений
    """
    request_data, bad_responce = await get_request_data_or_responce(request, 'notifications')
    if bad_responce:
        return bad_responce

    logger.info(f"Got notifications update request with {request_data=}")

    notifications_attrs, bad_responce = prepare_attrs_object_from_request(request_data, NotificationStatusEnum)
    if bad_responce:
        return bad_responce
    
    return await try_to_save_attrs(Notification, notifications_attrs)


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