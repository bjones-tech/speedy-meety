web: gunicorn spark.wsgi --log-file -
worker: celery worker --app=spark --beat