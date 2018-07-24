#!/bin/bash

# Apply database migrations
./wait-for-it.sh db:5432 -- echo "Creating config file"

if [ ! -f manage.py ]; then
  cd fornax
fi

echo "Apply database migrations"
if [ ! -f fornax/config.py ]; then
    cp fornax/config.py.example fornax/config.py
fi

python manage.py migrate

# Create users
echo "Create users"
python manage.py shell -c "from django.contrib.auth.models import User; \
  User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')"

#Start server
echo "Starting server"
python manage.py runserver 0.0.0.0:8003
