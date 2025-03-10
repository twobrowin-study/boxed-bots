import re
from datetime import datetime

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
from src.bot.helpers.telegram import get_safe_message_markdown_v1_content
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import FieldStatusEnum, FieldTypeEnum
from src.utils.db_model import Field, Settings, User

BOT_MAX_FILE_SIZE = 20_000_000


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

    field_value = _prepare_field_value_str_value_from_message(app, field, message)
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
    return await _check_field_bucket_and_file_name_and_reply_if_file_too_large(
        app, user, field, message, message.photo[-1], settings
    )


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

    return await _check_field_bucket_and_file_name_and_reply_if_file_too_large(
        app, user, field, message, message.document, settings
    )


async def _check_field_bucket_and_file_name_and_reply_if_file_too_large(
    app: BBApplication, user: User, field: Field, message: Message, file_value: Document | PhotoSize, settings: Settings
) -> Document | PhotoSize | None:
    """
    Проверить перед сохранением поля:
      * Наличие бакета поля
      * Размер файла и сообщить о слишком большом размере файла
      * Наличие необходимого имени пользователя для сохранения файла
    """
    # Выбросит исключение если значение поля не будет найдено
    await user_get_name_field_value(app, user, settings)

    if not field.bucket:
        raise CouldNotUploadFileToMinioWithoutBucketError

    if file_value.file_size and file_value.file_size > BOT_MAX_FILE_SIZE:
        await message.reply_markdown(settings.user_file_too_large_message_plain)
        return None

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


def _prepare_field_value_str_value_from_message(app: BBApplication, field: Field, message: Message) -> str | None:
    """Подготовить текстовое значение поля из сообщения"""
    field_value = get_safe_message_markdown_v1_content(message)
    return prepare_field_value_str_value(app, field, field_value)


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
