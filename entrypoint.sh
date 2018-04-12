#!/bin/bash

# Apply database migrations
echo "Apply database migrations"
./wait-for-it.sh db:5432 -- python manage.py migrate

# Create users
echo "Create users"
python manage.py shell -c "from django.contrib.auth.models import User; \
  User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')"

#Start server
echo "Starting server"
python manage.py runserver 0.0.0.0:8000
