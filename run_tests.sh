#!/bin/bash

pytest tests/test_units.py
bash docker-build.sh
docker-compose up -d
pytest tests/test_system.py
docker stop $(docker ps -aq) 