class UserChangeFieldCallback:
    """Тип данных для регистрации кнопок изменения состояния пользователей"""
    PREFIX   = 'user_change_'
    """Префикс"""
    TEMPLATE = 'user_change_{field_id}'
    """Шаблон данных"""
    PATTERN  = 'user_change_[0-9]+'
    """Паттерн регулярног выражения"""

class UserStartBranchReplyCallback:
    """Тип данных для регистрации кнопки начала заполнения ветки вопросов"""
    PREFIX   = 'branch_start_'
    """Префикс"""
    SPLIT    = '|'
    """Разделитель данных"""
    TEMPLATE = 'branch_start_{reply_message_id}|{branch_id}'
    """Шаблон данных"""
    PATTERN  = 'branch_start_[0-9]+|[0-9]+'
    """Паттерн регулярног выражения"""

class UserFullTextAnswerReplyCallback:
    """Тип данных для регистрации кнопки заполнения вопроса"""
    PREFIX   = 'full_text_answer_'
    """Префикс"""
    SPLIT    = '|'
    """Разделитель данных"""
    TEMPLATE = 'full_text_answer_{reply_message_id}|{field_id}'
    """Шаблон данных"""
    PATTERN  = 'full_text_answer_[0-9]+|[0-9]+'
    """Паттерн регулярног выражения"""

class UserFastAnswerReplyCallback:
    """Тип данных для регистрации кнопок быстрых ответов на вопросы"""
    PREFIX   = 'fast_answer_'
    """Префикс"""
    SPLIT    = '|'
    """Разделитель данных"""
    TEMPLATE = 'fast_answer_{reply_message_id}|{field_id}|{answer_idx}'
    """Шаблон данных"""
    PATTERN  = 'fast_answer_[0-9]+|[0-9]+|[0-9]+'
    """Паттерн регулярног выражения"""

class UserSubmitQrCallback:
    """Тип данных для регистрации кнопки отправки заявки на qr код"""
    PATTERN = 'submit_qr'
    STATE_SUBMIT_AWAIT = 1

class GroupApproveQrConversation:
    """Тип данных для регистрации статусов выгрузки таблицы пользователей с подтверждёнными qr кодами"""
    XLSX_AWAIT = 1