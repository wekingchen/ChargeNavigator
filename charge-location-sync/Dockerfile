FROM python:3.10-alpine

WORKDIR /app

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    && pip install --no-cache-dir flask pynacl requests \
    && apk del gcc musl-dev

COPY . /app

EXPOSE 5000

CMD ["python", "charge_location_sync.py"]
