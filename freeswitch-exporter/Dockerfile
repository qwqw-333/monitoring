FROM python:3.12-slim
LABEL maintainer="monitoring-stack"

WORKDIR /app
COPY exporter.py event_detector.py ./

EXPOSE 9724

USER nobody
ENTRYPOINT ["python3", "-u", "exporter.py"]
