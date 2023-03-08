FROM python:3.11
WORKDIR /service
COPY ./requirements.txt /service/requirements.txt
RUN pip install -U pip
RUN pip install --no-cache-dir --upgrade -r /service/requirements.txt
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "80"]
