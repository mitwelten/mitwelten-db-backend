FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9
COPY ./viz/requirements.txt /requirements.txt
RUN pip install -U pip
RUN pip install --no-cache-dir --upgrade -r /requirements.txt