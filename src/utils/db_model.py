from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    BigInteger
)
from sqlalchemy.orm import (
    MappedAsDataclass, 
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)
from utils.custom_types import (
    BotStatusEnum,
    BotStatusEnum,
    GroupStatusEnum,
    UserStatusEnum,
    FieldBranchStatusEnum,
    FieldStatusEnum,
    ReplyTypeEnum,
    KeyboardKeyStatusEnum,
    NotificationStatusEnum,
    UserFieldDataPlain,
    UserFieldDataPrepared,
    UserDataPrepared,
    PersonalNotificationStatusEnum,
    PromocodeStatusEnum,
    QrCodeSubmitStatus
)
from utils.config_model import I18n

from datetime import datetime

class Base(MappedAsDataclass, DeclarativeBase):
    pass

class BotStatus(Base):
    """
    Выключение и текущее состояние бота
    """

    __tablename__ = "bot_status"

    id:                   Mapped[int]           = mapped_column(primary_key=True,         nullable=False)
    bot_status:           Mapped[BotStatusEnum] = mapped_column(default=BotStatusEnum.ON, nullable=False)
    is_registration_open: Mapped[bool]          = mapped_column(default=True,             nullable=False)

class Group(Base):
    """
    Группа, в которую бот будет высылать уведомления
    """

    __tablename__ = "groups"

    id:          Mapped[int]             = mapped_column(primary_key=True, nullable=False)
    chat_id:     Mapped[int]             = mapped_column(nullable=False,   index=True, unique=True, type_=BigInteger)
    status:      Mapped[GroupStatusEnum] = mapped_column(nullable=False,   default=GroupStatusEnum.INACTIVE)
    description: Mapped[str|None]        = mapped_column(default=None)

class FieldBranch(Base):
    """
    Ветки вопросов пользователей
    """

    __tablename__ = "field_branches"

    id:  Mapped[int] = mapped_column(primary_key=True, nullable=False)
    key: Mapped[str] = mapped_column(nullable=False,   index=True, unique=True)
    status: Mapped[FieldBranchStatusEnum] = mapped_column(nullable=False,   default=FieldBranchStatusEnum.INACTIVE)

    is_ui_editable:  Mapped[bool] = mapped_column(default=True, nullable=False)
    is_bot_editable: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_deferrable:   Mapped[bool] = mapped_column(default=True, nullable=False)

    next_branch_id: Column[int|None] = Column(Integer, ForeignKey('field_branches.id'), nullable=True)

class Field(Base):
    """
    Поле данных пользователя
    """

    __tablename__ = "fields"

    id:     Mapped[int]             = mapped_column(primary_key=True, nullable=False)
    key:    Mapped[str]             = mapped_column(nullable=False,   index=True, unique=True)
    status: Mapped[FieldStatusEnum] = mapped_column(nullable=False,   default=FieldStatusEnum.INACTIVE)

    order_place: Mapped[int] = mapped_column(nullable=False, default=0)
    
    branch_id: Column[int] = Column(Integer, ForeignKey(FieldBranch.id), nullable=False)
    branch = relationship('FieldBranch', lazy='selectin')

    question_markdown: Mapped[str|None] = mapped_column(default=None)
    answer_options:    Mapped[str|None] = mapped_column(default=None)
    image_bucket:      Mapped[str|None] = mapped_column(default=None)
    document_bucket:   Mapped[str|None] = mapped_column(default=None)
    is_boolean:        Mapped[bool]     = mapped_column(default=False)

    validation_regexp: Mapped[str|None] = mapped_column(default=None)
    validation_error_markdown: Mapped[str|None] = mapped_column(default=None)
    validation_remove_regexp: Mapped[str|None] = mapped_column(default=None)

    is_skippable: Mapped[bool] = mapped_column(default=False)

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
    
    id:     Mapped[int] = mapped_column(primary_key=True, nullable=False)
    name:   Mapped[str] = mapped_column(nullable=False,   unique=True, index=True)

    text_markdown: Mapped[str]      = mapped_column(nullable=False)
    photo_link:    Mapped[str|None] = mapped_column(nullable=True, default=None)

    condition_bool_field_id: Column[int|None] = Column(Integer, ForeignKey(Field.id), nullable=True)
    """
    Id булева поля, используемого как условие для показа кнопки клавиатуры или отправки уведомления
    
    Не заполняется чтобы показать всем пользователям
    """
    condition_bool_field = relationship('Field', lazy='selectin', foreign_keys=condition_bool_field_id)

    reply_condition_bool_field_id: Column[int|None] = Column(Integer, ForeignKey(Field.id), nullable=True)
    """
    Id булева поля, используемого как условие для показа inline-клавиатуры

    Не заполняется для того чтобы показать клавиатуру всем пользователям
    """
    reply_condition_bool_field = relationship('Field', lazy='selectin', foreign_keys=reply_condition_bool_field_id)

    reply_type: Mapped[ReplyTypeEnum|None] = mapped_column(nullable=True, default=None)
    """
    Тип ответа:
    * начало ветки вопросов
    * полнотестовый ответ на один вопрос
    * быстрый ответ из списка
    """

    reply_answer_field_id: Column[int|None] = Column(Integer, ForeignKey(Field.id), nullable=True)
    """Id поля, используемого для записи ответа"""
    reply_answer_field_branch_id: Column[int|None] = Column(Integer, ForeignKey(FieldBranch.id), nullable=True)
    """Id ветки полей, используемой для начала записи ответов"""

    reply_keyboard_keys: Mapped[str|None] = mapped_column(default=None)
    """
    Названия клавиш для записи ответов
    * В случае ответа на один вопрос или начала ветки должна быть одна клавиша
    * В случае быстрого ответа это варианты ответов
    """
    reply_status_replies: Mapped[str|None] = mapped_column(default=None)
    """
    Обозначения ответов:
    * В случае начала ветки вопросов - сообщение, отправляемое после ответа на последний вопрос из ветки
    * В случае ответа на один вопроса - сообщение, отправляемое после ответа на этот вопрос
    * В случае быстрого ответа - сообщение, отправляемое после указания на каждый из вариантов
    """

class User(Base):
    """
    Пользователь - не динамические данные о пользователе
    """

    __tablename__ = "users"

    id:        Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    chat_id:   Mapped[int]      = mapped_column(nullable=False, index=True, unique=True, type_=BigInteger)
    username:  Mapped[str|None] = mapped_column(default=None)
    
    status:          Mapped[UserStatusEnum] = mapped_column(nullable=False, default=UserStatusEnum.INACTIVE)
    have_banned_bot: Mapped[bool]           = mapped_column(nullable=False, default=False)
    
    curr_field_id: Column[int|None] = Column(Integer, ForeignKey(Field.id), nullable=True)
    curr_field    = relationship('Field', lazy='selectin', foreign_keys=curr_field_id)

    fields_values = relationship('UserFieldValue', backref='user', lazy='selectin')

    change_field_message_id: Mapped[int|None] = mapped_column(nullable=True, default=None, type_=BigInteger)
    deferred_field_id: Column[int|None] = Column(Integer, ForeignKey(Field.id), nullable=True)
    """Id отложенного пользователем поля"""
    deferred_field = relationship('Field', lazy='selectin', foreign_keys=deferred_field_id)
    """Отложенный вопрос"""

    curr_reply_message_id: Column[int|None] = Column(Integer, ForeignKey(ReplyableConditionMessage.id), nullable=True)
    """Id сообщения, на которое на данный момент отвечает пользователь"""
    curr_reply_message = relationship('ReplyableConditionMessage', lazy='selectin')
    """Сообщения, на которое на данный момент отвечает пользователь"""

    curr_keyboard_key_parent_id: Mapped[int|None] = mapped_column(ForeignKey("keyboard_keys.id"), default=None)
    """Id родительской кнопки последней клавиши, на которую нажал пользователь"""

    qr_code_status: Mapped[QrCodeSubmitStatus] = mapped_column(default=QrCodeSubmitStatus.NOT_SUBMITED)
    """Статус обработки QR кода"""

    def to_plain_dict(self, branch_id: int|None = None, i18n: I18n|None = None) -> dict[str, str]:
        """
        Преобразовать в плоский словарь для табличной выгрузки
        * branch_id: int = None - указывает ветку пользователей по которой нужно выполнить преобразование
        * i18n: I18n = None - Данные для перевода булевых значений
        """
        user_dict: dict[str, str] = {
            'id':       self.id,
            'chat_id':  self.chat_id,
            'username': self.username
        }
        fields_dict: dict[str, UserFieldDataPlain] = {}
        for field_value in self.fields_values:
            field_value: UserFieldValue
            field: Field = field_value.field
            if not branch_id or field.branch_id == branch_id:
                value = field_value.value
                if field.is_boolean and i18n:
                    if value == 'true':
                        value = i18n.yes
                    elif value == 'false':
                        value = i18n.no
                fields_dict |= {
                    f"{field.branch_id}_{field.order_place}": UserFieldDataPlain(
                        key   = field.key,
                        value = value
                    )
                }
        user_dict |= {
            fv.key: fv.value for _,fv in sorted(fields_dict.items(), key=lambda item: item[0])
        }
        return user_dict

    def prepare(self) -> UserDataPrepared:
        return UserDataPrepared(
            id       = self.id,
            chat_id  = self.chat_id,
            username = self.username,
            fields   = self.prepare_fields()
        )

    def prepare_fields(self) -> dict[int, UserFieldDataPrepared]:
        fields = {}
        for field_value in self.fields_values:
            field_value: UserFieldValue
            field: Field = field_value.field
            fields |= {
                field_value.field_id: UserFieldDataPrepared(
                    value = field_value.value,
                    document_bucket = field.document_bucket,
                    image_bucket    = field.image_bucket,
                    personal_notification_status = field_value.personal_notification_status
                )
            }
        return fields

class UserFieldValue(Base):
    """
    Значение поля пользователя
    """

    __tablename__ = "user_field_values"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    
    user_id  = Column(Integer, ForeignKey(User.id), nullable=False)
    field_id = Column(Integer, ForeignKey(Field.id), nullable=False)

    value: Mapped[str] = mapped_column(nullable=False)
    
    message_id: Mapped[int] = mapped_column(nullable=True, default=None, type_=BigInteger)

    field = relationship('Field', lazy='selectin')

    personal_notification_status: Mapped[PersonalNotificationStatusEnum] = mapped_column(nullable=True, default=None)

class KeyboardKey(Base):
    """
    Кнопки клавиатуры - основное взаимодействие с ботом
    """

    __tablename__ = "keyboard_keys"

    id:      Mapped[int]                   = mapped_column(primary_key=True, nullable=False)
    key:     Mapped[str]                   = mapped_column(nullable=False,   unique=True, index=True)
    status:  Mapped[KeyboardKeyStatusEnum] = mapped_column(nullable=False,   default=KeyboardKeyStatusEnum.INACTIVE)

    reply_condition_message_id = Column(Integer, ForeignKey(ReplyableConditionMessage.id), nullable=True)
    """Id сообщения с настройками условий и ответов"""
    reply_condition_message = relationship('ReplyableConditionMessage', lazy='selectin')
    """Сообщение с настройками условий и ответов"""

    branch_id = Column(Integer, ForeignKey(FieldBranch.id), nullable=True)
    """Id Ветки, на основе которой отображаются данные для модификации или возврата при статусе KeyboardKeyStatusEnum.ME"""

    parent_key_id: Mapped[int|None] = mapped_column(ForeignKey("keyboard_keys.id"), default=None)
    """Id клавиши, которая является родительской для данной кнопки"""

class Notification(Base):
    """
    Уведомления для пользователей
    """

    __tablename__ = "notifications"

    id:          Mapped[int]                    = mapped_column(primary_key=True, nullable=False)
    notify_date: Mapped[datetime]               = mapped_column(nullable=False)
    status:      Mapped[NotificationStatusEnum] = mapped_column(nullable=False,   default=NotificationStatusEnum.INACTIVE)

    reply_condition_message_id = Column(Integer, ForeignKey(ReplyableConditionMessage.id), nullable=False)
    """Id сообщения с настройками условий и ответов"""
    reply_condition_message = relationship('ReplyableConditionMessage', lazy='selectin')
    """Сообщение с настройками условий и ответов"""

class Log(Base):
    """
    Лог - дополнительный способ сохранить информацию из бота
    """

    __tablename__ = "logs"

    id:        Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    message:   Mapped[str]      = mapped_column(nullable=False)

class Settings(Base):
    """
    Настройки бота
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    
    my_name:                  Mapped[str] = mapped_column(nullable=False)
    my_short_description:     Mapped[str] = mapped_column(nullable=False)
    my_description:           Mapped[str] = mapped_column(nullable=False)
    help_command_description: Mapped[str] = mapped_column(nullable=False)
    
    service_mode_message: Mapped[str] = mapped_column(nullable=False)
    registration_is_over: Mapped[str] = mapped_column(nullable=False)
    
    start_template:           Mapped[str] = mapped_column(nullable=False)
    first_field_branch:       Mapped[str] = mapped_column(nullable=False)
    user_document_name_field: Mapped[str] = mapped_column(nullable=False)

    registration_complete: Mapped[str] = mapped_column(nullable=False)
    
    restart_user_template:                 Mapped[str] = mapped_column(nullable=False)
    help_user_template:                    Mapped[str] = mapped_column(nullable=False)
    help_restart_on_registration_complete: Mapped[str] = mapped_column(nullable=False)

    user_change_message_reply_template: Mapped[str] = mapped_column(nullable=False)
    
    strange_user_error:   Mapped[str] = mapped_column(nullable=False)
    edited_message_reply: Mapped[str] = mapped_column(nullable=False)
    error_reply:          Mapped[str] = mapped_column(nullable=False)
    
    help_normal_group:     Mapped[str] = mapped_column(nullable=False)
    help_admin_group:      Mapped[str] = mapped_column(nullable=False)
    help_superadmin_group: Mapped[str] = mapped_column(nullable=False)
    
    notification_admin_groups_template:                   Mapped[str] = mapped_column(nullable=False)
    notification_admin_groups_condition_template:         Mapped[str] = mapped_column(nullable=False)
    notification_planned_admin_groups_template:           Mapped[str] = mapped_column(nullable=False)
    notification_planned_admin_groups_condition_template: Mapped[str] = mapped_column(nullable=False)
    
    report_send_every_x_active_users:       Mapped[str] = mapped_column(nullable=False)
    report_currently_active_users_template: Mapped[str] = mapped_column(nullable=False)
    
    qr_code_user_field: Mapped[str] = mapped_column()
    """Название ветки и пользовательского поля, содержащего QR коды"""
    qr_code_message: Mapped[str] = mapped_column()
    """Сообщение, посылаемое вместе с QR кодом пользователя"""
    no_qr_code_message: Mapped[str] = mapped_column()
    """Сообщение, посылаемое если пользователю не выдан QR код"""
    qr_submit_message: Mapped[str] = mapped_column()
    """Сообщение высылаемое пользователю при начале отправки заявки на QR код"""
    qr_submitted_message: Mapped[str] = mapped_column()
    """Сообщение высылаемое пользователю после подтверждения отправки заявки на QR код"""
    qr_submited_superadmin_j2_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, отправляемого суперадминистраторам при отправке пользователем заявки на qr код"""

    personal_notification_jinja_template: Mapped[str] = mapped_column()
    """Шаблон сообщения, высылаемого как персональное уведомление для пользователя"""
    expired_promocodes_jinja_template: Mapped[str] = mapped_column()
    """Шаблон сообщения о просроченных промокодах"""
    avaliable_promocodes_jinja_template: Mapped[str] = mapped_column()
    """Шаблон сообщения о доступных промокодах"""

    number_of_last_news_to_show: Mapped[str] = mapped_column()
    """Количество последних показываемых новостей"""

class NewsPost(Base):
    """Класс новостных сообщений"""

    __tablename__ = "news_posts"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор"""
    chat_id: Mapped[int] = mapped_column(nullable=False, index=False, unique=False, type_=BigInteger)
    """Уникальный идентификатор канала новостей"""
    message_id: Mapped[int] = mapped_column(nullable=False, index=False, unique=True, type_=BigInteger)
    """Уникальный идентификатор сообщения новостей"""

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
    description: Mapped[str|None] = mapped_column()
    """Описание промокода"""
    expire_at: Mapped[datetime|None] = mapped_column()
    """Время окончания действия промокода"""