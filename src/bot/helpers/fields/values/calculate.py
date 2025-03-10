from jinja2 import Template
from loguru import logger
from sqlalchemy import select

from src.bot.exceptions import CouldNotCalculateJinja2TemplateFieldAfterUserRegistrationError
from src.bot.helpers.fields.values.prepare import prepare_field_value_str_value
from src.bot.helpers.fields.values.upsert import user_upsert_string_field_value
from src.bot.telegram.application import BBApplication
from src.utils.custom_types import FieldStatusEnum
from src.utils.db_model import Field, User


async def user_calculate_after_registration_fields(app: BBApplication, user: User) -> None:
    """Вычислить поля, вычисляемые после регистрации, пользователя"""
    logger.debug(f"Calculating after registration fields for user {user.id=}")

    async with app.provider.db_sessionmaker() as session:
        jinja2_after_user_registration_fields = await session.scalars(
            select(Field).where(Field.status == FieldStatusEnum.JINJA2_FROM_USER_AFTER_REGISTRATION)
        )

    user_dict = user.to_plain_dict()

    logger.debug(f"Calculating user fields over values {user_dict=}")

    for field in jinja2_after_user_registration_fields:
        logger.debug(f"Calculating after registration field {field.key=} for user {user.id=}")

        if not field.question_markdown_or_j2_template:
            raise CouldNotCalculateJinja2TemplateFieldAfterUserRegistrationError

        field_value = await Template(
            field.question_markdown_or_j2_template,
            enable_async=True,
        ).render_async(user=user_dict)

        field_value_prepared = prepare_field_value_str_value(app, field, field_value)
        if field_value_prepared:
            await user_upsert_string_field_value(
                app=app, user=user, field=field, message=None, field_value=field_value_prepared
            )
