#!/bin/bash
PROJECT_PATH=/opt/dix/aspic

cd $PROJECT_PATH
PIPENV_VENV_PATH=$PROJECT_PATH/.venv/bin
PATH="$PIPENV_VENV_PATH:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
echo PATH=$PATH

# Загружаем .env
set -a
source .env
set +a

# Запуск с выводом ошибок
pipenv run $PIPENV_VENV_PATH/python3 -m app.main 2>&1 | tee $PROJECT_PATH/prj_log_error.log