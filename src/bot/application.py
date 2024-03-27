from asyncio import Queue
from typing import Any, Callable, Coroutine
from telegram.ext import Application
from telegram.ext._basepersistence import BasePersistence
from telegram.ext._baseupdateprocessor import BaseUpdateProcessor
from telegram.ext._contexttypes import ContextTypes
from telegram.ext._updater import Updater

from telegram import (
    Bot, BotName,
    BotShortDescription,
    BotDescription,
    BotCommand,
)

from datetime import datetime
from loguru import logger

from utils.bb_provider  import BBProvider
from utils.custom_types import BotStatusEnum

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy import insert, update
from utils.db_model import BotStatus, Log

class BBApplication(Application):
    """
    Класс приложения бота в коробке
    """

    UPDATE_GROUP_USER_REQUEST  = 0
    UPDATE_GROUP_GROUP_REQUEST = 2
    UPDATE_GROUP_CHAT_MEMBER   = 3

    START_COMMAND  = 'start'
    HELP_COMMAND   = 'help'
    REPORT_COMMAND = 'report'

    def __init__(
            self, *,
            provider: BBProvider, 
            bot: Any,
            update_queue: Queue[object],
            updater: Updater | None,
            job_queue: Any,
            update_processor: BaseUpdateProcessor,
            persistence: BasePersistence | None,
            context_types: ContextTypes,
            post_init: Callable[[Application], Coroutine[Any, Any, None]] | None,
            post_shutdown: Callable[[Application], Coroutine[Any, Any, None]] | None,
            post_stop: Callable[[Application], Coroutine[Any, Any, None]] | None
        ):
        super().__init__(
            bot=bot,
            update_queue=update_queue,
            updater=updater,
            job_queue=job_queue,
            update_processor=update_processor,
            persistence=persistence,
            context_types=context_types,
            post_init=post_init if post_init else self._post_init,
            post_shutdown=post_shutdown,
            post_stop=post_stop if post_stop else self._post_stop
        )
        self.provider = provider
        self.status   = BotStatusEnum.OFF
    
    async def update_bot_status(self) -> None:
        """
        Обновить статус бота - используется при старте программы
        """
        bot_status  = await self.provider.bot_status
        self.status = bot_status.bot_status
        
    async def _post_init(self, _: Application) -> None:
        """
        Стандартная функция инициализации бота

        Устанавливает имя, описание и команды бота

        Учитывает и сохряняет состояние:

            * Выключает бота если указано выключение

            * Переводит бота в активное состояние если указано состояние перезагрузки

            * Сохраняет состояние бота для учёта при запуске
        """
        bot: Bot = self.bot

        logger.info("Performing DB writes...")
        async with self.provider.db_session() as session:
            if self.status in [BotStatusEnum.RESTART, BotStatusEnum.RESTARTING]:
                await session.execute(
                    update(BotStatus).values(bot_status = BotStatusEnum.ON)
                )
                await self._write_log(session, "Starting in `standard` mode after restart")
            elif self.status == BotStatusEnum.SERVICE:
                await self._write_log(session, "Starting in `service` mode")
            elif self.status == BotStatusEnum.ON:
                await self._write_log(session, "Starting in `standard` mode")
            else:
                await self._write_log(session, "Starting in `strange mode`, recheck code!")
            
            await session.commit()
        
        settings = await self.provider.settings
        
        bot_my_name: BotName = await bot.get_my_name()
        if bot_my_name.name != settings.my_name:
            await bot.set_my_name(settings.my_name)
            logger.info("Found difference in my name - updated")

        bot_my_short_description: BotShortDescription = await bot.get_my_short_description()
        if bot_my_short_description.short_description != settings.my_short_description:
            await bot.set_my_short_description(settings.my_short_description)
            logger.info("Found difference in my short description - updated")

        bot_my_description: BotDescription = await bot.get_my_description()
        if bot_my_description.description != settings.my_description:
            await bot.set_my_description(settings.my_description)
            logger.info("Found difference in my description - updated")

        bot_my_comands: tuple[BotCommand] = await bot.get_my_commands()
        my_commands = (BotCommand(self.HELP_COMMAND, settings.help_command_description), )
        if bot_my_comands != my_commands:
            await bot.set_my_commands(my_commands)
            logger.info("Found difference in my commands - updated")
        
        logger.info("Post init complete... starting main update loop")
    
    async def _post_stop(self, _: Application) -> None:
        """
        Внутренняя функция, используемая для логгирования остановки бота
        """
        logger.warning("Writing logs before stop")
        await self.write_log("Stopped an application")
    
    async def _write_log(self, session: AsyncSession, message: str) -> None:
        """
        Запись лога в БД при уже инциализированной сессии
        """
        await session.execute(
            insert(Log).values(
                timestamp = datetime.now(),
                message   = message
            )
        )
    
    async def write_log(self, message: str) -> None:
        """
        Запись лога в БД
        """
        async with self.provider.db_session() as session:
            await self._write_log(session, message)
            await session.commit()