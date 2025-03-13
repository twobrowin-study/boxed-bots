import os
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from pydantic import BaseModel, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class DefaultValue(BaseModel, extra="forbid"):
    """Значения по-умолчанию"""

    description: str
    value: str


class Defaults(BaseModel, extra="forbid"):
    """
    Все значения настроек по-умолчанию

    Не используются, если БД инициализирована
    """

    bot_my_name_plain: DefaultValue
    bot_my_short_description_plain: DefaultValue
    bot_my_description_plain: DefaultValue
    bot_help_command_description_plain: DefaultValue

    user_service_mode_message_plain: DefaultValue
    user_registration_is_over_message_plain: DefaultValue

    user_start_message_j2_template: DefaultValue
    user_first_field_branch_plain: DefaultValue
    user_name_field_plain: DefaultValue

    user_registration_complete_message_plain: DefaultValue

    user_restart_message_j2_template: DefaultValue
    user_help_message_j2_template: DefaultValue
    user_registered_help_or_restart_message_plain: DefaultValue

    user_change_reply_message_j2_template: DefaultValue
    user_skip_button_plain: DefaultValue
    user_defer_button_plain: DefaultValue
    user_defered_message_plain: DefaultValue
    user_or_group_cancel_button_plain: DefaultValue
    user_field_change_canceled_message_plain: DefaultValue

    user_strange_error_massage_plain: DefaultValue
    user_message_edited_reply_message_plain: DefaultValue
    user_error_message_plain: DefaultValue
    user_file_too_large_message_plain: DefaultValue
    user_file_upload_without_field_context: DefaultValue

    group_normal_help_message_plain: DefaultValue
    group_admin_help_message_plain: DefaultValue
    group_superadmin_help_message_plain: DefaultValue

    group_admin_notification_sent_message_j2_template: DefaultValue
    group_admin_notification_planned_message_j2_template: DefaultValue

    group_admin_report_every_x_active_users_int: DefaultValue
    group_admin_report_currently_active_users_message_j2_template: DefaultValue

    user_pass_field_plain: DefaultValue

    user_pass_registration_button_plain: DefaultValue
    user_pass_submit_button_plain: DefaultValue
    user_pass_confirm_button_plain: DefaultValue
    user_pass_submit_canceled_message_plain: DefaultValue

    user_field_to_request_pass_plain: DefaultValue
    user_pass_message_plain: DefaultValue
    user_pass_removed_message_plain: DefaultValue
    user_pass_hint_message_plain: DefaultValue
    user_pass_add_request_field_value_message_plain: DefaultValue
    user_pass_not_yet_approved_message_plain: DefaultValue
    user_pass_submit_message_plain: DefaultValue
    user_pass_submitted_message_plain: DefaultValue
    group_superadmin_pass_submited_superadmin_message_j2_template: DefaultValue

    group_superadmin_pass_download_submited_button_plain: DefaultValue
    group_superadmin_pass_send_approved_button_plain: DefaultValue
    group_superadmin_pass_submitted_empty_message_plain: DefaultValue
    group_superadmin_pass_send_approved_zip_photos_message_plain: DefaultValue
    group_superadmin_pass_available_approved_zip_photos_done_message_j2_template: DefaultValue
    group_superadmin_pass_send_approved_xlsx_message_plain: DefaultValue
    group_superadmin_pass_approved_canceled_message_plain: DefaultValue
    group_superadmin_pass_approved_message_j2_template: DefaultValue
    group_superadmin_pass_not_approved_message_j2_template: DefaultValue

    user_personal_notification_message_j2_template: DefaultValue
    group_superadmin_expired_promocodes_message_j2_template: DefaultValue
    user_avaliable_promocodes_message_j2_template: DefaultValue

    user_number_of_last_news_to_show_int: DefaultValue

    user_defer_button_plain: DefaultValue
    user_defered_message_plain: DefaultValue

    group_admin_status_report_message_j2_template: DefaultValue

    def model_dump_anythig(self, what_to_dump: str) -> dict[str, str]:
        full_dump: dict[str, dict[str, str]] = self.model_dump()
        return {key: obj[what_to_dump] for key, obj in full_dump.items()}

    def model_dump_values(self) -> dict[str, str]:
        return self.model_dump_anythig("value")

    def model_dump_descriptions(self) -> dict[str, str]:
        return self.model_dump_anythig("description")


class I18n(BaseModel, extra="forbid"):
    """Перевод приложения"""

    yes: str
    no: str

    answer_options: str
    append: str
    bot_is_off: str
    bot_is_on: str
    bot_status: str
    branch_id: str
    bucket: str
    change: str
    chat_id: str
    check_future_date: str
    check_future_year: str
    condition_bool_field_id: str
    data_empty: str
    description: str
    description: str
    description: str
    document_bucket: str
    document: str
    done: str
    download_file: str
    download_users_report: str
    error_answer_options_can_only_be_shown_with_full_text_field: str
    error_bad_field_request: str
    error_cannot_set_parent_key_id_in_keyboard_key_object_while_status_is_news: str
    error_could_not_restore_previous_api_call: str
    error_could_not_update_bot_status: str
    error_could_not_update_settings: str
    error_did_not_found_branch_id_in_keyboard_key_object_while_status_is_me: str
    error_did_not_found_parent_key_id_in_keyboard_key_object_while_status_is_back: str
    error_did_not_found_reply_answer_field_branch_id_in_replyable_condition_message_object_while_status_is_branch_start: str
    error_did_not_found_reply_answer_field_id_in_replyable_condition_message_object_while_status_is_full_text_answer_or_fast_answer: str
    error_did_not_found_reply_condition_message_id_in_keyboard_key_object_while_status_is_normal: str
    error_did_not_update_table: str
    error_field_id_was_not_found: str
    error_field_is_not_in_request: str
    error_field_prefix: str
    error_field_with_bucket_must_have_document_or_image_type: str
    error_field_with_document_or_image_type_must_have_bucket: str
    error_field_with_validation_regexp_should_be_full_text_type: str
    error_field_with_validation_remove_regexp_should_be_full_text_type: str
    error_for_jinja2_field_must_not_be_set_is_skippable_check_future_date_check_future_year_upper_before_save_params: (
        str
    )
    error_found_photo_link_in_replyable_condition_message_while_photo_bucket_or_photo_filename_are_also_in_replyable_condition_message: str
    error_found_unknown_bot_status: str
    error_found_unknown_request_field: str
    error_got_bad_id: str
    error_got_bad_key_value_pair: str
    error_got_bad_user_fields: str
    error_got_not_numeric_field_id: str
    error_got_not_numeric_user_id: str
    error_got_value_error_as: str
    error_group_prefix: str
    error_jinja2_field_should_be_full_text_or_boolean: str
    error_keyboard_key_prefix: str
    error_logout_not_by_get_method_it_mus_be_impossible: str
    error_minio_no_bio: str
    error_new_lines_found_in_reply_keyboard_keys_in_replyable_condition_message_object_while_status_is_full_text_answer_or_branch_start: str
    error_no_name_or_text_markdown_in_replyable_condition_message: str
    error_reply_type_is_set_but_there_is_no_reply_keyboard_keys_or_reply_status_replies: str
    error_replyable_condition_message_prefix: str
    error_should_be_numeric_but_got: str
    error_should_set_both_photo_bucket_and_photo_filename_at_the_same_time: str
    error_there_is_no_field_branches: str
    error_trying_to_set_pass_managment_to_non_admin_group: str
    error_value_not_directory_field_value: str
    error_value_not_in_field_value: str
    expire_at: str
    field_branch_inactive: str
    field_branch_normal: str
    field_branches: str
    field_inactive: str
    field_jinja2_from_user_after_registration: str
    field_jinja2_from_user_on_create: str
    field_normal: str
    field_personal_notifiation: str
    field_type_boolean: str
    field_type_full_text: str
    field_type_image: str
    field_type_pdf_document: str
    field_type_zip_document: str
    fields: str
    group_admin: str
    group_inactive: str
    group_news_channel: str
    group_normal: str
    group_super_admin: str
    groups: str
    image_bucket: str
    image: str
    is_active: str
    is_boolean: str
    is_bot_editable: str
    is_deferrable: str
    is_inactive: str
    is_registration_open: str
    is_skippable: str
    is_ui_editable: str
    key: str
    keyboard_key_back: str
    keyboard_key_deferred: str
    keyboard_key_inactive: str
    keyboard_key_me_change: str
    keyboard_key_me: str
    keyboard_key_news: str
    keyboard_key_normal: str
    keyboard_key_pass: str
    keyboard_key_promocodes: str
    keyboard_keys: str
    keyboard: str
    logout: str
    logs: str
    message: str
    new_record: str
    news_tag: str
    next_branch_id: str
    none: str
    notification_delivered: str
    notification_inactive: str
    notification_planned: str
    notification_to_deliver: str
    notifications: str
    notifications: str
    order_place: str
    parent_key_id: str
    pass_management: str
    personal_notification_delivered: str
    personal_notification_inactive: str
    personal_notification_to_deliver: str
    photo_bucket: str
    photo_filename: str
    photo_link: str
    promocode_active: str
    promocode_expired: str
    promocode_inactive: str
    promocodes: str
    question_markdown_or_j2_template: str
    register: str
    registration_close: str
    registration_closed: str
    registration_open: str
    registration_opened: str
    registration_set_active: str
    registration_set_inactive: str
    registration: str
    reply_answer_field_branch_id: str
    reply_answer_field_id: str
    reply_condition_bool_field_id: str
    reply_condition_message_id: str
    reply_condition_message_name: str
    reply_keyboard_keys: str
    reply_status_replies: str
    reply_type_branch_start: str
    reply_type_fast_answer: str
    reply_type_full_text_answer: str
    reply_type: str
    replyable_condition_messages: str
    report_order: str
    report: str
    restart_normal: str
    restart_planned: str
    restart_service: str
    restarting: str
    schedule_datetime: str
    service_mode: str
    set_active: str
    set_inactive: str
    settings: str
    source: str
    status: str
    super: str
    text_markdown: str
    there_was_en_error: str
    timestamp: str
    turn_off: str
    turn_on: str
    type_error_markdown: str
    type: str
    upper_before_save: str
    username: str
    users: str
    validation_error_markdown: str
    validation_regexp: str
    validation_remove_regexp: str
    value: str
    value: str


class ConfigYaml(BaseSettings):
    """
    Основной класс конфигурации прилоежния

    Поддерживается установка полей конфигурации при помощи переменных окружения

    Например, `TG_TOKEN`

    В случае, если требуется переписать вложенные словари, следует их разделять символами `__`

    Например, `VOICE_REPLY__RUN_IMMEDIATELY`
    """

    model_config = SettingsConfigDict(env_nested_delimiter="__")

    tz: str

    app_home: str

    path_secure: str
    path_prefix: str

    tg_token: str

    postgres_host: str
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr

    minio_host: str
    minio_secure: bool
    minio_access_key: str
    minio_secret_key: SecretStr

    keycloak_url: str
    keycloak_realm: str
    keycloak_client: str
    keycloak_secret: SecretStr
    keycloak_verify: bool

    defaults: Defaults
    i18n: I18n


def create_config() -> ConfigYaml:
    """
    Создание конфига из файла и переменных окружения
    """

    load_dotenv(find_dotenv())

    configs = Path.cwd() / "config"

    with Path.open(configs / "config.yaml") as stream:
        full_config = yaml.safe_load(stream)

    if not full_config:
        full_config = {}

    if not os.getenv("MINIO_SECURE"):
        full_config["minio_secure"] = False
        if os.getenv("MINIO_CERTDIR"):
            full_config["minio_secure"] = True

    with Path.open(configs / "defaults.yaml") as stream:
        full_config["defaults"] = yaml.safe_load(stream)

    with Path.open(configs / "i18n.yaml") as stream:
        full_config["i18n"] = yaml.safe_load(stream)

    config_obj = ConfigYaml(**full_config)

    logger.debug(f"\n{config_obj.model_dump_json(indent=4)}")

    return config_obj
