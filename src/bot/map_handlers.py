from loguru import logger
from telegram.ext import (
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
)
from telegram.ext.filters import COMMAND, PHOTO, TEXT, ChatType, Document, UpdateType

from src.bot.exceptions import JobQueueNotFoundError
from src.bot.handlers.groups import base_handlers as groups_base_handlers
from src.bot.handlers.groups import pass_handlers as groups_pass_handlers
from src.bot.handlers.users import branch_start_callback_handlers as user_branch_start_callback_handlers
from src.bot.handlers.users import change_callback_handlers as user_change_callback_handlers
from src.bot.handlers.users import fast_answer_callback_handlers as user_fast_answer_callback_handlers
from src.bot.handlers.users import full_text_answer_callback_handlers as user_full_text_answer_callback_handlers
from src.bot.handlers.users import pass_submit_handlers as user_pass_submit_handlers
from src.bot.handlers.users import start_help_handlers as user_start_help_handlers
from src.bot.handlers.users import text_file_handlers as user_text_file_handlers
from src.bot.jobs import expired_promocodes, notifications, personal_notifications
from src.bot.telegram import default_handlers
from src.bot.telegram.application import BBApplication
from src.bot.telegram.callback_constants import (
    GroupApprovePassesConversation,
    UserChangeFieldCallback,
    UserChangePassFieldCallback,
    UserFastAnswerReplyCallback,
    UserFullTextAnswerReplyCallback,
    UserStartBranchReplyCallback,
    UserSubmitPassCallback,
)


def map_service_mode_handlers(app: BBApplication) -> None:
    """
    Добавить обработчик сообщений в сервисном режиме бота
    """
    app.add_handler(
        MessageHandler(ChatType.PRIVATE | ChatType.GROUPS, default_handlers.service_mode_handler, block=False)
    )


def map_default_handlers(app: BBApplication) -> None:
    """
    Добавить стандартные обработчики событий
    """
    ##
    # Chat member handlers
    ##
    app.add_handler(
        ChatMemberHandler(
            default_handlers.chat_member_handler,
            chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER,
            block=False,
        ),
        group=app.UPDATE_GROUP_CHAT_MEMBER,
    )

    ##
    # Default user handlers
    ##
    app.add_handler(
        MessageHandler(UpdateType.EDITED, default_handlers.eddited_handler, block=False),
        group=app.UPDATE_GROUP_USER_REQUEST,
    )

    ##
    # Group handlers
    ##
    app.add_handler(
        ConversationHandler(
            entry_points=[
                MessageHandler(
                    TEXT & ~COMMAND & ChatType.GROUP,
                    groups_pass_handlers.text_key_button_handler,
                ),
            ],
            states={
                GroupApprovePassesConversation.ZIP_AWAIT: [
                    MessageHandler(
                        Document.ZIP & ChatType.GROUP,
                        groups_pass_handlers.upload_aproved_passes_zip_document_handler,
                    ),
                ],
                GroupApprovePassesConversation.XLSX_AWAIT: [
                    MessageHandler(
                        Document.ALL & ChatType.GROUP,
                        groups_pass_handlers.upload_aproved_passes_xlsx_document_handler,
                    ),
                ],
            },
            fallbacks=[
                MessageHandler(
                    TEXT & ChatType.GROUP,
                    groups_pass_handlers.text_key_button_handler,
                ),
                CommandHandler(app.HELP_COMMAND, groups_base_handlers.help_handler, filters=ChatType.GROUPS),
            ],
            block=False,
        ),
        group=app.UPDATE_GROUP_GROUP_REQUEST,
    )

    app.add_handlers(
        [
            CommandHandler(
                app.HELP_COMMAND,
                groups_base_handlers.help_handler,
                filters=ChatType.GROUPS,
                block=False,
            ),
            CommandHandler(
                app.REPORT_COMMAND,
                groups_base_handlers.report_handler,
                filters=ChatType.GROUPS,
                block=False,
            ),
            MessageHandler(
                ChatType.CHANNEL & ~UpdateType.EDITED,
                groups_base_handlers.channel_publication_handler,
                block=False,
            ),
        ],
        group=app.UPDATE_GROUP_GROUP_REQUEST,
    )

    ##
    # User handlers
    ##
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    user_pass_submit_handlers.start_callback_handler,
                    pattern=UserSubmitPassCallback.PATTERN,
                )
            ],
            states={
                UserSubmitPassCallback.STATE_SUBMIT_AWAIT: [
                    MessageHandler(
                        TEXT & ChatType.PRIVATE,
                        user_pass_submit_handlers.approve_handler,
                    )
                ]
            },
            fallbacks=[
                CommandHandler(
                    app.HELP_COMMAND,
                    user_start_help_handlers.handler,
                    filters=ChatType.PRIVATE,
                    block=False,
                ),
            ],
            block=False,
        ),
        group=app.UPDATE_GROUP_USER_REQUEST,
    )

    app.add_handlers(
        [
            CommandHandler(
                app.START_COMMAND,
                user_start_help_handlers.handler,
                filters=ChatType.PRIVATE,
                block=False,
            ),
            CommandHandler(
                app.HELP_COMMAND,
                user_start_help_handlers.handler,
                filters=ChatType.PRIVATE,
                block=False,
            ),
        ],
        group=app.UPDATE_GROUP_USER_REQUEST,
    )

    app.add_handler(
        MessageHandler(
            ChatType.PRIVATE & (TEXT | PHOTO | Document.IMAGE | Document.ZIP | Document.PDF),
            user_text_file_handlers.handler,
            block=False,
        ),
        group=app.UPDATE_GROUP_USER_REQUEST,
    )

    app.add_handlers(
        [
            CallbackQueryHandler(
                user_change_callback_handlers.handler,
                pattern=UserChangeFieldCallback.PATTERN,
                block=False,
            ),
            CallbackQueryHandler(
                user_pass_submit_handlers.change_field_value_callback_handler,
                pattern=UserChangePassFieldCallback.PATTERN,
                block=False,
            ),
            CallbackQueryHandler(
                user_branch_start_callback_handlers.handler,
                pattern=UserStartBranchReplyCallback.PATTERN,
                block=False,
            ),
            CallbackQueryHandler(
                user_full_text_answer_callback_handlers.handler,
                pattern=UserFullTextAnswerReplyCallback.PATTERN,
                block=False,
            ),
            CallbackQueryHandler(
                user_fast_answer_callback_handlers.handler,
                pattern=UserFastAnswerReplyCallback.PATTERN,
                block=False,
            ),
        ],
        group=app.UPDATE_GROUP_USER_REQUEST,
    )

    if not app.job_queue:
        raise JobQueueNotFoundError

    app.job_queue.run_once(notifications.job, when=1, name="notifications_first_time")
    app.job_queue.run_repeating(notifications.job, interval=10, name="notifications")
    app.job_queue.run_repeating(personal_notifications.job, interval=10, name="personal_notifications")
    app.job_queue.run_repeating(expired_promocodes.job, interval=10, name="expired_promocodes")
    logger.info("Starting notify jobs")
