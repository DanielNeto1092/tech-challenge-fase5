FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system guardia \
    && adduser --system --ingroup guardia --home /app guardia

COPY pyproject.toml ./
COPY app ./app
COPY training ./training
COPY artifacts ./artifacts
COPY data ./data

RUN python -m pip install . \
    && mkdir -p /app/data/audit \
    && chown -R guardia:guardia /app/data/audit

USER guardia

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

