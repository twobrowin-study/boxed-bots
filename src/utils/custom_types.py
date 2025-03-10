from enum import Enum
from typing import NamedTuple


class BotStatusEnum(Enum):
    """Статус работы бота"""

    ON = "on"
    """
    Бот запущен:
      - Устанавливается администратором в случае если бот должен работать в обычном режиме
      - Устанавливается самим ботом после перезагрузки
    """

    OFF = "off"
    """Бот выключен - отключатся процесс бота, устанавливается администратором"""

    SERVICE = "service"
    """Сервисный режим - бот отправляет уведомление о том, что он находится в сервисном режиме при любом взаимодействии"""

    RESTART = "restart"
    """Команда на перезапуск, устанавливается администратором"""
    RESTARTING = "restarting"
    """Состояние перезапуска, устанавливается ботом при выключением перед перезагрузкой"""


class GroupStatusEnum(Enum):
    """Статус группы для управления доступом"""

    NORMAL = "normal"
    """Обычная группа"""

    ADMIN = "admin"
    """
    Группа администраторов:
      - приходят оповещения об отправке уведомлений
      - приходят оповещения о количестве зарегестрированных пользователей
    """

    SUPER_ADMIN = "super_admin"
    """
    Группа суперадминистраторов, помимо функций обычных администраторов:
      - приходят уведомления о запланированных уведомлениях
      - приходят уведомления об ошибках в боте
    """

    NEWS_CHANNEL = "news_channel"
    """Новостной канал из которого будут пересланы сообщения"""

    INACTIVE = "inactive"
    """Неактивная группа"""


class UserStatusEnum(Enum):
    """Статус пользователей"""

    ACTIVE = "active"
    """Обычный пользователь"""
    INACTIVE = "inactive"
    """Неактивный пользователь"""


class FieldBranchStatusEnum(Enum):
    """Статус поля пользователя"""

    NORMAL = "normal"
    """Нормальная ветка"""
    INACTIVE = "inactive"
    """Неактивная ветка"""


class FieldStatusEnum(Enum):
    """Статус поля пользователя"""

    NORMAL = "normal"
    """Нормальный вопрос"""
    INACTIVE = "inactive"
    """Неактвное поле"""

    PERSONAL_NOTIFICATION = "personal_notifiation"
    """Индивидуальное уведомление пльзователя"""

    JINJA2_FROM_USER_ON_CREATE = "jinja2_from_user_on_create"
    """Вычисляемое поле при помощи Jinja2 на основе объекта-пользователя при его создании"""

    JINJA2_FROM_USER_AFTER_REGISTRATION = "jinja2_from_user_after_registration"
    """Вычисляемое поле при помощи Jinja2 на основе объекта-пользователя (с доступом ко всем полям) после окончания регистрации"""


class FieldTypeEnum(Enum):
    """Тип поля пользователя"""

    FULL_TEXT = "full_text"
    """Полнотекстовое поле"""

    BOOLEAN = "boolean"
    """Булево поле"""

    IMAGE = "image"
    """Изображение"""

    ZIP_DOCUMENT = "zip_document"
    """ZIP архив"""

    PDF_DOCUMENT = "pdf_document"
    """PDF документ"""


class PersonalNotificationStatusEnum(Enum):
    """Статусы отправки индивидуальных уведомлений пользователям"""

    INACTIVE = "inactive"
    """Неактивное уведомление"""
    TO_DELIVER = "to_deliver"
    """Запланирована отправка"""
    DELIVERED = "delivered"
    """Отправлено"""


class ReplyTypeEnum(Enum):
    """Тип ответа на сообщения"""

    BRANCH_START = "branch_start"
    """Ответ на ветку вопросов"""
    FULL_TEXT_ANSWER = "full_text_answer"
    """Полнотекстовый ответ на один вопрос"""
    FAST_ANSWER = "fast_answer"
    """Короткий ответ на вопрос (выбор кнопками)"""


class KeyboardKeyStatusEnum(Enum):
    """Статус кнопки на клавиатуре"""

    NORMAL = "normal"
    """Обычная клавиша"""

    BACK = "back"
    """Вернуться на меню выше"""

    DEFERRED = "deferred"
    """
    Вернуться к отложенному вопросу

    Отображается только когда у пользователя заполненно поле отложенного вопроса
    """

    ME = "me"
    """Отображение параметров регистрации"""
    ME_CHANGE = "me_change"
    """Изменение параметров регистрации"""

    PASS = "pass"
    """Показать пропуск пользователя"""

    NEWS = "news"
    """Отобразить новости сообщества"""

    PROMOCODES = "promocodes"
    """Отобразить доступные промокоды"""

    INACTIVE = "inactive"
    """Неактивная клавиша - не отображается"""


class NotificationStatusEnum(Enum):
    """Статус отправки уведомлений"""

    INACTIVE = "inactive"
    """Уведомление не активно"""
    TO_DELIVER = "to_deliver"
    """Уведомление помечено к отправке"""
    PLANNED = "planned"
    """Уведомление запланировано к отправке"""
    DELIVERED = "delivered"
    """Уведомление отправлено"""


class PromocodeStatusEnum(Enum):
    """Статус промокодов"""

    ACTIVE = "active"
    """Промокод активен"""
    INACTIVE = "inactive"
    """Промокод не активен"""
    EXPIRED = "expired"
    """Промокод просрочен"""


class PassSubmitStatusEnum(Enum):
    """Статус выдачи пропусков"""

    NOT_SUBMITED = "not_submited"
    """Пропуск не запрошен"""
    SUBMITED = "submited"
    """Пропуск запрошен"""
    APPROVED = "approved"
    """Пропуск одобрен"""


class UserFieldDataPlain(NamedTuple):
    """Значение поля пользователя"""

    key: str
    """Название поля"""
    value: str
    """Значение поля"""


class UserFieldDataPrepared(NamedTuple):
    """Упрощённые данные поля пользователя"""

    value: str
    """Значение поля"""
    type: FieldTypeEnum
    """Тип поля"""
    bucket: str | None
    """Бакет документов"""
    value_file_id: str | None = None
    """Идентификатор файла пользователя"""
    empty: bool = False
    """Признак того, что поле пусто"""
    personal_notification_status: PersonalNotificationStatusEnum | None = None
    """Статус уведомления"""
    answer_options: list[str] | None = None
    """Варианты ответа"""


class UserDataPrepared(NamedTuple):
    """Упрощённые данные пользователя"""

    id: int
    chat_id: int
    username: str | None
    fields: dict[int, UserFieldDataPrepared]
