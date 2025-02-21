FROM python:3.11.11-slim

WORKDIR /app

COPY . /app


RUN pip install --no-cache-dir -e .


# Run bot.py when the container launches
CMD ["/bin/bash"]
