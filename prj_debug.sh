#!/bin/bash
PROJECT_PATH=/opt/dix/aspic
cd $PROJECT_PATH

echo "=== ОТЛАДКА ==="
echo "1. Текущая директория: $(pwd)"
echo "2. Содержимое .env:"
cat .env
echo ""
echo "3. Проверка pipenv:"
which pipenv
pipenv --version
echo ""
echo "4. Проверка виртуального окружения:"
pipenv --venv
echo ""
echo "5. Установленные пакеты:"
pipenv run pip list
echo ""
echo "6. Попытка запуска main.py:"
pipenv run python -m app.main