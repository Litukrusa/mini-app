#!/bin/bash
# Запуск VK Mini App для локального теста
cd "$(dirname "$0")"

if lsof -ti :8080 >/dev/null 2>&1; then
  echo "Порт 8080 занят. Останавливаю старый процесс..."
  lsof -ti :8080 | xargs kill 2>/dev/null || true
  sleep 1
fi

echo "Сборка фронтенда..."
(cd miniapp/frontend && npm run build) || exit 1

echo ""
echo "Запуск сервера..."
exec python3 run_miniapp_dev.py
