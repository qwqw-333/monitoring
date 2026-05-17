FROM python:3.12-slim
LABEL maintainer="monitoring-stack"

WORKDIR /app
COPY exporter.py ./

EXPOSE 9725

USER nobody
ENTRYPOINT ["python3", "-u", "exporter.py"]
