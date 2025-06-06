FROM python:3.10-alpine

WORKDIR /app

# 正确指定虚拟构建依赖组 .build-deps
RUN apk add --no-cache --virtual .build-deps \
      gcc \
      musl-dev \
      libffi-dev \
      openssl-dev \
    && pip install --no-cache-dir flask pynacl requests \
    && apk del .build-deps

COPY . /app

EXPOSE 5000

CMD ["python", "charge_location_sync.py"]
