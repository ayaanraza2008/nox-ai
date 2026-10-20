FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=10000

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && python -m playwright install-deps chromium \
    && python -m playwright install chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN useradd --create-home --uid 10001 nox \
    && chown -R nox:nox /app /ms-playwright /home/nox

USER nox

EXPOSE 10000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
