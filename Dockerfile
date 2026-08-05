FROM python:3.12.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN addgroup --system tradearena \
    && adduser --system --ingroup tradearena --home /nonexistent tradearena

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY migrations ./migrations
COPY tradearena ./tradearena

USER tradearena

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)"

CMD ["python", "-m", "tradearena", "serve"]
