FROM python:3.11.11-slim as builder

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt setup.py ./
COPY jira_telegram_bot/__init__.py ./jira_telegram_bot/


RUN pip install setuptools
RUN pip install --no-cache-dir -e .
RUN mkdir -p /app/data/storage && \
    for year in {1404..1407}; do \
        curl "https://persian-calendar-api.sajjadth.workers.dev/?year=$year" -o "/app/data/storage/$year.json" && \
        [ -s "/app/data/storage/$year.json" ] || exit 1; \
    done


CMD ["/bin/bash"]
