FROM python:3.11-slim-buster

WORKDIR /

COPY notification_service/ /notification_service

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    curl \
    build-essential

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml poetry.lock README.md /
RUN poetry install
WORKDIR /notification_service

ENTRYPOINT ["poetry", "run", "python", "main.py"]
