import os
import yaml
from dotenv import load_dotenv, find_dotenv
from pydantic import (
    BaseModel,
    SecretStr
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from loguru import logger

class Keycloak(BaseModel, extra="forbid"):
    """
    Настройки Keycloak
    """
    url:    str
    realm:  str
    client: str
    secret: SecretStr

class DefaultValue(BaseModel, extra="forbid"):
    """
    Значения по-умолчанию
    """
    description: str
    value:       str

class Defaults(BaseModel, extra="forbid"):
    """
    Все значения настроек по-умолчанию

    Не используются, если БД инициализирована
    """
    my_name:                  DefaultValue
    my_short_description:     DefaultValue
    my_description:           DefaultValue
    help_command_description: DefaultValue

    service_mode_message: DefaultValue
    registration_is_over: DefaultValue

    start_template:           DefaultValue
    first_field_branch:       DefaultValue
    user_document_name_field: DefaultValue

    registration_complete: DefaultValue

    restart_user_template:                 DefaultValue
    help_user_template:                    DefaultValue
    help_restart_on_registration_complete: DefaultValue
    
    user_change_message_reply_template: DefaultValue

    strange_user_error:   DefaultValue
    edited_message_reply: DefaultValue
    error_reply:          DefaultValue
    file_too_large_reply: DefaultValue

    help_normal_group:     DefaultValue
    help_admin_group:      DefaultValue
    help_superadmin_group: DefaultValue
    
    notification_admin_groups_template:                   DefaultValue
    notification_admin_groups_condition_template:         DefaultValue
    notification_planned_admin_groups_template:           DefaultValue
    notification_planned_admin_groups_condition_template: DefaultValue
    
    report_send_every_x_active_users:       DefaultValue
    report_currently_active_users_template: DefaultValue

    pass_user_field:                      DefaultValue
    user_field_to_request_pass:           DefaultValue
    pass_message:                         DefaultValue
    pass_removed_message:                 DefaultValue
    pass_hint_message:                    DefaultValue
    pass_add_field_to_request_value:      DefaultValue
    pass_not_yet_approved_message:        DefaultValue
    pass_submit_message:                  DefaultValue
    pass_submitted_message:               DefaultValue
    pass_submited_superadmin_j2_template: DefaultValue

    personal_notification_jinja_template: DefaultValue
    expired_promocodes_jinja_template:    DefaultValue
    avaliable_promocodes_jinja_template:  DefaultValue

    number_of_last_news_to_show: DefaultValue

    def model_dump_anythig(self, what_to_dump: str) -> dict[str, str]:
        full_dump: dict[str, dict[str, str]] = self.model_dump()
        return {
            key: obj[what_to_dump] for key, obj in full_dump.items()
        }

    def model_dump_values(self) -> dict[str, str]:
        return self.model_dump_anythig('value')

    def model_dump_descriptions(self) -> dict[str, str]:
        return self.model_dump_anythig('description')

class I18n(BaseModel, extra="forbid"):
    """
    Перевод приложения
    """
    yes:  str
    no:   str
    none: str

    there_was_en_error: str

    logout: str
    
    done:  str
    super: str
    
    is_active:    str
    is_inactive:  str
    set_inactive: str
    set_active:   str

    has_been_set_inactive: str
    has_been_set_active:   str
    
    data_empty: str
    register:   str
    
    switch:        str
    groups:        str
    users:         str
    registration:  str
    report:        str
    notifications: str
    keyboard:      str
    settings:      str
    logs:          str

    timestamp: str
    message:   str
    
    key:         str
    description: str
    value:       str

    bot_status: str
    
    on_male:         str
    off_male:        str
    restart_planned: str
    restarting:      str
    service_mode:    str

    turn_on:         str
    turn_off:        str
    restart_normal:  str
    restart_service: str
    
    is_registration_open: str
    registration_opened:  str
    registration_closed:  str
    registration_close:   str
    registration_open:    str

    username: str

    chat_id:     str
    status:      str
    description: str

    group_inactive:     str
    group_normal:       str
    group_admin:        str
    group_super_admin:  str
    group_news_channel: str

    keyboard_keys: str

    reply_condition_message_id: str

    text_markdown: str
    photo_link:    str

    keyboard_key_inactive:   str
    keyboard_key_normal:     str
    keyboard_key_deferred:   str
    keyboard_key_me:         str
    keyboard_key_pass:       str
    keyboard_key_news:       str
    keyboard_key_back:       str
    keyboard_key_me_change:  str
    keyboard_key_promocodes: str

    field_branches: str
    fields:         str

    is_ui_editable:  str
    is_bot_editable: str
    is_deferrable:   str
    next_branch_id:  str

    field_branch_inactive: str
    field_branch_normal:   str
    field_personal_notifiation: str
    field_jinja2_from_user_on_create: str

    order_place:       str
    branch_id:         str
    question_markdown: str
    answer_options:    str
    image_bucket:      str
    document_bucket:   str
    is_boolean:        str

    field_inactive: str
    field_normal:   str

    image:    str
    document: str

    download_users_report: str

    replyable_condition_messages: str
    reply_condition_message_name: str

    condition_bool_field_id: str

    reply_condition_bool_field_id: str

    reply_type: str
    reply_type_branch_start:     str
    reply_type_full_text_answer: str
    reply_type_fast_answer:      str

    reply_answer_field_id:        str
    reply_answer_field_branch_id: str
    reply_keyboard_keys:          str
    reply_status_replies:         str

    notifications: str
    notify_date:   str

    notification_inactive:   str
    notification_to_deliver: str
    notification_planned:    str
    notification_delivered:  str

    defer:   str
    defered: str

    download_file: str

    parent_key_id: str

    change: str
    append: str

    personal_notification_inactive: str
    personal_notification_to_deliver: str
    personal_notification_delivered: str

    promocodes: str

    promocode_active:   str
    promocode_expired:  str
    promocode_inactive: str

    source:      str
    value:       str
    description: str
    expire_at:   str

    validation_regexp:         str
    validation_error_markdown: str
    validation_remove_regexp:  str
    is_skippable:              str

    cancel: str
    skip:   str
    change_canceled: str

    help_pass:     str
    submit_pass:   str
    confirm_pass:  str
    pass_canceled: str

    download_submited: str
    send_approved:     str
    submitted_empty:   str

    send_approved_zip_photos: str
    send_approved_zip_photos_done: str
    send_approved_to_send:  str
    send_approved_canceled: str
    would_not_be_safe:      str
    send_approved_done:     str

    photo_bucket:   str
    photo_filename: str

    news_tag: str

    check_future_date: str
    check_future_year: str

class ConfigYaml(BaseSettings):
    """
    Основной класс конфигурации прилоежния

    Поддерживается установка полей конфигурации при помощи переменных окружения

    Например, `TG_TOKEN`

    В случае, если требуется переписать вложенные словари, следует их разделять символами `__`

    Например, `VOICE_REPLY__RUN_IMMEDIATELY`
    """

    model_config = SettingsConfigDict(env_nested_delimiter='__')

    box_bot_home: str

    tg_token:    str
    path_prefix: str 
    
    pg_user:     str
    pg_password: SecretStr
    
    minio_root_user:     str
    minio_root_password: SecretStr
    minio_secure: bool
    minio_host:   str

    keycloak: Keycloak
    defaults: Defaults
    i18n:     I18n
    
def create_config() -> ConfigYaml:
    """
    Создание конфига из файла и переменных окружения
    """

    load_dotenv(find_dotenv())
    BOX_BOT_HOME = os.getenv('BOX_BOT_HOME')

    if not BOX_BOT_HOME:
        BOX_BOT_HOME = os.getcwd()

    with open(f"{BOX_BOT_HOME}/config/config.yaml", "r") as stream:
        full_config = yaml.safe_load(stream)

    if not full_config:
        full_config = {}
    
    full_config['minio_secure'] = False
    if os.getenv('MINIO_CERTDIR'):
        full_config['minio_secure'] = True

    with open(f"{BOX_BOT_HOME}/config/defaults.yaml", "r") as stream:
        full_config['defaults'] = yaml.safe_load(stream)

    with open(f"{BOX_BOT_HOME}/config/i18n.yaml", "r") as stream:
        full_config['i18n'] = yaml.safe_load(stream)

    config_obj = ConfigYaml(**full_config)
    
    logger.info(f"\n{config_obj.model_dump_json(indent=4)}")

    return config_obj