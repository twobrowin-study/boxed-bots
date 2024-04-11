# CALLBACK_USER_SET_INACTIVE         = 'user_set_inactive'
# CALLBACK_USER_SET_ACTIVE           = 'user_set_active'
# CALLBACK_USER_ACTIVE_STATE_PATTERN = 'user_set_(in|)active'


class UserChangeFieldCallback:
    """
    Тип данных для регистрации кнопок изменения состояния пользователей
    """
    PREFIX   = 'user_change_'
    """Префикс"""
    TEMPLATE = 'user_change_{field_id}'
    """Шаблон данных"""
    PATTERN  = 'user_change_[0-9]+'
    """Паттерн регулярног выражения"""