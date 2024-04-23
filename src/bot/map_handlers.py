from telegram.ext import (
    MessageHandler,
    ChatMemberHandler,
    CommandHandler,
    CallbackQueryHandler
)

from telegram.ext.filters import (
    ChatType, UpdateType,
    TEXT, PHOTO, Document
)

from loguru import logger

from bot.application import BBApplication

from bot.handlers.default import (
    service_mode_handler,
    chat_member_handler,
    eddited_handler
)

from bot.handlers.group import (
    group_help_handler,
    group_report_handler,
)

from bot.handlers.user import (
    user_start_help_handler,
    user_message_text_handler,
    user_message_photo_document_handler,
    user_change_state_callback,
    branch_start_callback_handler,
    full_text_callback_handler,
    fast_answer_callback_handler
)

from bot.handlers.notification import notify_job

from bot.callback_constants import (
    UserChangeFieldCallback,
    UserStartBranchReplyCallback,
    UserFullTextAnswerReplyCallback,
    UserFastAnswerReplyCallback
)

def map_service_mode_handlers(app: BBApplication) -> None:
    """
    Добавить обработчик сообщений в сервисном режиме бота
    """
    app.add_handler(MessageHandler(ChatType.PRIVATE | ChatType.GROUPS, service_mode_handler, block=False))

def map_default_handlers(app: BBApplication) -> None:
    """
    Добавить стандартные обработчики событий
    """
    ##
    # Chat member handlers
    ##
    app.add_handler(
        ChatMemberHandler(chat_member_handler, chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER, block=False),
        group=app.UPDATE_GROUP_CHAT_MEMBER
    )

    ##
    # Default user handlers
    ##
    app.add_handler(
        MessageHandler(UpdateType.EDITED, eddited_handler, block=False),
        group=app.UPDATE_GROUP_USER_REQUEST
    )

    ##
    # Group handlers
    ##
    app.add_handlers([
        CommandHandler(app.HELP_COMMAND,   group_help_handler, filters=ChatType.GROUPS, block=False),
        CommandHandler(app.REPORT_COMMAND, group_report_handler, filters=ChatType.GROUPS, block=False),
    ], group=app.UPDATE_GROUP_GROUP_REQUEST)

    ##
    # User handlers
    ##
    app.add_handlers([
        CommandHandler(app.START_COMMAND, user_start_help_handler, filters=ChatType.PRIVATE, block=False),
        CommandHandler(app.HELP_COMMAND,  user_start_help_handler, filters=ChatType.PRIVATE, block=False),
    ], group=app.UPDATE_GROUP_USER_REQUEST)

    app.add_handlers([
        MessageHandler(ChatType.PRIVATE & TEXT,                                user_message_text_handler,           block=False),
        MessageHandler(ChatType.PRIVATE & (PHOTO|Document.IMAGE|Document.ZIP), user_message_photo_document_handler, block=False),
    ], group=app.UPDATE_GROUP_USER_REQUEST)

    app.add_handlers([
        CallbackQueryHandler(user_change_state_callback,    pattern=UserChangeFieldCallback.PATTERN,         block=False),
        CallbackQueryHandler(branch_start_callback_handler, pattern=UserStartBranchReplyCallback.PATTERN,    block=False),
        CallbackQueryHandler(full_text_callback_handler,    pattern=UserFullTextAnswerReplyCallback.PATTERN, block=False),
        CallbackQueryHandler(fast_answer_callback_handler,  pattern=UserFastAnswerReplyCallback.PATTERN,     block=False),
    ], group=app.UPDATE_GROUP_USER_REQUEST)

    app.job_queue.run_once(notify_job, when=1)
    app.job_queue.run_repeating(notify_job, interval=10)
    logger.info("Starting notify job")
