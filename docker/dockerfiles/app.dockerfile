FROM python:3.12-slim-bookworm

ENV IS_IN_DOCKER=Yes
ENV PYTHONPATH=/opt/dix/aspic

WORKDIR /opt/dix/aspic

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -snf /usr/share/zoneinfo/Europe/Moscow /etc/localtime

# Копирование зависимостей
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./app ./app
COPY README.md .
COPY .env .

# Порт
EXPOSE 15191

# Запуск
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "15191", "--workers", "1"]
#CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "15191"]