from sqlalchemy import select

from src.bot.exceptions import CouldNotGetUserNameFieldValueError
from src.bot.telegram.application import BBApplication
from src.utils.db_model import Field, Settings, User, UserFieldValue


async def user_get_field_value_by_key(app: BBApplication, user: User, key: str) -> str | None:
    """Получить значение пользовательского поля по заданному ключу"""
    async with app.provider.db_sessionmaker() as session:
        return await session.scalar(
            select(UserFieldValue.value)
            .where(Field.key == key)
            .where(UserFieldValue.field_id == Field.id)
            .where(UserFieldValue.user_id == user.id)
            .limit(1)
        )


async def user_get_name_field_value(app: BBApplication, user: User, settings: Settings) -> str:
    user_name_field_value = await user_get_field_value_by_key(app, user, settings.user_name_field_plain)
    if not user_name_field_value:
        raise CouldNotGetUserNameFieldValueError
    return user_name_field_value
