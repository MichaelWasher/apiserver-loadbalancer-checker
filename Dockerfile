FROM docker.io/alpine:latest

RUN apk add python3 py3-pip
COPY ./ /app
RUN pip install -r /app/requirements.txt

ENTRYPOINT ["python3", "/app/app.py"]