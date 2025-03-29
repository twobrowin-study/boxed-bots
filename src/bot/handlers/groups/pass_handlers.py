import io
import zipfile
from datetime import datetime

import pandas as pd
from jinja2 import Template
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy import update as sql_update
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
from xlsxwriter.worksheet import Worksheet

from src.bot.exceptions import GroupPassesNoBucketError, GroupPassesNoFieldError
from src.bot.helpers.groups import (
    get_group_cancel_keyboard,
    get_group_default_keyboard,
    get_group_message_data,
    group_passes_download_document,
)
from src.bot.helpers.telegram import send_long_markdown_splitted_by_newlines
from src.bot.telegram.callback_constants import GroupApprovePassesConversation
from src.utils.custom_types import FieldTypeEnum, PassSubmitStatusEnum, PersonalNotificationStatusEnum
from src.utils.db_model import Field, User, UserFieldValue


async def text_key_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    _, _, message, settings = await get_group_message_data(update, context, "text handle")

    if message.text == settings.group_superadmin_pass_download_submited_button_plain:
        return await download_submited_key_handler(update, context)

    if message.text == settings.group_superadmin_pass_send_approved_button_plain:
        return await upload_aproved_passes_xlsx_start_handler(update, context)

    if message.text == settings.user_or_group_cancel_button_plain:
        return await upload_aproved_passes_xlsx_cancel_handler(update, context)

    return None


async def download_submited_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ответ на нажатие кнопки для скачивания всех пользователей, подавших заявку на получение пропуска"""
    app, group, message, settings = await get_group_message_data(update, context, "download submitted")
    if not group.pass_management:
        logger.debug(f"Got download submitted from group without pass management {group.chat_id=}")
        return ConversationHandler.END

    async with app.provider.db_sessionmaker() as session:
        users_selected = await session.execute(
            select(User).where(User.pass_status == PassSubmitStatusEnum.SUBMITED).order_by(User.id.asc())
        )

    users_df = pd.DataFrame(
        [
            user.to_plain_dict(i18n=app.provider.config.i18n, result_dict_type="ordered_pass_report")
            for user in users_selected.scalars()
        ]
    )

    if settings.user_pass_field_plain not in users_df.columns:
        users_df[settings.user_pass_field_plain] = None

    logger.debug(f"Users df:\n{users_df}")

    if users_df.empty:
        await message.reply_markdown(settings.group_superadmin_pass_submitted_empty_message_plain)
        return ConversationHandler.END

    filename = f"{datetime.now(app.provider.tz).strftime('%Y_%m_%d__%H_%M_%S')}__submitted_pass_report.xlsx"

    sheet_name = app.provider.config.i18n.download_users_report

    report_bio = io.BytesIO()
    with pd.ExcelWriter(report_bio) as writer:
        users_df.to_excel(
            writer,
            startrow=0,
            merge_cells=False,
            sheet_name=sheet_name,
            index=False,
        )

        worksheet: Worksheet = writer.sheets[sheet_name]
        row_count = len(users_df.index)
        column_count = len(users_df.columns)

        worksheet.autofilter(0, 0, row_count - 1, column_count - 1)

        for idx, col in enumerate(users_df):
            series = users_df[col]
            max_len = max((series.astype(str).map(len).max(), len(str(series.name)))) + 5
            worksheet.set_column(idx, idx, max_len)

    report_bio.seek(0)
    await message.reply_document(report_bio, filename=filename)
    return ConversationHandler.END


async def upload_aproved_passes_xlsx_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик нажатия на кнопку старта отправки"""
    app, group, message, settings = await get_group_message_data(update, context, "upload approved")
    if not group.pass_management:
        logger.debug(f"Got upload approved from group without pass management {group.chat_id=}")
        return ConversationHandler.END

    async with app.provider.db_sessionmaker() as session:
        pass_field_type = await session.scalar(select(Field.type).where(Field.key == settings.user_pass_field_plain))

    if pass_field_type == FieldTypeEnum.FULL_TEXT:
        await message.reply_markdown(
            settings.group_superadmin_pass_send_approved_xlsx_message_plain,
            reply_markup=get_group_cancel_keyboard(settings),
        )
        return GroupApprovePassesConversation.XLSX_AWAIT

    await message.reply_markdown(
        settings.group_superadmin_pass_send_approved_zip_photos_message_plain,
        reply_markup=get_group_cancel_keyboard(settings),
    )
    return GroupApprovePassesConversation.ZIP_AWAIT


async def upload_aproved_passes_xlsx_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик нажатия на кнопку отмены отправки"""
    _, group, message, settings = await get_group_message_data(update, context, "upload cancel")
    if not group.pass_management:
        logger.debug(f"Got approved cancel from group without pass management {group.chat_id=}")
        return ConversationHandler.END

    await message.reply_markdown(
        settings.group_superadmin_pass_approved_canceled_message_plain,
        reply_markup=get_group_default_keyboard(group, settings),
    )

    return ConversationHandler.END


async def upload_aproved_passes_zip_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик отправки файла с фото пропусков"""
    app, group, message, settings = await get_group_message_data(update, context, "upload photos zip")
    if not group.pass_management:
        logger.debug(f"Got upload photos zip from group without pass management {group.chat_id=}")
        return ConversationHandler.END

    async with app.provider.db_sessionmaker() as session:
        passes_bucket = await session.scalar(
            select(Field.bucket)
            .where(Field.key == settings.user_pass_field_plain)
            .where(Field.type.in_([FieldTypeEnum.IMAGE, FieldTypeEnum.PDF_DOCUMENT, FieldTypeEnum.ZIP_DOCUMENT]))
        )

    if not passes_bucket:
        raise GroupPassesNoBucketError

    bio = await group_passes_download_document(message)
    zip_photos = zipfile.ZipFile(bio)

    zip_photos_names = zip_photos.namelist()

    context.chat_data["zip_photos"] = zip_photos_names  # type: ignore

    for zip_photo in zip_photos_names:
        zip_photo_bio = io.BytesIO(zip_photos.read(zip_photo))
        await app.provider.minio.upload_guessed(bucket=passes_bucket, filename=zip_photo, bio=zip_photo_bio)

    await message.reply_markdown(
        await Template(
            settings.group_superadmin_pass_available_approved_zip_photos_done_message_j2_template, enable_async=True
        ).render_async(filenames=list(map(escape_markdown, zip_photos_names)))
    )

    await message.reply_markdown(
        settings.group_superadmin_pass_send_approved_xlsx_message_plain,
        reply_markup=get_group_cancel_keyboard(settings),
    )

    return GroupApprovePassesConversation.XLSX_AWAIT


async def upload_aproved_passes_xlsx_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик отправки файла с обработанными пропусками"""
    app, group, message, settings = await get_group_message_data(update, context, "upload approved passes")
    if not group.pass_management:
        logger.debug(f"Got upload approved passes from group without pass management {group.chat_id=}")
        return ConversationHandler.END

    bio = await group_passes_download_document(message)
    passes_df = pd.read_excel(bio)

    logger.debug(f"Passes df:\n{passes_df}")

    pass_field_key = settings.user_pass_field_plain

    to_save_selector = passes_df[pass_field_key].notna()
    if context.chat_data and "zip_photos" in context.chat_data:
        to_save_selector &= passes_df[pass_field_key].isin(context.chat_data["zip_photos"])

    passes_to_save_df = passes_df.loc[to_save_selector]
    passes_not_to_save_df = passes_df.loc[~to_save_selector]

    async with app.provider.db_sessionmaker() as session:
        if not passes_not_to_save_df.empty:
            user_objects_not_to_save = await session.scalars(
                select(User).where(User.id.in_(passes_not_to_save_df["id"].to_numpy()))
            )
            user_dicts_not_to_save = [user.to_plain_dict() for user in user_objects_not_to_save]
            await send_long_markdown_splitted_by_newlines(
                message,
                await Template(
                    settings.group_superadmin_pass_not_approved_message_j2_template, enable_async=True
                ).render_async(users=user_dicts_not_to_save),
            )

        logger.debug(f"Passes to be saved df:\n{passes_to_save_df[['id']]}")
        user_objects_saved: list[dict[str, str | int | None]] = []
        for _, row in passes_to_save_df.iterrows():
            field_id = await session.scalar(select(Field.id).where(Field.key == pass_field_key))
            if not field_id:
                raise GroupPassesNoFieldError

            user_id = int(row["id"])
            field_value = row[pass_field_key]
            await session.execute(
                sql_update(User).where(User.id == user_id).values(pass_status=PassSubmitStatusEnum.APPROVED)
            )
            prev_user_field_value = await session.scalar(
                select(UserFieldValue)
                .where(UserFieldValue.user_id == user_id)
                .where(UserFieldValue.field_id == field_id)
            )
            if not prev_user_field_value:
                await session.execute(
                    insert(UserFieldValue).values(
                        user_id=user_id,
                        field_id=field_id,
                        value=field_value,
                        personal_notification_status=PersonalNotificationStatusEnum.TO_DELIVER,
                    )
                )
            elif field_value != prev_user_field_value.value:
                await session.execute(
                    sql_update(UserFieldValue)
                    .where(UserFieldValue.id == prev_user_field_value.id)
                    .values(
                        value=field_value,
                        personal_notification_status=PersonalNotificationStatusEnum.TO_DELIVER,
                    )
                )

            user_saved = await session.scalar(select(User).where(User.id == user_id))
            if user_saved:
                user_objects_saved += [user_saved.to_plain_dict()]

            logger.success(f"Updated pass field for user {user_id=} and {field_id=}")

        await session.commit()

    await send_long_markdown_splitted_by_newlines(
        message,
        await Template(settings.group_superadmin_pass_approved_message_j2_template, enable_async=True).render_async(
            users=user_objects_saved
        ),
        reply_markup=get_group_default_keyboard(group, settings),
    )

    return ConversationHandler.END
