#!/bin/sh
python manage.py collectstatic --noinput
python manage.py compress -f
gunicorn parliament.wsgi -c gunicorn.conf.py
