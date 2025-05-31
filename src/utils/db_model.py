from datetime import datetime
from typing import Literal

from sqlalchemy import BigInteger, Column, ForeignKey, Integer
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)

from src.utils.config_model import I18n
from src.utils.custom_types import (
    BotStatusEnum,
    FieldBranchStatusEnum,
    FieldStatusEnum,
    FieldTypeEnum,
    GroupStatusEnum,
    KeyboardKeyStatusEnum,
    NotificationStatusEnum,
    PassSubmitStatusEnum,
    PersonalNotificationStatusEnum,
    PromocodeStatusEnum,
    ReplyTypeEnum,
    UserDataPrepared,
    UserFieldDataPlain,
    UserFieldDataPrepared,
    UserStatusEnum,
)


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class BotStatus(Base):
    """Выключение и текущее состояние бота"""

    __tablename__ = "bot_status"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    bot_status: Mapped[BotStatusEnum] = mapped_column(default=BotStatusEnum.ON, nullable=False)
    """Cтатус бота"""
    is_registration_open: Mapped[bool] = mapped_column(default=True, nullable=False)
    """Статус открытия регстрации"""


class Group(Base):
    """Группа, в которую бот будет высылать уведомления"""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    chat_id: Mapped[int] = mapped_column(nullable=False, index=True, unique=True, type_=BigInteger)
    """Идентификатор чата"""
    status: Mapped[GroupStatusEnum] = mapped_column(nullable=False, default=GroupStatusEnum.INACTIVE)
    """Статус группы"""
    pass_management: Mapped[bool] = mapped_column(nullable=False, default=False)
    """Разрешение группе управления пропусками (только для админов и суперадминов)"""
    description: Mapped[str | None] = mapped_column(default=None)
    """Описание группы"""


class FieldBranch(Base):
    """Ветки вопросов пользователей"""

    __tablename__ = "field_branches"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    key: Mapped[str] = mapped_column(nullable=False, index=True, unique=True)
    """Уникальный ключ ветки полей"""
    status: Mapped[FieldBranchStatusEnum] = mapped_column(nullable=False, default=FieldBranchStatusEnum.INACTIVE)
    """Статус ветки полей"""

    order_place: Mapped[int] = mapped_column(nullable=False, default=0)
    """Номер по порядку"""

    is_ui_editable: Mapped[bool] = mapped_column(default=True, nullable=False)
    """Можно менять в UI интерфейсе"""
    is_bot_editable: Mapped[bool] = mapped_column(default=True, nullable=False)
    """Можно менять в боте"""
    is_deferrable: Mapped[bool] = mapped_column(default=True, nullable=False)
    """Можно отложить"""

    next_branch_id: Column[int | None] = Column(Integer, ForeignKey("field_branches.id"), nullable=True)  # type: ignore
    """Следующая ветка вопросов"""


class Field(Base):
    """Поле данных пользователя"""

    __tablename__ = "fields"

    branch: FieldBranch = relationship("FieldBranch", lazy="selectin")  # type: ignore
    """Объект ветки поля"""

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    key: Mapped[str] = mapped_column(nullable=False, index=True, unique=True)
    """Уникальный ключ поля"""
    status: Mapped[FieldStatusEnum] = mapped_column(nullable=False, default=FieldStatusEnum.INACTIVE)
    """Статус поля"""
    type: Mapped[FieldTypeEnum] = mapped_column(nullable=False, default=FieldTypeEnum.FULL_TEXT)
    """Тип значения поля"""

    order_place: Mapped[int] = mapped_column(nullable=False, default=0)
    """Номер по порядку в ветке"""

    branch_id: Column[int] = Column(Integer, ForeignKey(FieldBranch.id), nullable=False)
    """Идентификатор ветки"""

    question_markdown_or_j2_template: Mapped[str | None] = mapped_column(default=None)
    """Вопрос markdown или шаблон значения поля"""

    type_error_markdown: Mapped[str | None] = mapped_column(default=None)
    """
    Сообщение пользователю в случае ошибки типа

    Если не заполнять, то будет выслан повтор вопроса
    """

    validation_regexp: Mapped[str | None] = mapped_column(default=None)
    """Регулярное выражение проверки значения поля"""
    validation_remove_regexp: Mapped[str | None] = mapped_column(default=None)
    """Регулярное выражение для удаления"""
    validation_error_markdown: Mapped[str | None] = mapped_column(default=None)
    """
    Сообщение пользователю в случае ошибки валидации

    Если не заполнять, то будет выслан повтор вопроса
    """

    answer_options: Mapped[str | None] = mapped_column(default=None)
    """Варианты ответа через перенос строки"""

    bucket: Mapped[str | None] = mapped_column(default=None)
    """Бакет пользовательских файлов"""

    is_skippable: Mapped[bool] = mapped_column(default=False)
    """Можно ли пропустить вопрос"""

    check_future_date: Mapped[bool] = mapped_column(default=False)
    """Указание на проверку даты из будущего"""
    check_future_year: Mapped[bool] = mapped_column(default=False)
    """Указание на проверку года из будущег"""

    upper_before_save: Mapped[bool] = mapped_column(default=False)
    """Преобразовать в верхний регистр перед сохранением"""

    report_order: Mapped[int | None] = mapped_column(default=None, unique=True)
    """Порядок отображения поля в отчёте, для попадания в отчёт должно быть больше 1"""


class ReplyableConditionMessage(Base):
    """
    Абстрактное сообщение, которое обладает настройками:
    * Обязательно содержит уникальное текстовое имя для указания в ui

    * Обязательно содержит текст сообщения
    * Может содержать ссылку на фото для отправки

    * Может содержать указание на булево поле, определяющее условие отображения у пользователя

    * Может содержать указание на булево поле, определяющее возможность пользователя использовать inline-клавиатуру для ответа
    * Может содержать тип ответа: начало ветки вопросов, полнотестовый ответ на один вопрос или быстрый ответ из списка

    * Может содержать указание на поле, куда будет записан ответ пользователя
    * Может содержать указание на ветку, которая будет использована для записи ответов пользователей

    * Может содержать указание на строчки отображаемых кнопок
    * Может содержать указание на строчки ответов
    """

    __tablename__ = "replyable_condition_message"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    name: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    """Уникальное название"""

    text_markdown: Mapped[str] = mapped_column()
    """Тест в разметке Markdown"""
    photo_link: Mapped[str | None] = mapped_column(nullable=True, default=None)
    """Ссылка на изображение"""

    photo_bucket: Mapped[str | None] = mapped_column(default=None)
    """Бакет, в котором хранится фото, отправляемое вместе с сообщением"""
    photo_filename: Mapped[str | None] = mapped_column(default=None)
    """Название фото в хранилище S3"""
    photo_file_id: Mapped[str | None] = mapped_column(default=None)
    """Идентификатор файла фото в telegram"""

    condition_bool_field_id: Column[int | None] = Column(Integer, ForeignKey(Field.id), nullable=True)  # type: ignore
    """
    Идентификатор булева поля, используемого как условие для показа кнопки клавиатуры или отправки уведомления
    
    Не заполняется чтобы показать всем пользователям
    """
    condition_bool_field: "Field | None" = relationship(  # type: ignore
        "Field", lazy="selectin", foreign_keys=condition_bool_field_id, default=None
    )
    """Объект булева поля, используемого как условие для показа кнопки клавиатуры или отправки уведомления"""

    reply_condition_bool_field_id: Column[int | None] = Column(Integer, ForeignKey(Field.id), nullable=True)  # type: ignore
    """
    Идентификатор булева поля, используемого как условие для показа inline-клавиатуры

    Не заполняется для того чтобы показать клавиатуру всем пользователям
    """
    reply_condition_bool_field: "Field | None" = relationship(  # type: ignore
        "Field", lazy="selectin", foreign_keys=reply_condition_bool_field_id, default=None
    )
    """Объект булева поля, используемого как условие для показа inline-клавиатуры"""

    reply_type: Mapped[ReplyTypeEnum | None] = mapped_column(nullable=True, default=None)
    """
    Тип ответа:
    * начало ветки вопросов
    * полнотестовый ответ на один вопрос
    * быстрый ответ из списка
    """

    reply_answer_field_id: Column[int | None] = Column(Integer, ForeignKey(Field.id), nullable=True)  # type: ignore
    """Идентификатор поля, используемого для записи ответа"""
    reply_answer_field: "Field | None" = relationship(  # type: ignore
        "Field", lazy="selectin", foreign_keys=reply_answer_field_id, default=None
    )
    """Объект поля, используемого для записи ответа"""

    reply_answer_field_branch_id: Column[int | None] = Column(Integer, ForeignKey(FieldBranch.id), nullable=True)  # type: ignore
    """Идентификатор ветки полей, используемой для начала записи ответов"""
    reply_answer_field_branch: "FieldBranch | None" = relationship(  # type: ignore
        "FieldBranch", lazy="selectin", foreign_keys=reply_answer_field_branch_id, default=None
    )
    """Объект ветки полей, используемой для начала записи ответов"""

    reply_keyboard_keys: Mapped[str | None] = mapped_column(default=None)
    """
    Названия клавиш для записи ответов
    * В случае ответа на один вопрос или начала ветки должна быть одна клавиша
    * В случае быстрого ответа это варианты ответов
    """
    reply_status_replies: Mapped[str | None] = mapped_column(default=None)
    """
    Обозначения ответов:
    * В случае начала ветки вопросов - сообщение, отправляемое после ответа на последний вопрос из ветки
    * В случае ответа на один вопроса - сообщение, отправляемое после ответа на этот вопрос
    * В случае быстрого ответа - сообщение, отправляемое после указания на каждый из вариантов
    """


class User(Base):
    """Пользователь - не динамические данные о пользователе"""

    fields_values: list["UserFieldValue"] = relationship("UserFieldValue", backref="user", lazy="selectin")  # type: ignore
    """Заполненные поля пользователя"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    timestamp: Mapped[datetime] = mapped_column()
    """Дата создания"""
    chat_id: Mapped[int] = mapped_column(nullable=False, index=True, unique=True, type_=BigInteger)
    """Идентификатор чата Telegram"""
    username: Mapped[str | None] = mapped_column(default=None)
    """Имя пользователя Telegram"""

    status: Mapped[UserStatusEnum] = mapped_column(nullable=False, default=UserStatusEnum.INACTIVE)
    """Статус пользоваетля"""
    have_banned_bot: Mapped[bool] = mapped_column(nullable=False, default=False)
    """Указание на то, заблокировал ли пользователь бота"""

    curr_field_id: Column[int | None] = Column(Integer, ForeignKey(Field.id), nullable=True)  # type: ignore
    """Идентификатор текущего заполняемого пользователем поле"""
    curr_field: Field | None = relationship(Field, lazy="selectin", foreign_keys=curr_field_id, default=None)  # type: ignore
    """Текущее заполняемое пользователем поле"""

    change_field_message_id: Mapped[int | None] = mapped_column(nullable=True, default=None, type_=BigInteger)
    """Идентификатор поля изменяемого пользователем"""

    curr_reply_message_id: Column[int | None] = Column(Integer, ForeignKey(ReplyableConditionMessage.id), nullable=True)  # type: ignore
    """Идентификатор сообщения, на которое на данный момент отвечает пользователь"""
    curr_reply_message: ReplyableConditionMessage | None = relationship(  # type: ignore
        "ReplyableConditionMessage", lazy="selectin", foreign_keys=curr_reply_message_id, default=None
    )
    """Сообщение с условием, на которое на данный момент отвечает пользователь"""

    deferred_field_id: Column[int | None] = Column(Integer, ForeignKey(Field.id), nullable=True)  # type: ignore
    """Идентификатор отложенного пользователем поля"""
    deferred_field: Field | None = relationship(Field, lazy="selectin", foreign_keys=deferred_field_id, default=None)  # type: ignore
    """Отложенный вопрос"""
    deferred_reply_message_id: Column[int | None] = Column(
        Integer, ForeignKey(ReplyableConditionMessage.id), nullable=True
    )  # type: ignore
    """Идентификатор отложенного пользователем сообщения с условием"""

    pass_status: Mapped[PassSubmitStatusEnum] = mapped_column(default=PassSubmitStatusEnum.NOT_SUBMITED)
    """Статус обработки пропуска"""
    pass_field_change: Mapped[bool] = mapped_column(default=False)
    """Флаг изменения поля для пропуска"""

    curr_keyboard_key_parent_id: Mapped[int | None] = mapped_column(ForeignKey("keyboard_keys.id"), default=None)
    """Идентификатор родительской кнопки последней клавиши, на которую нажал пользователь"""

    def to_plain_dict(
        self,
        branch_id: int | None = None,
        i18n: I18n | None = None,
        result_dict_type: Literal["full", "ordered_pass_report"] = "full",
    ) -> dict[str, str | int | None]:
        """
        Преобразовать в плоский словарь для табличной выгрузки
        * branch_id: int = None - указывает ветку пользователей по которой нужно выполнить преобразование
        * i18n: I18n = None - Данные для перевода булевых значений
        * result_dict_type: Literal["full", "ordered_pass_report"] - Тип возвращаемых данных
          full - Выгрузка всех полей пользователя (статичных и дополнительных)
          ordered_pass_report - Только отсортированные данные для отчёта пропусков
        """
        user_dict: dict[str, str | int | None] = {}
        if result_dict_type == "full":
            user_dict |= {"id": self.id, "chat_id": self.chat_id, "username": self.username}

        fields_dict: dict[str, UserFieldDataPlain] = {}
        for field_value in self.fields_values:
            field_value: UserFieldValue
            field: Field = field_value.field

            check_if_field_in_branch: bool = not branch_id or branch_id == field.branch_id
            check_if_field_in_result: bool = result_dict_type == "full" or (
                field.report_order is not None and field.report_order >= 1
            )
            if check_if_field_in_branch and check_if_field_in_result:
                value = field_value.value
                if field.type == FieldTypeEnum.BOOLEAN and i18n:
                    if value == "true":
                        value = i18n.yes
                    elif value == "false":
                        value = i18n.no

                if result_dict_type == "full":
                    field_order_key = f"{field.branch_id:04d}_{field.order_place:04d}"
                elif result_dict_type == "ordered_pass_report":
                    field_order_key = f"{field.report_order:04d}"

                fields_dict |= {field_order_key: UserFieldDataPlain(key=field.key, value=value)}
        user_dict |= {fv.key: fv.value for _, fv in sorted(fields_dict.items(), key=lambda item: item[0])}
        if result_dict_type == "ordered_pass_report":
            user_dict |= {"id": self.id}
        return user_dict

    def prepare(self) -> UserDataPrepared:
        """Подготовка упрощённых данных пользователя"""
        return UserDataPrepared(
            id=self.id,
            chat_id=self.chat_id,
            username=self.username,
            fields=self.prepare_fields(),
        )

    def prepare_fields(self) -> dict[int, UserFieldDataPrepared]:
        """Подготовить поля пользователя"""
        fields = {}
        for field_value in self.fields_values:
            field: Field = field_value.field
            fields |= {
                field_value.field_id: UserFieldDataPrepared(
                    value=field_value.value,
                    empty=field_value.value == "",
                    type=field.type,
                    bucket=field.bucket,
                    value_file_id=field_value.value_file_id,
                    personal_notification_status=field_value.personal_notification_status,
                    answer_options=field.answer_options.split("\n") if field.answer_options else None,
                )
            }
        return fields


class UserFieldValue(Base):
    """Значение поля пользователя"""

    __tablename__ = "user_field_values"

    field: Field = relationship("Field", lazy="selectin")  # type: ignore
    """Поле"""

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальных идентификатор"""

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    """Идентификатор пользователя"""
    field_id = Column(Integer, ForeignKey(Field.id), nullable=False)
    """Идентификатор поля"""

    value: Mapped[str] = mapped_column()
    """Значение"""
    value_file_id: Mapped[str | None] = mapped_column()
    """
    Идентификатор файла значения

    Используется в случае если поле сохраняет изображение или документ для быстрого отображения
    """

    message_id: Mapped[int] = mapped_column(nullable=True, default=None, type_=BigInteger)
    """Идентификатор сообщения"""

    personal_notification_status: Mapped[PersonalNotificationStatusEnum] = mapped_column(nullable=True, default=None)


class KeyboardKey(Base):
    """Кнопки клавиатуры"""

    __tablename__ = "keyboard_keys"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    key: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    """Уникальный ключ"""
    status: Mapped[KeyboardKeyStatusEnum] = mapped_column(nullable=False, default=KeyboardKeyStatusEnum.INACTIVE)
    """Статус кнопки"""

    reply_condition_message_id = Column(Integer, ForeignKey(ReplyableConditionMessage.id), nullable=True)
    """Идентификатор сообщения с настройками условий и ответов"""
    reply_condition_message: "ReplyableConditionMessage | None" = relationship(  # type: ignore
        "ReplyableConditionMessage", lazy="selectin", default=None
    )
    """Сообщение с настройками условий и ответов"""

    branch_id: Column[int | None] = Column(Integer, ForeignKey(FieldBranch.id), nullable=True)  # type: ignore
    """Идентификатор Ветки, на основе которой отображаются данные для модификации или возврата при статусе KeyboardKeyStatusEnum.ME"""

    parent_key_id: Mapped[int | None] = mapped_column(ForeignKey("keyboard_keys.id"), default=None)
    """Идентификатор кнопки, которая является родительской для данной кнопки"""

    news_tag: Mapped[str | None] = mapped_column(default=None)
    """Тег новости, по которому будет выполнен поиск новостей"""


class Notification(Base):
    """Уведомления для пользователей"""

    __tablename__ = "notifications"

    reply_condition_message: "ReplyableConditionMessage" = relationship("ReplyableConditionMessage", lazy="selectin")  # type: ignore
    """Сообщение с настройками условий и ответов"""

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    schedule_datetime: Mapped[datetime] = mapped_column()
    """Дата и время уведомления"""
    status: Mapped[NotificationStatusEnum] = mapped_column(nullable=False, default=NotificationStatusEnum.INACTIVE)
    """Статус уведомления"""

    reply_condition_message_id = Column(Integer, ForeignKey(ReplyableConditionMessage.id), nullable=False)
    """Идентификатор сообщения с настройками условий и ответов"""


class Log(Base):
    """Лог"""

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальынй идентификатор"""
    timestamp: Mapped[datetime] = mapped_column()
    """Время создания лога"""
    message: Mapped[str] = mapped_column()
    """Сообщение лога"""


class Settings(Base):
    """Настройки бота"""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""

    bot_my_name_plain: Mapped[str] = mapped_column()
    """Название бота"""
    bot_my_short_description_plain: Mapped[str] = mapped_column()
    """Краткое описание бота, показываемое при передаче ссылки на бота"""
    bot_my_description_plain: Mapped[str] = mapped_column()
    """Описание бота, показываемое пользователю при начале взаимодействия с ботом"""
    bot_help_command_description_plain: Mapped[str] = mapped_column()
    """Описание команды помощи"""

    user_service_mode_message_plain: Mapped[str] = mapped_column()
    """Сообщение, отправляемые для всех пользователей если бот находится в сервисном режме"""
    user_registration_is_over_message_plain: Mapped[str] = mapped_column()
    """Текст сообщения для пользователя в случае если регистрация уже заверешена"""

    user_start_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон Jinja2 первого сообщения пользователю"""
    user_first_field_branch_plain: Mapped[str] = mapped_column()
    """
    Ветка полей, с которой начинается взаимодействие с ботом

    В качестве первого поля берётся основное поле заданной ветки с наименьшим значением номера по порядку
    """
    user_name_field_plain: Mapped[str] = mapped_column()
    """
    Основное поле пользователя, используемое как его имя

    Это поле отображается в UI как имя пользователя

    Также это поле является основой имени файла в хранилище
    """

    user_registration_complete_message_plain: Mapped[str] = mapped_column()
    """Текст сообщения, который будет показан пользователю когда он окончит регистрацию"""

    user_restart_message_j2_template: Mapped[str] = mapped_column()
    """
    Текст сообщения для пользователя в случае если он разбанил бота

    Это аналогично тому, что он попытался ввести команду /start снова, но он уже зарегистрирован
    """
    user_help_message_j2_template: Mapped[str] = mapped_column()
    """
    Помощь обычному пользователю

    Других команд нет, все остальное см. на листе Клавиатура
    """
    user_registered_help_or_restart_message_plain: Mapped[str] = mapped_column()
    """Текст для пользователя в случае если он уже зарегистрирован и запрашивает помощь"""

    user_change_reply_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон подтверждения пользователю об изменении поля"""

    user_fast_answer_reply_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон подтверждения пользователю об изменении поля"""

    user_skip_button_plain: Mapped[str] = mapped_column()
    """Текст кнопки пропуска вопроса"""

    user_defer_button_plain: Mapped[str] = mapped_column()
    """Текст кнопки для откладывания текущего вопроса"""
    user_defered_message_plain: Mapped[str] = mapped_column()
    """Текст сообщения, отправляемого после того как пользователь нажал на кнопку откладывания вопроса"""

    user_or_group_cancel_button_plain: Mapped[str] = mapped_column()
    """Текст кнопки отмены действия"""
    user_field_change_canceled_message_plain: Mapped[str] = mapped_column()
    """Сообщение высылаемое после того как пользоваель отменил именение поля"""

    user_strange_error_massage_plain: Mapped[str] = mapped_column()
    """Текст ошибки, передаваемый пользователю в случае если он имеет доступ к боту, но не зарегистрирован"""
    user_message_edited_reply_message_plain: Mapped[str] = mapped_column()
    """Ответ пользователю, который изменил одно из сообщений."""
    user_error_message_plain: Mapped[str] = mapped_column()
    """Ответ пользователю об ошибке"""
    user_file_upload_without_field_context: Mapped[str] = mapped_column()
    """Ответ пользователю на загрузку файла без контекста поля"""

    user_file_too_large_message_j2_template: Mapped[str] = mapped_column()
    """Ответ пользователю о том что отправленный файл слишком большой"""
    user_max_image_file_size_kb_int: Mapped[str] = mapped_column()
    """Максимальный размер изображения в KB"""
    user_max_document_file_size_kb_int: Mapped[str] = mapped_column()
    """Максимальный размер документа в KB"""

    user_unavaliable_image_type_message_j2_template: Mapped[str] = mapped_column()
    """Ответ пользователю о том что отправленное изображение имеет неподдерживаемый тип"""
    user_avaliable_image_types_array: Mapped[str] = mapped_column()
    """Доступные типы файлов изображений"""

    group_normal_help_message_plain: Mapped[str] = mapped_column()
    """Текст помощи для обычной группы пользователей"""
    group_admin_help_message_plain: Mapped[str] = mapped_column()
    """Текст помощи для группы администраторов"""
    group_superadmin_help_message_plain: Mapped[str] = mapped_column()
    """Текст помощи для группы супер администраторов"""

    group_admin_notification_sent_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон оповещения групп администраторов о разосланном уведомлении"""
    group_admin_notification_planned_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон оповещения групп администраторов о заполанированном уведомлении"""

    group_admin_report_every_x_active_users_int: Mapped[str] = mapped_column()
    """Количество активных пользователей, по которым будет выслано оповещение в группу администраторов"""
    group_admin_report_currently_active_users_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, которое будет выслано в группу администраторов при достижении необходимого числа пользователей"""

    group_admin_status_report_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения отчёта для админиатраторов"""

    user_pass_field_plain: Mapped[str] = mapped_column()
    """
    Название пользовательского поля, содержащего пропуск
    
    При инициализации создаётся ветка полей с таким же именованием
    """

    user_pass_registration_button_plain: Mapped[str] = mapped_column()
    """Кнопка начала регистрации пропуска """
    user_pass_submit_button_plain: Mapped[str] = mapped_column()
    """Кнопка подачи заявки на пропуск"""
    user_pass_confirm_button_plain: Mapped[str] = mapped_column()
    """Кнопка подтверждения заявки на пропуск"""
    user_pass_submit_canceled_message_plain: Mapped[str] = mapped_column()
    """Сообщение, отправляемое пользователю после отмены отправки заявки на пропуск"""

    user_pass_required_field_plain: Mapped[str] = mapped_column()
    """Необязательно по умолчанию поле, необходимое для получения пропуска"""
    user_pass_availability_field_plain: Mapped[str] = mapped_column()
    """Булево поле, разрешающее пользователю получить пропуск"""

    user_pass_message_j2_template: Mapped[str] = mapped_column()
    """Сообщение, посылаемое вместе с пропуском пользователя"""
    user_pass_removed_message_plain: Mapped[str] = mapped_column()
    """Сообщение, высылаемое в случае если запланирована доставка сообщения с пропуском, но пропуска нет"""
    user_pass_hint_message_plain: Mapped[str] = mapped_column()
    """Сообщение помощи пользователю о регистрации пропуска"""
    user_pass_unavailable_message_plain: Mapped[str] = mapped_column()
    """Сообщение пользователю о недоступности регистрации пропуска"""
    user_pass_add_request_field_value_message_plain: Mapped[str] = mapped_column()
    """Сообщение, отправляемое в случае если невозможно отправить запрос на формирование пропуска поскольку не заполнено поле, необходимое для получения пропуска"""
    user_pass_not_yet_approved_message_plain: Mapped[str] = mapped_column()
    """Сообщение, посылаемое если пользователю ещё не выдан пропуск"""
    user_pass_submit_message_plain: Mapped[str] = mapped_column()
    """Сообщение высылаемое пользователю при начале отправки заявки на пропуск"""
    user_pass_submitted_message_plain: Mapped[str] = mapped_column()
    """Сообщение высылаемое пользователю после подтверждения отправки заявки на пропуск"""
    group_superadmin_pass_submited_superadmin_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, отправляемого суперадминистраторам при отправке пользователем заявки на пропуск"""

    group_superadmin_pass_download_submited_button_plain: Mapped[str] = mapped_column()
    """Кнопка суперадминов для получения списка пользователей, подавших заявку на пропуск"""
    group_superadmin_pass_send_approved_button_plain: Mapped[str] = mapped_column()
    """Кнопка суперадминов для загрузки списка пользователей, получивших пользователей"""
    group_superadmin_pass_submitted_empty_message_plain: Mapped[str] = mapped_column()
    """Сообщение, показываемое если нет пользоваелей, подавших заявку на пропуск"""
    group_superadmin_pass_send_approved_zip_photos_message_plain: Mapped[str] = mapped_column()
    """Сообщение, отправляемое суперадминистраторам для отправки изображений пропусков пользоваелей"""
    group_superadmin_pass_available_approved_zip_photos_done_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, содержащего распакованные изображения пропусков пользователей"""
    group_superadmin_pass_send_approved_xlsx_message_plain: Mapped[str] = mapped_column()
    """Сообщение, высылаемое суперадминам для выгрузки таблицы разрешённых пропусков пользователей"""
    group_superadmin_pass_approved_canceled_message_plain: Mapped[str] = mapped_column()
    """Сообщение, высылаемое суперадминам, в случае отмены высылки таблицы разрешённых пропусков пользователей"""
    group_superadmin_pass_approved_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, высылаемого суперадминам, со списком пользователей, получивших пропуска"""
    group_superadmin_pass_not_approved_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, высылаемого суперадминам, со списком пользователей, не получивших пропуска"""

    user_personal_notification_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, высылаемого как персональное уведомление для пользователя"""

    group_superadmin_expired_promocodes_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения о просроченных промокодах"""
    user_avaliable_promocodes_message_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения о доступных промокодах"""

    user_number_of_last_news_to_show_int: Mapped[str] = mapped_column()
    """Количество последних показываемых новостей"""


class NewsPost(Base):
    """Класс новостных сообщений"""

    __tablename__ = "news_posts"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    chat_id: Mapped[int] = mapped_column(nullable=False, index=False, unique=False, type_=BigInteger)
    """Идентификатор канала новостей в TG"""
    message_id: Mapped[int] = mapped_column(nullable=False, index=False, unique=True, type_=BigInteger)
    """Идентификатор сообщения новостей"""
    tags: Mapped[str | None] = mapped_column(default=None)
    """Теги сообщения"""


class Promocode(Base):
    """Доступные промокоды"""

    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    status: Mapped[PromocodeStatusEnum] = mapped_column()
    """Статус промокода"""
    source: Mapped[str] = mapped_column()
    """Источник промокода - организация"""
    value: Mapped[str] = mapped_column()
    """Значение промокода"""
    description: Mapped[str | None] = mapped_column()
    """Описание промокода"""
    expire_at: Mapped[datetime | None] = mapped_column()
    """Время окончания действия промокода"""
