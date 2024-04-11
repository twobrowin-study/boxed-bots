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
    KeyboardKeyStatusEnum,
)

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

    is_ui_edditable:  Mapped[bool] = mapped_column(default=True, nullable=False)
    is_bot_edditable: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_deferrable:    Mapped[bool] = mapped_column(default=True, nullable=False)

    next_branch_id = Column(Integer, ForeignKey('field_branches.id'), nullable=True)

class Field(Base):
    """
    Поле данных пользователя
    """

    __tablename__ = "fields"

    id:     Mapped[int]             = mapped_column(primary_key=True, nullable=False)
    key:    Mapped[str]             = mapped_column(nullable=False,   index=True, unique=True)
    status: Mapped[FieldStatusEnum] = mapped_column(nullable=False,   default=FieldStatusEnum.INACTIVE)

    order_place: Mapped[int] = mapped_column(nullable=False, default=0)
    
    branch_id = Column(Integer, ForeignKey(FieldBranch.id), nullable=False)
    branch    = relationship('FieldBranch', lazy='selectin')

    question_markdown: Mapped[str|None] = mapped_column(default=None)
    answer_options:    Mapped[str|None] = mapped_column(default=None)
    image_bucket:      Mapped[str|None] = mapped_column(default=None)
    document_bucket:   Mapped[str|None] = mapped_column(default=None)

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
    
    curr_field_id = Column(Integer, ForeignKey(Field.id), nullable=True)
    curr_field    = relationship('Field', lazy='selectin')

    fields_values = relationship('UserFieldValue', backref='user', lazy='selectin')

    def to_dict(self) -> dict[str, str|dict]:
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'username': self.username,
            'fields': {
                field_value.field_id: {
                    'value':           field_value.value,
                    'document_bucket': field_value.field.document_bucket,
                    'image_bucket':    field_value.field.image_bucket
                }
                for field_value in self.fields_values
            }
        }

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

class KeyboardKey(Base):
    """
    Кнопки клавиатуры - основное взаимодействие с ботом
    """

    __tablename__ = "keyboard_keys"

    id:      Mapped[int]                   = mapped_column(primary_key=True, nullable=False)
    key:     Mapped[str]                   = mapped_column(nullable=False,   index=True)
    status:  Mapped[KeyboardKeyStatusEnum] = mapped_column(nullable=False,   default=KeyboardKeyStatusEnum.INACTIVE)

    text_markdown: Mapped[str]      = mapped_column(nullable=False, default=None)
    photo_link:    Mapped[str|None] = mapped_column(nullable=True,  default=None)

    branch_id = Column(Integer, ForeignKey(FieldBranch.id), nullable=True)
    """
    Id Ветки, на основе которой отображаются данные для модификации или возврата
    
    Используется при статусе KeyboardKeyStatusEnum.ME или KeyboardKeyStatusEnum.DEFERRED
    """

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
    