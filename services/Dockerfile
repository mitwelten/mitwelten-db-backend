FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY ./results /app

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY credentials.py /app/credentials.py
