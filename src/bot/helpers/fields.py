from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from utils.db_model import (
    User, Field,
    UserFieldValue,
    Settings
)
from utils.custom_types import FieldStatusEnum

async def get_first_field_question(session: AsyncSession, settings: Settings) -> Field:
    """
    Получить первое пользовательское поле, который нужно задать пользователю при регистрации
    """
    selected = await session.execute(
        select(Field)
        .where(Field.branch == settings.first_field_branch)
        .order_by(Field.id.asc())
        .limit(1)
    )
    return selected.scalar_one()

async def get_next_field_question_in_branch(session: AsyncSession, curr_field: Field) -> Field|None:
    """
    Получить следующий вопрос в той же ветке
    """
    selected = await session.execute(
        select(Field)
        .where(
            (Field.branch == curr_field.branch) &
            (Field.id > curr_field.id) &
            (Field.status != FieldStatusEnum.INACTIVE)
        )
        .order_by(Field.id.asc())
        .limit(1)
    )
    return selected.scalar_one_or_none()

async def get_user_field_value_by_key(session: AsyncSession, user: User, key: str) -> str|None:
    """
    Получить значение пользовательского поля по заданному ключу
    """
    selected = await session.execute(
        select(UserFieldValue.value)
        .where(
            (Field.key == key) &
            (UserFieldValue.field_id == Field.id) &
            (UserFieldValue.user_id  == user.id)
        )
        .limit(1)
    )
    return selected.scalar_one_or_none()