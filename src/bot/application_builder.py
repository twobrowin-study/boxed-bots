from telegram.ext import ApplicationBuilder

from bot.application import BBApplication
from utils.bb_provider import BBProvider

class BBApplicationBuilder(ApplicationBuilder):
    """
    Переопределённый класс `ApplicationBuilder` для нужд этого приложения

    Создаёт проводник ресурсов и устанавливает токен для бота из него
    """

    def __init__(self):
        super().__init__()
        
        self._provider = BBProvider()
        self._token    = self._provider.config.tg_token
        
        self._application_class  = BBApplication
        self._application_kwargs = {'provider': self._provider}