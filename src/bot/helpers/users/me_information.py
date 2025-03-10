from io import BytesIO
from typing import Literal

from loguru import logger
from sqlalchemy import Column, select, update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.helpers.keyboards.user_currents import get_user_current_keyboard
from src.bot.helpers.telegram import shrink_text_up_to_80_symbols
from src.bot.helpers.telegram.send_message_and_return_file_id import send_message_and_return_file_id
from src.bot.telegram.application import BBApplication
from src.bot.telegram.callback_constants import UserChangeFieldCallback
from src.utils.custom_types import FieldStatusEnum, FieldTypeEnum, UserFieldDataPrepared
from src.utils.db_model import Field, User, UserFieldValue


async def user_send_me_information(
    app: BBApplication,
    user: User,
    field_branch_id: Column[int | None],
    message: Message,
    context: Literal["me_plain", "me_change"],
) -> None:
    """
    Отправить пользователю информацию о регистрации

    Параметры:
     * app: BBApplication - Приложение
     * user: User - Пользователь
     * field_branch_id: Column[int | None] - Идентификатор ветки пользователя, по которой следует отображать данные
     * message: Message - Сообщение, на которое следует ответить
     * context: Literal["me_plain", "me_change"] - Контекст отправки информации о пользователе:
       * "me_plain" - Полское представление, без отправки кнопок пользователю
       * "me_change" - Изменение значений пользователя, с отправкой полей
    """

    logger.debug(f"Sending me information to user {user.id=} with context {context=}")

    file_descriptor, text, reply_markup = await prepare_me_information_message_documents_photos_text_and_reply_keyboard(
        app, user, field_branch_id
    )

    for field, file, filename in file_descriptor:
        file_type = None
        if field.type == FieldTypeEnum.IMAGE:
            file_type = "image"
        elif field.type in [FieldTypeEnum.ZIP_DOCUMENT, FieldTypeEnum.PDF_DOCUMENT]:
            file_type = "document"

        if file_type:
            file_id = await send_message_and_return_file_id(
                app=app,
                user=user,
                text=None,
                file=file,
                file_type=file_type,
                filename=filename,
            )

            if file_id and type(file) is not str:
                await _user_field_value_set_value_field_id(app, user, field, file_id)

    await message.reply_markdown(
        text=text, reply_markup=reply_markup if context == "me_change" else await get_user_current_keyboard(app, user)
    )


async def _user_field_value_set_value_field_id(app: BBApplication, user: User, field: Field, file_id: str) -> None:
    async with app.provider.db_sessionmaker() as session:
        await session.execute(
            update(UserFieldValue)
            .where(UserFieldValue.user_id == user.id)
            .where(UserFieldValue.field_id == field.id)
            .values(value_file_id=file_id)
        )
        await session.commit()


async def prepare_me_information_message_documents_photos_text_and_reply_keyboard(
    app: BBApplication, user: User, field_branch_id: Column[int | None]
) -> tuple[list[tuple[Field, str | BytesIO, str]], str, InlineKeyboardMarkup]:
    """
    Подготовить информацию о пользователе для отправки или обновления сообщения

    Параметры:
     * app: BBApplication - Приложение
     * user: User - Пользователь
     * field_branch_id: Column[int|None] - Идентификатор ветки пользователя, по которой следует отображать данные

    Возвращает tuple из:
     * list[tuple[Field, str | BytesIO, str]] - Список высылаемых объектов фото или документов по порядку, содержит:
       * Field: Поле
       * str | BytesIO: Идентификатор поля или его содержимое
       * str: Имя файла
     * str - Текст высылаемого сообщения - содержит все поля пользователя
     * InlineKeyboardMarkup - Разметка inline-клавиатуры для отображения с текстовым сообщением
    """
    file_list: list[tuple[Field, str | BytesIO, str]] = []
    text_lines: list[str] = []
    buttons: list[InlineKeyboardButton] = []

    prepeared_user_field_values = user.prepare_fields()

    async with app.provider.db_sessionmaker() as session:
        ordered_fields = await session.scalars(
            select(Field)
            .where(Field.branch_id == field_branch_id)
            .where(Field.status == FieldStatusEnum.NORMAL)
            .where(Field.type != FieldTypeEnum.BOOLEAN)
            .order_by(Field.order_place.asc())
        )
        for field in ordered_fields:
            if field.id in prepeared_user_field_values:
                prepeared_field_value = prepeared_user_field_values[field.id]
            else:
                prepeared_field_value = UserFieldDataPrepared(
                    value="", type=field.type, bucket=field.bucket, empty=True
                )

            # Добавление кнопок в зависимости от того задал ли пользователь значение
            button_action_text = (
                app.provider.config.i18n.change if not prepeared_field_value.empty else app.provider.config.i18n.append
            )
            buttons += [
                InlineKeyboardButton(
                    text=f"{button_action_text} {field.key}",
                    callback_data=UserChangeFieldCallback.TEMPLATE.format(field_id=field.id),
                )
            ]

            # Заполнение текста для текстовых полей
            if field.type == FieldTypeEnum.FULL_TEXT:
                field_value_text = (
                    app.provider.config.i18n.data_empty
                    if prepeared_field_value.empty
                    else shrink_text_up_to_80_symbols(prepeared_field_value.value)
                )
                text_lines += [f"*{field.key}*: `{field_value_text}`"]
                continue

            # Работа с документами только в случае если поле не пустое
            if prepeared_field_value.empty or not prepeared_field_value.bucket:
                continue

            if field.type not in [FieldTypeEnum.IMAGE, FieldTypeEnum.PDF_DOCUMENT, FieldTypeEnum.ZIP_DOCUMENT]:
                continue

            filename = prepeared_field_value.value.replace("_thumbnail", "")

            if prepeared_field_value.value_file_id:
                file = prepeared_field_value.value_file_id
            else:
                file, _ = await app.provider.minio.download(prepeared_field_value.bucket, filename)

            if file:
                file_list += [(field, file, filename)]

    return file_list, "\n".join(text_lines), InlineKeyboardMarkup([[button] for button in buttons])
