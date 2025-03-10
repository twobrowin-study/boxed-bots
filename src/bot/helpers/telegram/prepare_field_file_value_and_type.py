from io import BytesIO
from typing import Literal

from src.bot.telegram.application import BBApplication
from src.utils.custom_types import FieldTypeEnum
from src.utils.db_model import Field, UserFieldValue


async def prepare_field_file_value_and_type(
    app: BBApplication, field: Field, user_field_value: UserFieldValue
) -> tuple[str | BytesIO | None, Literal["image", "document"] | None]:
    """Подготовить файл и тип файла для отправки"""
    file = None
    file_type = None
    if user_field_value.value_file_id:
        file = user_field_value.value_file_id
    elif field.type in [FieldTypeEnum.IMAGE, FieldTypeEnum.ZIP_DOCUMENT, FieldTypeEnum.PDF_DOCUMENT] and field.bucket:
        file, _ = await app.provider.minio.download(field.bucket, user_field_value.value)

    if field.type == FieldTypeEnum.IMAGE:
        file_type = "image"
    elif field.type in [FieldTypeEnum.ZIP_DOCUMENT, FieldTypeEnum.PDF_DOCUMENT]:
        file_type = "document"

    return file, file_type
