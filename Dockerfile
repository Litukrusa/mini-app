# Сборка из корня репозитория (Dokploy: Docker Context = . , Docker File = Dockerfile)
# Рекомендуется вместо этого: Context = new , файл new/Dockerfile

FROM node:20-alpine AS frontend

WORKDIR /build

COPY new/miniapp/frontend/package.json new/miniapp/frontend/package-lock.json ./miniapp/frontend/
RUN cd miniapp/frontend && npm ci

COPY new/miniapp/frontend/ ./miniapp/frontend/
RUN cd miniapp/frontend && npm run build

FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MINIAPP_ENABLED=1 \
    MINIAPP_HOST=0.0.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY new/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY new/main.py ./main.py
COPY new/bot/ ./bot/
COPY new/scripts/ ./scripts/

COPY --from=frontend /build/miniapp/static ./miniapp/static

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os,urllib.request; p=os.environ.get('MINIAPP_PORT') or os.environ.get('PORT','3000'); urllib.request.urlopen('http://127.0.0.1:%s/api/health'%p, timeout=5)"

CMD ["python", "main.py"]
