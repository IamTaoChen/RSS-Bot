FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt . 
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN addgroup --gid 1000 rss && \
    adduser --uid 1000 --ingroup rss --disabled-password --gecos "" rss && \
    chown -R rss:rss /app && \
    mkdir -p /tmp/rss_cache && \
    chown rss:rss /tmp/rss_cache

COPY ./src ./src
COPY main.py .
COPY config_example.yaml ./config.yaml

USER rss
ENV PYTHONUNBUFFERED=1

ENTRYPOINT [ "python", "main.py" ]

CMD ["-c", "config.yaml"]