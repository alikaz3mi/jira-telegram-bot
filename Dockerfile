FROM python:3.9-slim

WORKDIR /app

COPY . /app


RUN pip install --no-cache-dir -e .


# Run bot.py when the container launches
CMD ["python", "jirabot.py"]
