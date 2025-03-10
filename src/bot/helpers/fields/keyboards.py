from typing import Literal

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

from src.utils.db_model import Field, Settings


def construct_field_reply_keyboard_markup(
    field: Field, settings: Settings, context: Literal["full_text_answer", "change_user_field_value"]
) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """
    Получить клавиатуру по строке вариантов ответов

    Параметры:
     * field: Field - Поле
     * settings: Settings - настройки приложения
     * context: Literal["full_text_answer", "change_user_field_value"] - контекст полнотекстового ответа на вопрос или изменение значения
    """
    bottom_buttons = []

    if context == "full_text_answer" and field.branch.is_deferrable:
        bottom_buttons.append([settings.user_defer_button_plain])

    if context == "full_text_answer" and field.is_skippable:
        bottom_buttons.append([settings.user_skip_button_plain])

    if context == "change_user_field_value":
        bottom_buttons.append([settings.user_or_group_cancel_button_plain])

    if not field.answer_options and bottom_buttons:
        return ReplyKeyboardMarkup(bottom_buttons)

    if not field.answer_options:
        return ReplyKeyboardRemove()

    return ReplyKeyboardMarkup([[key] for key in field.answer_options.split("\n")] + bottom_buttons)
