import re
from datetime import datetime

from jinja2 import Template
from telegram import Document, Message, PhotoSize

from src.bot.exceptions import (
    CouldNotApplyValidationRemoveRegexpOnFieldError,
    CouldNotReSendFieldQuestionError,
    CouldNotUploadFileToMinioWithoutBucketError,
    UserShoulAnswerOnlyNormalFieldsError,
    UserShuldNotAnswerBooleanFieldError,
)
from src.bot.helpers.fields.keyboards import construct_field_reply_keyboard_markup
from src.bot.helpers.fields.values.get import user_get_name_field_value
from src.bot.helpers.telegram import get_message_text_urled
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import FieldStatusEnum, FieldTypeEnum
from src.utils.db_model import Field, Settings, User

BOT_MAX_FILE_SIZE_KB = 20_000


async def user_prepare_field_value_or_answer_type_validation_error(
    app: BBApplication, user: User, field: Field, message: Message, settings: Settings
) -> str | Document | PhotoSize | None:
    """
    Подготовить значение поля пользователя

    Проверяет корректность наличия текста, фото или документа у соответствующих полей и отправялет сообщение об ошибке пользовател.
    """

    if field.status != FieldStatusEnum.NORMAL:
        raise UserShoulAnswerOnlyNormalFieldsError

    if field.type == FieldTypeEnum.BOOLEAN:
        raise UserShuldNotAnswerBooleanFieldError

    if field.type == FieldTypeEnum.FULL_TEXT:
        return await _prepere_str_field_value_or_answer_error(app, user, field, message, settings)

    if field.type == FieldTypeEnum.IMAGE:
        return await _prepere_photo_field_value_or_answer_error(app, user, field, message, settings)

    if field.type in [FieldTypeEnum.PDF_DOCUMENT, FieldTypeEnum.ZIP_DOCUMENT]:
        return await _prepere_document_field_value_or_answer_error(app, user, field, message, settings)

    return None


async def _prepere_str_field_value_or_answer_error(
    app: BBApplication, user: User, field: Field, message: Message, settings: Settings
) -> str | None:
    """Подготовить строковое значение поля пользоватля"""
    if not message.text:
        await _reply_field_error_or_repeate_question(user, field, message, field.type_error_markdown, settings)
        return None

    field_value = prepare_field_value_str_value(app, field, get_message_text_urled(message))
    if not field_value:
        await _reply_field_error_or_repeate_question(user, field, message, field.validation_error_markdown, settings)
        return None

    return field_value


async def _prepere_photo_field_value_or_answer_error(
    app: BBApplication, user: User, field: Field, message: Message, settings: Settings
) -> Document | PhotoSize | None:
    """Подготовить значение фото поля пользоватля"""
    if not message.photo:
        return await _prepere_document_field_value_or_answer_error(app, user, field, message, settings)
    return await _check_file_field_requirements_and_reply_needed(app, user, field, message, message.photo[-1], settings)


async def _prepere_document_field_value_or_answer_error(
    app: BBApplication, user: User, field: Field, message: Message, settings: Settings
) -> Document | PhotoSize | None:
    """Подготовить значение документа поля пользоватля"""
    if not message.document or not message.document.mime_type:
        await _reply_field_error_or_repeate_question(user, field, message, field.type_error_markdown, settings)
        return None

    if field.type == FieldTypeEnum.IMAGE and not message.document.mime_type.startswith("image"):
        await _reply_field_error_or_repeate_question(user, field, message, field.type_error_markdown, settings)
        return None

    if field.type == FieldTypeEnum.PDF_DOCUMENT and message.document.mime_type != "application/pdf":
        await _reply_field_error_or_repeate_question(user, field, message, field.type_error_markdown, settings)
        return None

    if field.type == FieldTypeEnum.ZIP_DOCUMENT and message.document.mime_type not in [
        "application/zip",
        "application/octet-stream",
        "application/x-zip-compressed",
        "multipart/x-zip",
    ]:
        await _reply_field_error_or_repeate_question(user, field, message, field.type_error_markdown, settings)
        return None

    return await _check_file_field_requirements_and_reply_needed(app, user, field, message, message.document, settings)


async def _check_file_field_requirements_and_reply_needed(
    app: BBApplication, user: User, field: Field, message: Message, file_value: Document | PhotoSize, settings: Settings
) -> Document | PhotoSize | None:
    """
    Проверить перед сохранением поля:
      * Наличие необходимого имени пользователя для сохранения файла
      * Наличие бакета поля
      * Размер файла и сообщить о слишком большом размере файла
      * Поддерживаемые типы файлов изображений
    """
    # Выбросит исключение если значение поля не будет найдено
    await user_get_name_field_value(app, user, settings)

    # Выбросить исключение если нет бакета
    if not field.bucket:
        raise CouldNotUploadFileToMinioWithoutBucketError

    # Максимальный размер файла в зависимости от типа файла: изображение или файл
    max_file_size_kb = BOT_MAX_FILE_SIZE_KB
    if type(file_value) is PhotoSize or (
        type(file_value) is Document and file_value.mime_type and file_value.mime_type.startswith("image/")
    ):
        max_file_size_kb = max(int(settings.user_max_image_file_size_kb_int), BOT_MAX_FILE_SIZE_KB)
    elif type(file_value) is Document:
        max_file_size_kb = max(int(settings.user_max_document_file_size_kb_int), BOT_MAX_FILE_SIZE_KB)

    # Ответить если размер файла слишком большой
    file_size_kb = file_value.file_size // 1000 if file_value.file_size else 0
    if file_size_kb > max_file_size_kb:
        await message.reply_markdown(
            await Template(settings.user_file_too_large_message_j2_template, enable_async=True).render_async(
                file_size_kb=file_size_kb, max_file_size_kb=max_file_size_kb
            )
        )
        return None

    # Ответить если использован неподдерживаемый тип файла
    if type(file_value) is Document and file_value.mime_type and file_value.mime_type.startswith("image/"):
        avaliable_image_types = settings.user_avaliable_image_types_array.split(",")
        for avaliable_image_type in avaliable_image_types:
            if file_value.mime_type.endswith(avaliable_image_type):
                return file_value
        await message.reply_markdown(
            await Template(settings.user_unavaliable_image_type_message_j2_template, enable_async=True).render_async(
                image_type=file_value.mime_type.replace("image/", ""), avaliable_image_types=avaliable_image_types
            )
        )
        return None

    # Вернуть данные для документа или фото (это всегда jpeg, поэтому нет проверки типа)
    return file_value


async def _reply_field_error_or_repeate_question(
    user: User, field: Field, message: Message, error_text: str | None, settings: Settings
) -> None:
    """Отправить сообщени об ошибке или повторить вопрос"""
    if not field.question_markdown_or_j2_template:
        raise CouldNotReSendFieldQuestionError

    await message.reply_markdown(
        error_text or field.question_markdown_or_j2_template,
        reply_markup=construct_field_reply_keyboard_markup(
            field,
            settings,
            "full_text_answer" if not user.change_field_message_id else "change_user_field_value",
        ),
    )


def prepare_field_value_str_value(app: BBApplication, field: Field, field_value: str) -> str | None:
    """Подготовить текстовое значение поля"""
    if field.validation_regexp:
        validation_regexp = re.compile(field.validation_regexp)
        if validation_regexp.match(field_value) is None:
            return None

    now_datetime = datetime.now(app.provider.tz)

    if field.check_future_date:
        input_datetime = _create_datetime_object_from_field_value(app, field_value, "%d.%m.%Y")
        if input_datetime.date() > now_datetime.date():
            return None

    if field.check_future_year:
        input_datetime = _create_datetime_object_from_field_value(app, field_value, "%Y")
        if input_datetime.year > now_datetime.year:
            return None

    if field.validation_remove_regexp:
        try:
            field_value = re.sub(re.compile(field.validation_remove_regexp), "", field_value)
        except Exception as e:
            raise CouldNotApplyValidationRemoveRegexpOnFieldError from e

    if field.upper_before_save:
        field_value = field_value.upper()

    return field_value


def _create_datetime_object_from_field_value(app: BBApplication, field_value: str, datetime_format: str) -> datetime:
    """Получить преобразованные значение даты поля"""
    return datetime.strptime(field_value, datetime_format).astimezone(app.provider.tz)
