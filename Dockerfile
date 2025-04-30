FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt . 
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY ./src ./src
COPY main.py .
COPY config_example.yaml ./config.yaml

ENV PYTHONUNBUFFERED=1

ENTRYPOINT [ "python", "main.py" ]

CMD ["-c", "config.yaml"]