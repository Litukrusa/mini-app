# --- Сборка VK Mini App (React + Vite) ---
FROM node:20-alpine AS frontend

WORKDIR /build/miniapp/frontend

COPY miniapp/frontend/package.json miniapp/frontend/package-lock.json ./
RUN npm ci

COPY miniapp/frontend/ ./
RUN npm run build

# --- Бот + HTTP Mini App ---
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MINIAPP_ENABLED=1 \
    MINIAPP_HOST=0.0.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY main.py ./
COPY scripts/ ./scripts/

# Статика miniapp из этапа сборки (index.html + assets)
COPY --from=frontend /build/miniapp/static ./miniapp/static

# Кэш групп / преподавателей / аудиторий (если есть в репозитории)
COPY bot/data/ ./bot/data/

# Порт задаётся в Dokploy: MINIAPP_PORT или PORT (см. bot/config.py)

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request; p=os.environ.get('MINIAPP_PORT') or os.environ.get('PORT','8080'); urllib.request.urlopen('http://127.0.0.1:%s/api/health'%p, timeout=3)"

CMD ["python", "main.py"]
