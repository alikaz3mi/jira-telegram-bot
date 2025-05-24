FROM python:3.11.11-slim

RUN apt-get update && apt-get install -y curl ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app


RUN pip install --no-cache-dir -e .
RUN mkdir -p /app/data/storage && \
    for year in {1404..1407}; do \
        curl "https://persian-calendar-api.sajjadth.workers.dev/?year=$year" -o "/app/data/storage/$year.json" && \
        [ -s "/app/data/storage/$year.json" ] || exit 1; \
    done


# Run bot.py when the container launches
CMD ["/bin/bash"]
