#!/bin/bash
set -e

# Create logs directory
mkdir -p /app/logs
chmod 777 /app/logs

# Print diagnostic information
echo "Python path:"
python -c 'import sys; print(sys.path)'

echo "Checking WSGI module:"
python -c 'import irip.wsgi; print("WSGI module successfully imported")'

# Run database migrations
echo "Running migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn
echo "Starting Gunicorn server..."
exec python -m gunicorn irip.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --capture-output \
    --enable-stdio-inheritance
