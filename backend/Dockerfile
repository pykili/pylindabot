FROM python:3.7-slim

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

COPY requirements.txt /root

RUN BUILD_DEPS='build-essential python3-dev libcurl4-openssl-dev libssl-dev' \
    && apt-get update && apt-get install -y --no-install-recommends ${BUILD_DEPS} \
    && apt-get install -y --no-install-recommends vim \
    && pip3 install -U pip && pip3 install -r /root/requirements.txt \
    && mkdir -p /var/www/app \
    && apt-get autoremove -y ${BUILD_DEPS} \
    && apt-get clean \
    && mkdir -p /var/cache/pykilibot \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /var/www/app

RUN touch .env

COPY src/ /var/www/app
