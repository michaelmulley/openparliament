#!/bin/sh
python manage.py collectstatic --noinput
gunicorn parliament.wsgi -c gunicorn.conf.py
