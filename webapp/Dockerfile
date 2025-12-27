
# start by pulling the python image
FROM python:3.9-alpine

# copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt

# switch working directory
WORKDIR /app

RUN \
 apk add --no-cache postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev && \
 python3 -m pip install -r requirements.txt --no-cache-dir && \
 pip install gunicorn && \
 apk --purge del .build-deps

# copy every content from the local file to the image
COPY . /app

CMD gunicorn -w 4 -b :80 wsgi:app
