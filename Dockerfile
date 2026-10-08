FROM python:slim AS builder
LABEL authors="Vinicius Meireles"
ARG USER_NAME=app_user
ARG USER_ID=1000
ARG GROUP_ID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.docker_venv
ENV PATH="/app/.docker_venv/bin:${PATH}"

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --no-editable

ADD . /app

RUN groupadd -g ${GROUP_ID} ${USER_NAME} \
    && useradd -u ${USER_ID} -g ${GROUP_ID} -d /app -s /bin/sh -m ${USER_NAME} \
    && mkdir -p /media /staticfiles \
    && chown ${USER_NAME}:${USER_NAME} /media /staticfiles

RUN chown -R ${USER_NAME}:${USER_NAME} /app /uv /uvx /bin || true
USER ${USER_NAME}

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/app/run.sh"]
