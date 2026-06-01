FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt ./

RUN apk add --no-cache --virtual .build-deps \
      gcc \
      musl-dev \
      libffi-dev \
      openssl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY charge_location_sync.py ./

EXPOSE 5000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "30", "charge_location_sync:app"]
