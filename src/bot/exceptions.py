class JobQueueNotFoundError(Exception):
    """Не найдено очереди заданий"""


class MessageIsEmptyError(Exception):
    """Сообщение не задано"""


class CallbackQueryIsEmptyError(Exception):
    """Ответ на нажатие inline-кнопки пользователем не задано"""


class CallbackQueryDataIsEmptyError(Exception):
    """Нет данных нажатой пользователем inline-кнопки"""


class CallbackQueryMessageIsEmptyOrInaccesibleError(Exception):
    """Пользователь ответил на несуществующее сообщение"""


class ChatIsEmptyError(Exception):
    """Чат не задан"""


class ChatMemberIsEmptyError(Exception):
    """Пользователь не задан"""


class GroupNotFoundError(Exception):
    """Группа не найдена"""


class GroupPassesNoFieldError(Exception):
    """Нет поля для сохранения пропусков"""


class GroupPassesNoBucketError(Exception):
    """Нет бакета для сохранения изображения пропусков"""


class GroupPassesNoDocumentError(Exception):
    """Нет файла в запросах пропусков"""


class TelegramUserNotFoundError(Exception):
    """Пользователь telegram не найден"""


class UserNotFoundError(Exception):
    """Пользователь не найден"""


class FirstFieldOfBranchNotFoundError(Exception):
    """Не найдено первое поле ветки полей"""


class CouldNotCreateUserError(Exception):
    """Не удалось создать пользователя"""


class CouldNotUpdateUserRegistrationError(Exception):
    """Не удалось обновить регистрацию пользователя"""


class CouldNotSaveUserKeyboardKeyHitError(Exception):
    """Не удалось сохранить нажатие клавиши клавиатуры"""


class CouldNotRestoreDeferredFieldError(Exception):
    """Не удалось вернуть отложенный вопрос"""


class CouldNotSendFirstFieldQuestionError(Exception):
    """Не удалось выслать первый вопрос"""


class CouldNotReSendFieldQuestionError(Exception):
    """Не удалось выслать повторно вопрос в случае несвопадения типа"""


class CouldNotSendNextFieldQuestionError(Exception):
    """Не удалось выслать следующий вопрос"""


class CouldNotSendReplyMessageReplyStatusRepliesError(Exception):
    """Не удалось выслать финальное сообщение сообщения с условием при сохранении ответа на вопрос"""


class UserShuldNotAnswerBooleanFieldError(Exception):
    """Пользователь не должен отвечать вручную на булевы поля"""


class UserShoulAnswerOnlyNormalFieldsError(Exception):
    """Пользователь должен отвечать только на нормальные поля"""


class CouldNotApplyValidationRemoveRegexpOnFieldError(Exception):
    """Не удалось применить функцию удаления данных по регулярному выражению"""


class CouldNotGetUserNameFieldValueError(Exception):
    """
    Не удалось получить значение пользовательского поля с именем пользователя

    Оно должно задаваться до попытки загрузить файл
    """


class CouldNotUploadFileToMinioWithoutBucketError(Exception):
    """Не удалось загрузить файл в minio поскольку не задан бакет"""


class CouldNotUpsertFieldValueError(Exception):
    """Не удалось создать значение пользовательского поля"""


class CouldNotCalculateJinja2TemplateFieldAfterUserRegistrationError(Exception):
    """Не удалось вычислить jinja2 поле после регистрации пользователя"""


class NoPassFieldIsFoundError(Exception):
    """Не задано поле пропуска"""


class NoFieldToRequestPassIsFoundError(Exception):
    """Не задано поле пропуска"""


class FastAnswerNoReplyableConditionMessageError(Exception):
    """Нет сообщения с условием и ответом для быстрого ответа"""


class FastAnswerNoFieldError(Exception):
    """Нет поля для записи быстрого ответа"""


class FastAnswerNotEnoughValuesError(Exception):
    """Недостаточно вариантов значений для поля для быстрого ответа"""


class FastAnswerNotEnoughReplyAnswersError(Exception):
    """Недостаточно ответов на нажатие кнопок пользователем для быстрого ответа"""


class FullTextAnswerNoReplyableConditionMessageError(Exception):
    """Нет сообщения с условием и ответом для полнотекстового ответа"""


class FullTextAnswerNoFieldError(Exception):
    """Нет поля для записи полнотекстового ответа"""


class FullTextAnswerNoFieldQuestionError(Exception):
    """Нет вопроса поля для записи полнотекстового ответа"""


class BranchStartNoReplyableConditionMessageError(Exception):
    """Нет сообщения с условием и ответом для полнотекстового ответа"""


class BranchStartNoBranchError(Exception):
    """Нет поля для записи полнотекстового ответа"""


class BranchStartNoBranchFirstFieldQuestionError(Exception):
    """Нет вопроса поля для записи полнотекстового ответа"""


class PassFieldToChangeNotFoundError(Exception):
    """Не найдено поле для изменения при отправке заявки на пропуск"""


class PassFieldToChangeNoQuestionError(Exception):
    """Нет вопроса для при изменении поля при отправке заявки на пропуск"""


class ChangeFieldNotFoundError(Exception):
    """Не найдено поле для изменения при отправке заявки на пропуск"""


class ChangeFieldNoQuestionError(Exception):
    """Нет вопроса для при изменении поля при отправке заявки на пропуск"""


class UserAfterChangeNotFoundError(Exception):
    """Пользователь после обновления значений не найден... странно"""


class NextReplyConditionMessageAfterFastAnswerWasNotFoundError(Exception):
    """Следующее сообщение не найдено после ответа пользователя на быстрое сообщение"""
