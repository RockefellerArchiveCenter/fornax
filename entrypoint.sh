#!/bin/bash

# Apply database migrations
./wait-for-it.sh db:5432 -- echo "Creating config file"

if [ ! -f manage.py ]; then
  cd fornax
fi

if [ ! -f fornax/config.py ]; then
    cp fornax/config.py.example fornax/config.py
fi

echo "Apply database migrations"
python manage.py migrate

echo "Starting server"
python manage.py runserver 0.0.0.0:8003
