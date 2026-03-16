FROM python:3.12-slim-bookworm

ENV IS_IN_DOCKER=Yes
ENV PYTHONPATH=/opt/dix/aspic
ENV TZ=Europe/Moscow
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/dix/aspic

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    libmagic1 \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/Europe/Moscow /etc/localtime

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY ./app ./app
COPY README.md .
COPY .env .

# Создание необходимых директорий
RUN mkdir -p /opt/dix/aspic/data/files /opt/dix/aspic/data/preview

# Порт
EXPOSE 15191

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:15191/ || exit 1

# Запуск с proxy-headers для корректного определения IP
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "15191", "--workers", "1", "--proxy-headers"]