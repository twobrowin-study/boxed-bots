from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from src.ui.app import provider
from src.ui.keycloak import KeycloakUser
from src.utils.db_model import Base

templates = Jinja2Templates(directory=f"{provider.config.app_home}/src/ui/templates")


def template(request: Request, template_name: str, user: KeycloakUser, **additional_context: Any) -> HTMLResponse:
    """Прослойка для стандартизации вывода шаблонов"""
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "uri_prefix": provider.config.path_prefix,
            "i18n": provider.config.i18n,
            "user": user,
        }
        | additional_context,
    )


async def get_request_data_or_responce(request: Request, main_field: str) -> dict[str, Any]:
    """
    Проверяет полученные из запроса данные по заданному базовому полю и возвращает их
    * request: Request - Запрос
    * main_field: str - Основное поле из запроса

    Пример: На запрос `{'users': {...}}` будет возвращён объект `{...}`
    """
    request_data = await request.json()

    if not isinstance(request_data, dict):
        raise HTTPException(500, provider.config.i18n.error_found_unknown_request_field)

    if main_field not in request_data:
        raise HTTPException(500, f"{provider.config.i18n.error_field_is_not_in_request} {main_field}")

    request_data_by_field = request_data[main_field]
    if not isinstance(request_data_by_field, dict):
        raise HTTPException(500, f"{provider.config.i18n.error_bad_field_request} {main_field}")

    return request_data_by_field


def make_db_object(
    plain_obj: dict[str, Any],
    numeric_keys: list[str],
    **enum_types_dict: type[Enum],
) -> dict[str, Any]:
    """
    Создание полей объекта БД
    * plain_obj: dict[str, Any] - Данные для заполнения (пришли из API)
    * status_type: type[Enum] - Тип статуса объекта БД
    * numeric_keys: list[str] - Целочисленные поля БД
    """
    obj: dict[str, Any] = {}
    for key, value in plain_obj.items():
        if key in numeric_keys and type(value) is str and value:
            if value.lstrip("-").isnumeric():
                obj[key] = int(value) if value else None
            else:
                raise HTTPException(
                    500,
                    f"{provider.config.i18n.error_got_value_error_as} {key=} {provider.config.i18n.error_should_be_numeric_but_got} {value=}",
                )

        elif type(value) is str:
            obj[key] = value if value else None

        elif type(value) is dict:
            if "bool_value" in value:
                obj[key] = value["bool_value"] == "true"
            elif "id_value" in value:
                obj[key] = None if value["id_value"] == "None" else int(value["id_value"])
            elif "date_value" in value:
                obj[key] = (
                    None if value["date_value"] in ["", None, "None"] else datetime.fromisoformat(value["date_value"])
                )
            elif key in enum_types_dict and value["value"] != "None":
                obj[key] = enum_types_dict[key](**value)
            else:
                obj[key] = None
        else:
            raise HTTPException(500, f"{provider.config.i18n.error_got_bad_key_value_pair} {key=} {value=}")
    return obj


def prepare_attrs_object_from_request(
    request_data: dict[str, Any],
    numeric_keys: list[str] | None = None,
    **enum_types_dict: type[Enum],
) -> dict[str | int, dict[str, Any]]:
    """
    Подготовка атрибутов объектов БД
    * request_data: dict[str, Any] - Исходные данные БД
    * status_type: type[Enum] - Тип статуса объекта БД
    * numeric_keys: list[str] | None - Целочисленные поля БД
    """
    if numeric_keys is None:
        numeric_keys = []
    attrs: dict[str | int, dict[str, Any]] = {}
    for idx_data, plain_obj in request_data.items():
        if idx_data != "new" and not idx_data.isnumeric():
            raise HTTPException(500, f"{provider.config.i18n.error_got_bad_id} {idx_data=}")
        idx = int(idx_data) if idx_data.isnumeric() else idx_data
        attrs[idx] = make_db_object(plain_obj, numeric_keys, **enum_types_dict)
    return attrs


async def try_to_save_attrs(db_type: type[Base], db_attrs: dict[str | int, dict[str, Any]]) -> JSONResponse:
    """
    Общая функция для сохранения записей в БД
    * db_type: type[Base] - тип объекта БД
    * db_attrs: dict[str | int, dict[str, Any]] - сохраняемые объекты БД: идентификатор или new и данные полей
    """
    async with provider.db_sessionmaker() as session:
        for idx, db_attr in db_attrs.items():
            if idx == "new":
                await session.execute(insert(db_type).values(**db_attr))
            else:
                await session.execute(update(db_type).where(db_type.__table__.c["id"] == idx).values(**db_attr))
        try:
            await session.commit()
            logger.success(f"Updated table {db_type.__name__}")
            return JSONResponse({"error": False})
        except IntegrityError as err:
            logger.error(err)
            await session.rollback()
            raise HTTPException(500, provider.config.i18n.error_did_not_update_table) from err
