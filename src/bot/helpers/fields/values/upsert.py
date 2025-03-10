from io import BytesIO

from filetype.types import TYPES as FILE_TYPES
from filetype.types import Type as FileType
from filetype.types import image as image_types
from loguru import logger
from sqlalchemy import insert, update
from telegram import Document, Message, PhotoSize

from src.bot.exceptions import (
    CouldNotUploadFileToMinioWithoutBucketError,
    CouldNotUpsertFieldValueError,
)
from src.bot.helpers.fields.values.get import user_get_name_field_value
from src.bot.telegram.application import BBApplication
from src.utils.db_model import Field, Settings, User, UserFieldValue


async def user_upsert_field_value_and_return_file_to_save(
    app: BBApplication,
    user: User,
    field: Field,
    message: Message | None,
    field_value: str | PhotoSize | Document,
    settings: Settings,
) -> PhotoSize | Document | None:
    """
    Вставить значение пользовательского поля

    Учитывает тип поля и загружает файл фото или документа

    Возвращает файловые типы данных
    """

    if type(field_value) is str:
        _field_value = field_value
        _field_value_file_id = None
    elif type(field_value) is PhotoSize or type(field_value) is Document:
        _field_value, _ = await _prepare_telegram_file_filename_and_filetype(
            app,
            user,
            field_value,
            settings,
        )
        _field_value_file_id = field_value.file_id

        # Не сохраняем идентификатор файла если пользователь загрузил изображение как документ
        # Бот будет высылать изображение как фото и сохранит идентификатор файла тогда
        if type(field_value) is Document and field_value.mime_type and field_value.mime_type.startswith("image"):
            _field_value_file_id = None
    else:
        raise CouldNotUpsertFieldValueError

    await user_upsert_string_field_value(
        app=app,
        user=user,
        field=field,
        message=message,
        field_value=_field_value,
        field_value_file_id=_field_value_file_id,
    )

    if type(field_value) is PhotoSize or type(field_value) is Document:
        return field_value
    return None


async def user_upsert_string_field_value(
    app: BBApplication,
    user: User,
    field: Field,
    message: Message | None,
    field_value: str,
    field_value_file_id: str | None = None,
) -> PhotoSize | Document | None:
    """
    Вставить строковое значение пользовательского поля

    Вставляет значение только в БД
    """
    message_id = message.id if message else None
    async with app.provider.db_sessionmaker() as session:
        user_field_value = await session.scalar(
            update(UserFieldValue)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.field_id == field.id)
            .values(value=field_value, message_id=message_id, value_file_id=field_value_file_id)
            .returning(UserFieldValue)
        )

        if not user_field_value:
            await session.execute(
                insert(UserFieldValue).values(
                    user_id=user.id,
                    field_id=field.id,
                    value=field_value,
                    message_id=message_id,
                    value_file_id=field_value_file_id,
                )
            )

        await session.commit()


async def _prepare_telegram_file_filename_and_filetype(
    app: BBApplication,
    user: User,
    field_value: PhotoSize | Document,
    settings: Settings,
) -> tuple[str, FileType]:
    # Поиск расширения среди поддерживаемых
    field_file_type = FileType("application/octet-stream", "bin")
    if type(field_value) is PhotoSize:
        field_file_type = image_types.Jpeg()
    elif type(field_value) is Document:
        for file_type in FILE_TYPES:
            if file_type.mime == field_value.mime_type:
                field_file_type = file_type

    # Добавление к значению указание на то, что следует сохранить эскиз
    thumbnail = ""
    if field_file_type.mime.startswith("image"):
        thumbnail = ".thumbnail"

    user_name_field_value = await user_get_name_field_value(app, user, settings)
    return f"{user_name_field_value}.{user.id}{thumbnail}.{field_file_type.extension}", field_file_type


async def upload_telegram_file_to_minio(
    app: BBApplication,
    user: User,
    field: Field,
    field_value: PhotoSize | Document,
    settings: Settings,
) -> None:
    """Загружает файл из telegram в Minio"""
    logger.debug(f"Uploading file from user {user.id=}")

    thumbnail_filename, content_type = await _prepare_telegram_file_filename_and_filetype(
        app,
        user,
        field_value,
        settings,
    )

    file = await field_value.get_file()

    bio = BytesIO()
    await file.download_to_memory(bio)

    if not field.bucket:
        raise CouldNotUploadFileToMinioWithoutBucketError

    await app.provider.minio.upload_w_thumbnail(
        bucket=field.bucket,
        thumbnail_filename=thumbnail_filename,
        bio=bio,
        content_type=content_type.mime,
    )
