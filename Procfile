release: python ./manage.py migrate
worker: celery worker -A boloo_shop -B -l info
web: gunicorn boloo_shop.wsgi:application --preload --workers 1