FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY paperless_finom ./paperless_finom

# Persist the audit DB outside the container.
VOLUME ["/data"]
ENV FINOM_DB_PATH=/data/finom_sync.sqlite3

# Default: run one sync and exit (good for `docker run` in a cron).
# For the HTTP trigger, override with: ["serve","--host","0.0.0.0"]
ENTRYPOINT ["python", "-m", "paperless_finom.cli"]
CMD ["sync"]
