import sys
from asyncio import Queue
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import insert, update
from telegram import (
    Bot,
    BotCommand,
    BotDescription,
    BotName,
    BotShortDescription,
)
from telegram.ext import Application, CallbackContext
from telegram.ext._basepersistence import BasePersistence
from telegram.ext._baseupdateprocessor import BaseUpdateProcessor
from telegram.ext._contexttypes import ContextTypes
from telegram.ext._updater import Updater

from src.bot.exceptions import JobQueueNotFoundError
from src.utils.bb_provider import BBProvider
from src.utils.custom_types import BotStatusEnum
from src.utils.db_model import BotStatus, Log


class BBApplication(Application):  # type: ignore
    """
    Класс приложения бота в коробке
    """

    UPDATE_GROUP_USER_REQUEST = 0
    UPDATE_GROUP_GROUP_REQUEST = 2
    UPDATE_GROUP_CHAT_MEMBER = 3

    START_COMMAND = "start"
    HELP_COMMAND = "help"
    REPORT_COMMAND = "report"

    def __init__(
        self,
        *,
        provider: BBProvider,
        bot: Any,
        update_queue: Queue[object],
        updater: Updater | None,
        job_queue: Any,
        update_processor: BaseUpdateProcessor,
        persistence: BasePersistence | None,  # type: ignore
        context_types: ContextTypes,  # type: ignore
        post_init: Callable[[Application], Coroutine[Any, Any, None]] | None,  # type: ignore
        post_shutdown: Callable[[Application], Coroutine[Any, Any, None]] | None,  # type: ignore
        post_stop: Callable[[Application], Coroutine[Any, Any, None]] | None,  # type: ignore
    ) -> None:
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
            post_stop=post_stop if post_stop else self._post_stop,
        )
        self.provider = provider
        self.status = BotStatusEnum.OFF

    async def update_bot_status(self) -> None:
        """Обновить статус бота - используется при старте программы"""
        bot_status = await self.provider.bot_status
        self.status = bot_status.bot_status

    async def _bot_status_switch_job(self, _: CallbackContext) -> None:  # type: ignore
        await self.update_bot_status()

        if self.status == BotStatusEnum.ON:
            return logger.debug("Checked bot status... should be on, so continuing")

        logger.warning(f"Got bot status {self.status=}... so restarting")

        async with self.provider.db_sessionmaker() as session:
            if self.status in [BotStatusEnum.RESTART, BotStatusEnum.RESTARTING]:
                await session.execute(update(BotStatus).values(bot_status=BotStatusEnum.RESTARTING))
                await self.write_log("Exiting into `restarting` mode")
            elif self.status == BotStatusEnum.SERVICE:
                await self.write_log("Exiting into `service` mode")
            elif self.status == BotStatusEnum.OFF:
                await self.write_log("Exiting into `off` mode")

            await session.commit()

            sys.exit(0)

    async def _post_init(self, _: Application) -> None:  # type: ignore
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

        if self.status in [BotStatusEnum.RESTART, BotStatusEnum.RESTARTING]:
            async with self.provider.db_sessionmaker() as session:
                await session.execute(update(BotStatus).values(bot_status=BotStatusEnum.ON))
                await session.commit()
            await self.write_log("Starting in `standard` mode after restart")

        elif self.status == BotStatusEnum.SERVICE:
            await self.write_log("Starting in `service` mode")

        elif self.status == BotStatusEnum.ON:
            await self.write_log("Starting in `standard` mode")

        else:
            await self.write_log("Starting in `strange mode`, recheck code!")

        settings = await self.provider.settings

        bot_my_name: BotName = await bot.get_my_name()
        if bot_my_name.name != settings.bot_my_name_plain:
            await bot.set_my_name(settings.bot_my_name_plain)
            logger.info("Found difference in my name - updated")

        bot_my_short_description: BotShortDescription = await bot.get_my_short_description()
        if bot_my_short_description.short_description != settings.bot_my_short_description_plain:
            await bot.set_my_short_description(settings.bot_my_short_description_plain)
            logger.info("Found difference in my short description - updated")

        bot_my_description: BotDescription = await bot.get_my_description()
        if bot_my_description.description != settings.bot_my_description_plain:
            await bot.set_my_description(settings.bot_my_description_plain)
            logger.info("Found difference in my description - updated")

        bot_my_comands: tuple[BotCommand] = await bot.get_my_commands()  # type: ignore
        my_commands = (BotCommand(self.HELP_COMMAND, settings.bot_help_command_description_plain),)
        if bot_my_comands != my_commands:
            await bot.set_my_commands(my_commands)
            logger.info("Found difference in my commands - updated")

        if not self.job_queue:
            raise JobQueueNotFoundError

        self.job_queue.run_repeating(self._bot_status_switch_job, interval=5)
        logger.info("Started bot status switch job")

        logger.info("Post init complete...")

    async def _post_stop(self, _: Application) -> None:  # type: ignore
        """Внутренняя функция, используемая для логгирования остановки бота"""
        logger.warning("Writing logs before stop")
        await self.write_log("Stopped an application")

    async def write_log(self, message: str) -> None:
        """Запись лога в БД"""
        async with self.provider.db_sessionmaker() as session:
            await session.execute(insert(Log).values(timestamp=datetime.now(), message=message))  # noqa: DTZ005
            await session.commit()
