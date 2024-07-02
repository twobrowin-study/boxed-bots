from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from sqlalchemy import select, insert, update as sql_update
from sqlalchemy.ext.asyncio.session import AsyncSession

import io
from loguru import logger
import pandas as pd
from datetime import datetime
from xlsxwriter.worksheet import Worksheet

from utils.db_model import Group, NewsPost, User, Field, UserFieldValue
from utils.custom_types import GroupStatusEnum, QrCodeSubmitStatus, PersonalNotificationStatusEnum

from bot.application import BBApplication
from bot.helpers.send_to_all import (
    send_to_all_coroutines_awaited,
    send_to_all_coroutines_tasked
)

from bot.callback_constants import GroupApproveQrConversation

async def group_send_to_all_superadmin_awaited(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем суперадминам с ожиданием окончания отправки
    """
    await send_to_all_coroutines_awaited(
        app=app, table=Group,
        selector=(Group.status == GroupStatusEnum.SUPER_ADMIN),
        message=message, parse_mode=parse_mode
    )

async def group_send_to_all_superadmin_tasked(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем суперадминам в виде параллельной задачи
    """
    await send_to_all_coroutines_tasked(
        app=app, table=Group,
        selector=(Group.status == GroupStatusEnum.SUPER_ADMIN),
        message=message, parse_mode=parse_mode,
        update={'update': 'group_send_to_all_superadmins_tasked', 'message': message}
    )

async def group_send_to_all_superadmin_tasked(
        app: BBApplication, message: str, parse_mode: ParseMode,
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None,
        session: AsyncSession = None, 
    ) -> None:
    """
    Отправить сообщение всем суперадминам в виде параллельной задачи
    """
    await send_to_all_coroutines_tasked(
        app=app, table=Group,
        selector=(Group.status == GroupStatusEnum.SUPER_ADMIN),
        message=message, parse_mode=parse_mode,
        update={'update': 'group_send_to_all_superadmins_tasked', 'message': message},
        session=session, reply_markup=reply_markup
    )

async def group_send_to_all_admin_tasked(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем админам и суперадминам в виде параллельной задачи
    """
    await send_to_all_coroutines_tasked(
        app=app, table=Group,
        selector=((Group.status == GroupStatusEnum.ADMIN) | (Group.status == GroupStatusEnum.SUPER_ADMIN)) ,
        message=message, parse_mode=parse_mode,
        update={'update': 'group_send_to_all_admins_tasked', 'message': message}
    )

async def group_send_to_all_normal_tasked(app: BBApplication, message: str, parse_mode: ParseMode) -> None:
    """
    Отправить сообщение всем обычным группам в виде параллельно задачи
    """
    await send_to_all_coroutines_tasked(
        app=app, table=Group,
        selector=(Group.status == GroupStatusEnum.NORMAL),
        message=message, parse_mode=parse_mode,
        update={'update': 'group_send_to_all_normal_tasked', 'message': message}
    )

async def _get_group_by_chat_id_or_none(app: BBApplication, chat_id: int) -> Group|None:
    """
    Найти группу по заданносу ИД чата
    """
    async with app.provider.db_session() as session:
        selected = await session.execute(
            select(Group)
            .where(
                (Group.chat_id == chat_id) &
                (Group.status  != GroupStatusEnum.INACTIVE)
            )
            .limit(1)
        )
        return selected.scalar_one_or_none()

async def group_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды помощи для группы
    """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)
    if not group:
        logger.info(f"Got start/help command from unknown group {chat_id=} and {group_name=}")
        return ConversationHandler.END

    settings = await app.provider.settings

    logger.info(f"Got start/help command from group {chat_id=} and {group_name=} as {group.status=}")
    
    if group.status == GroupStatusEnum.NORMAL:
        await update.message.reply_markdown(settings.help_normal_group)
        return ConversationHandler.END
    
    if group.status == GroupStatusEnum.ADMIN:
        await update.message.reply_markdown(settings.help_admin_group)
        return ConversationHandler.END
    
    if group.status == GroupStatusEnum.SUPER_ADMIN:
        await update.message.reply_markdown(
            settings.help_superadmin_group,
            reply_markup=ReplyKeyboardMarkup([
                [app.provider.config.i18n.download_submited],
                [app.provider.config.i18n.send_approved],
            ])
        )
        return ConversationHandler.END

async def group_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды на получение отчёта для групп администраторов или суперадминистраторов
    """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)

    if not group:
        return logger.info(f"Got report command from unknown group {chat_id=} and {group_name=}")
    
    if not group or group.status not in [GroupStatusEnum.ADMIN, GroupStatusEnum.SUPER_ADMIN]:
        return logger.info(f"Got report command from group {chat_id=} and {group_name=} as {group.status=}... ignoring")
    
    logger.info(f"Got report command from group {chat_id=} and {group_name=} as {group.status=}")
    
    await update.message.reply_markdown("Here will be kinda report")

async def channel_publication_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик публикации в канале новостей
    """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)

    if not group:
        return logger.info(f"Got publication from unknown group {chat_id=} and {group_name=}")
    
    if group.status != GroupStatusEnum.NEWS_CHANNEL:
        return logger.info(f"Got publication from group {chat_id=} and {group_name=} as {group.status=}... ignoring")
    
    if update.effective_message.text == None and update.effective_message.caption == None:
        return logger.warning(f"Got publication from group {chat_id=} and {group_name=} as {group.status=} without text, so it is propably is on of previuos post photo... ignoring")
    
    logger.info(f"Got publication from group {chat_id=} and {group_name=} as {group.status=}")
    
    message_id = update.effective_message.id
    async with app.provider.db_session() as session:
        await session.execute(
            insert(NewsPost).values(
                chat_id = chat_id,
                message_id = message_id
            )
        )
        await session.commit()
        logger.success(f"Added new news publication from {chat_id=} with {message_id=}")

async def group_download_submited_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ответ на нажатие кнопки для скачивания всех пользователей, подавших заявку на получение QR кода"""
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)

    if not group or group.status != GroupStatusEnum.SUPER_ADMIN:
        return logger.info(f"Got download submitted from unknown group {chat_id=} and {group_name=}")

    async with app.provider.db_session() as session:
        users_selected = await session.execute(
            select(User)
            .where(User.qr_code_status == QrCodeSubmitStatus.SUBMITED)
            .order_by(User.id.asc())
        )
        users_df = pd.DataFrame([
            user.to_plain_dict(i18n=app.provider.config.i18n)
            for user in users_selected.scalars()
        ])

        logger.debug(f"Users df:\n{users_df}")

        if users_df.empty:
            return await update.effective_message.reply_markdown(app.provider.config.i18n.submitted_empty)
        
        filename = f"{datetime.now().strftime('%Y_%m_%d__%H_%M_%S')}__submitted_qr_codes_report.xlsx"

        sheet_name = app.provider.config.i18n.download_users_report
        
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
        await update.effective_message.reply_document(report_bio, filename=filename)

async def group_upload_aproved_qr_xlsx_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик нажатия на кнопку старта отправки """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)

    if not group or group.status != GroupStatusEnum.SUPER_ADMIN:
        logger.info(f"Got upload approved start from unknown group {chat_id=} and {group_name=}")
        return ConversationHandler.END
    
    await update.effective_message.reply_markdown(
        app.provider.config.i18n.send_approved_to_send,
        reply_markup=ReplyKeyboardMarkup([
            [app.provider.config.i18n.cancel],
        ])
    )
    
    return GroupApproveQrConversation.XLSX_AWAIT

async def group_upload_aproved_qr_xlsx_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик нажатия на кнопку старта отправки """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)

    if not group or group.status != GroupStatusEnum.SUPER_ADMIN:
        logger.info(f"Got approved cancel from unknown group {chat_id=} and {group_name=}")
        return ConversationHandler.END
    
    await update.effective_message.reply_markdown(
        app.provider.config.i18n.send_approved_canceled,
        reply_markup=ReplyKeyboardMarkup([
            [app.provider.config.i18n.download_submited],
            [app.provider.config.i18n.send_approved],
        ])
    )
    
    return ConversationHandler.END

async def group_upload_aproved_qr_xlsx_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик нажатия на кнопку старта отправки """
    app: BBApplication = context.application
    chat_id    = update.effective_chat.id
    group_name = update.effective_chat.effective_name
    group      = await _get_group_by_chat_id_or_none(app, chat_id)
    settings   = await app.provider.settings

    if not group or group.status != GroupStatusEnum.SUPER_ADMIN:
        logger.info(f"Got upload approved from unknown group {chat_id=} and {group_name=}")
        return ConversationHandler.END
    
    file = await update.effective_message.document.get_file()

    bio = io.BytesIO()
    await file.download_to_memory(bio)
    bio.seek(0)

    qrs_df = pd.read_excel(bio)

    logger.debug(f"Qrs df:\n{qrs_df}")

    qr_field_key   = settings.qr_code_user_field
    name_field_key = settings.user_document_name_field

    qrs_to_save_df = qrs_df.loc[
        ~qrs_df[qr_field_key].isin(["", None]) &
        qrs_df[qr_field_key].notna() &
        qrs_df[qr_field_key].notnull()
    ]

    logger.debug(f"Qrs to be saved df:\n{qrs_to_save_df[["id", name_field_key]]}")

    async with app.provider.db_session() as session:
        for _,row in qrs_to_save_df.iterrows():
            field_id = await session.scalar(select(Field.id).where(Field.key == qr_field_key))
            if not field_id:
                raise Exception(f"Not found field with key {qr_field_key=}")
            
            user_id     = int(row["id"])
            field_value = row[qr_field_key]
            await session.execute(
                sql_update(User)
                .where(User.id == user_id)
                .values(qr_code_status = QrCodeSubmitStatus.APPROVED)
            )
            prev_field = await session.scalar(
                select(UserFieldValue)
                .where(UserFieldValue.user_id  == user_id)
                .where(UserFieldValue.field_id == field_id)
            )
            if not prev_field:
                await session.execute(
                    insert(UserFieldValue)
                    .values(
                        user_id  = user_id,
                        field_id = field_id,
                        value    = field_value,
                        personal_notification_status = PersonalNotificationStatusEnum.TO_DELIVER
                    )
                )

            if prev_field and field_value != prev_field.value:
                await session.execute(
                    sql_update(UserFieldValue)
                    .where(UserFieldValue.id == prev_field.id)
                    .values(
                        value = field_value,
                        personal_notification_status = PersonalNotificationStatusEnum.TO_DELIVER
                    )
                )
            
            logger.info(f"Updated qr code field for user {user_id=} and {field_id=}")
        
        await session.commit()
        
    done_names = "\n".join(qrs_to_save_df[name_field_key].values)
    await update.effective_message.reply_markdown(
        f"{app.provider.config.i18n.send_approved_done}\n\n{done_names}",
        reply_markup=ReplyKeyboardMarkup([
            [app.provider.config.i18n.download_submited],
            [app.provider.config.i18n.send_approved],
        ])
    )
    
    return ConversationHandler.END