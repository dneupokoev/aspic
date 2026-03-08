#!/bin/bash

#pipenv lock

rm docker/requirements.txt
pipenv requirements > docker/requirements.txt

rm docker/README.md
cp -R README.md docker/README.md

rm -rf docker/app
cp -R app docker/app

find ./docker -name "__pycache__" -exec rm -rf {} +
find ./docker -name "app.log" -type f -delete
find ./docker -name ".pytest_cache" -type d -exec rm -rf {} +
