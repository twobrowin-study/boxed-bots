import asyncio
from loguru import logger

from utils.custom_types import BotStatusEnum

from bot.application_builder import BBApplicationBuilder
from bot.application import BBApplication

from bot.map_handlers import (
    map_service_mode_handlers,
    map_default_handlers
)

from bot.default_handlers import error_handler

if __name__ == '__main__':
    logger.info("Starting...")
    
    app: BBApplication = BBApplicationBuilder() \
        .concurrent_updates(True) \
        .build()
    
    app.add_error_handler(error_handler)

    logger.info("Getting current bot status...")
    loop = asyncio.new_event_loop()
    loop.run_until_complete(app.update_bot_status())

    if app.status == BotStatusEnum.OFF:
        logger.warning("Bot should be OFF... so exiting... Bye!")
        exit(0)
    elif app.status in [BotStatusEnum.RESTART, BotStatusEnum.RESTARTING]:
        logger.success("Bot is starting afer restart... continuing to init with default handlers")
        map_default_handlers(app)
    elif app.status == BotStatusEnum.SERVICE:
        logger.warning("Bot should be run in service mode... so settings only service mode handlers")
        map_service_mode_handlers(app)
    elif app.status == BotStatusEnum.ON:
        logger.success("Bot is on! So continuing with default handlers...")
        map_default_handlers(app)
    else:
        logger.error("Unknown state... exiting!")
        exit(1)
    
    asyncio.set_event_loop(loop)
    app.run_polling()

    logger.info("Done! Have a greate day!")