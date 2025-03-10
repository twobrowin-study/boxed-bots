### Builder ###
FROM python:3.12-slim AS builder

ENV PIP_REQUESTS_TIMEOUT=120
ENV POETRY_REQUESTS_TIMEOUT=120

WORKDIR /app

RUN pip install poetry==2.0.1

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-cache --no-interaction --only=main

### Runtime ###
FROM python:3.12-slim AS runtime

WORKDIR /app
ENV APP_HOME=/app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

ARG APP_PATH=unknown

COPY src/utils/ src/utils/
COPY src/$APP_PATH/ src/$APP_PATH/
COPY config/ config/
COPY build/separated-images/entrypoint.sh ./

ENV APP_NAME=${APP_PATH}
CMD ["sh", "entrypoint.sh"]
