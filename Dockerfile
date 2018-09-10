FROM python:3.6.0-onbuild
CMD /usr/local/bin/gunicorn -w 2 -b :5000 app:app