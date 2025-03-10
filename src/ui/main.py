import uvicorn
from loguru import logger

from src.ui.app import app, provider

if __name__ == "__main__":
    logger.info("Starting now...")
    try:
        uvicorn.run(
            app=app,
            host="0.0.0.0",
            port=8080,
            reload=False,
            log_config=f"{provider.config.app_home}/src/ui/log_conf.yaml",
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Done! Have a great day!")
