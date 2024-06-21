from enum import Enum
from typing import NamedTuple

class BotStatusEnum(Enum):
    """
    Статус работы бота
    """
    ON  = 'on'  # Бот запущен:
                #  - Устанавливается администратором в случае если бот должен работать в обычном режиме
                #  - Устанавливается самим ботом после перезагрузки
    OFF = 'off' # Бот выключен - отключатся процесс бота, устанавливается администратором

    SERVICE = 'service' # Сервисный режим - бот отправляет уведомление о том, что он находится в сервисном режиме при любом взаимодействии
    
    RESTART    = 'restart'    # Команда на перезапуск, устанавливается администратором
    RESTARTING = 'restarting' # Состояние перезапуска, устанавливается ботом при выключением перед перезагрузкой

class GroupStatusEnum(Enum):
    """
    Статус группы для управления доступом
    """
    NORMAL      = 'normal'      # Обычная группа
    ADMIN       = 'admin'       # Группа администраторов:
                                #  - приходят оповещения об отправке уведомлений
                                #  - приходят оповещения о количестве зарегестрированных пользователей
    SUPER_ADMIN = 'super_admin' # Группа суперадминистраторов, помимо функций обычных администраторов:
                                #  - приходят уведомления о запланированных уведомлениях
                                #  - приходят уведомления об ошибках в боте
    
    NEWS_CHANNEL = 'news_channel'
    """Новостной канал из которого будут пересланы сообщения"""

    INACTIVE    = 'inactive'    # Не актвная группа

class UserStatusEnum(Enum):
    """
    Статус пользователей
    """
    ACTIVE   = 'active'   # Обычный пользователь
    INACTIVE = 'inactive' # Не актвный пользователь

class FieldBranchStatusEnum(Enum):
    """
    Статус поля пользователя 
    """
    NORMAL     = 'normal'   # Нормальная ветка
    INACTIVE   = 'inactive' # Не активная ветка

class FieldStatusEnum(Enum):
    """
    Статус поля пользователя 
    """
    NORMAL     = 'normal'   # Нормальный вопрос
    INACTIVE   = 'inactive' # Не актвное поле

    PERSONAL_NOTIFICATION = 'personal_notifiation'
    """Индивилуальное уведомление пльзователя"""

    JINJA2_FROM_USER_ON_CREATE = 'jinja2_from_user_on_create'
    """Вычисляемое поле при помощи Jinja2 на основе объекта-пользователя при его создании"""

class PersonalNotificationStatusEnum(Enum):
    """Статусы отправки индивидуальных уведомлений пользователям"""
    INACTIVE   = 'inactive'
    TO_DELIVER = 'to_deliver'
    DELIVERED  = 'delivered'

class ReplyTypeEnum(Enum):
    """
    Тип ответа на сообщения
    """
    BRANCH_START     = 'branch_start'
    FULL_TEXT_ANSWER = 'full_text_answer'
    FAST_ANSWER      = 'fast_answer'
    
class KeyboardKeyStatusEnum(Enum):
    """
    Статус кнопки на клавиатуре
    """
    NORMAL   = 'normal'   # Обычная клавиша

    BACK = 'back'
    """Вернуться на меню выше"""

    DEFERRED = 'deferred' # Вернуться к отложенному вопросу - отображается только когда у пользователя заполненно поле отложенного вопроса
    ME       = 'me'       # Посмотреть свою пользовательскую запись (основные и откладываемые вопросы)

    ME_CHANGE = 'me_change'
    """Изменение параметров регистрации"""
    
    QR = 'qr'
    """Показать QR код пользователя"""

    NEWS = 'news'
    """Отобразить новости сообщества"""

    PROMOCODES = 'promocodes'
    """Отобразить доступные промокоды"""

    INACTIVE = 'inactive' # Не актвная клавиша - не отображается

class NotificationStatusEnum(Enum):
    """
    Статус отправки уведомлений
    """
    INACTIVE   = 'inactive'
    TO_DELIVER = 'to_deliver'
    PLANNED    = 'planned'
    DELIVERED  = 'delivered'

class PromocodeStatusEnum(Enum):
    """Статус промокодов"""
    ACTIVE   = 'active'
    EXPIRED  = 'expired'
    INACTIVE = 'inactive'

class UserFieldDataPlain(NamedTuple):
    key:   str
    value: str

class UserFieldDataPrepared(NamedTuple):
    value: str
    document_bucket: str
    image_bucket:    str
    empty: bool = False
    personal_notification_status: PersonalNotificationStatusEnum|None = None

class UserDataPrepared(NamedTuple):
    id:       int
    chat_id:  int
    username: str
    fields:   dict[int, UserFieldDataPrepared]