release: python ./manage.py migrate
worker: python manage.py celery worker -A boloo_shop -B -l info
web: gunicorn app.wsgi:application --preload --workers 1