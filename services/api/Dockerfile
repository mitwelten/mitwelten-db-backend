FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /service
COPY ./requirements.txt /service/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /service/requirements.txt

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "80"]
