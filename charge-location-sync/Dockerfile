FROM python:3.12-alpine

WORKDIR /app

# 正确指定虚拟构建依赖组 .build-deps
RUN apk add --no-cache --virtual .build-deps \
      gcc \
      musl-dev \
      libffi-dev \
      openssl-dev \
    && pip install --no-cache-dir flask pynacl requests gunicorn \
    && apk del .build-deps

COPY . /app

EXPOSE 5000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "30", "charge_location_sync:app"]
