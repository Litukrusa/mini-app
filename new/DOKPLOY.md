# Деплой в Dokploy

## Вариант A — Docker Compose (проще)

1. Залейте репозиторий на GitHub.
2. В Dokploy: **Create Project** → **Create Service** → **Compose**.
3. Подключите репозиторий.
4. **Compose file path:**
   - из **корня** репозитория: `docker-compose.yml`
   - или если Root Directory = `new`: `docker-compose.yml` (файл `new/docker-compose.yml`)
5. **Environment** — добавьте переменные из [`.env.example`](.env.example) (или загрузите `.env`).
6. **Domains** — привяжите домен с HTTPS (Let's Encrypt).
7. **Ports** в настройках сервиса: контейнер слушает `PORT` (например `3000`). В `.env` задайте `PORT=3000`.

Проверка после деплоя: `https://ваш-домен/api/health` → `{"ok":true,...}`

---

## Вариант B — Dockerfile

1. **Create Service** → **Application** → **Dockerfile**.
2. Репозиторий → ветка `main` / `miniapps`.
3. Настройки сборки:

| Поле | Значение |
|------|----------|
| **Docker Context Path** | `new` |
| **Docker File** | `Dockerfile` |

Либо Context = `.` (корень репо) и Dockerfile из корня — см. `/Dockerfile`.

4. **Environment** — из `.env.example`.
5. **Ports** → `3000` (или ваш `PORT`).
6. **Health Check** (если есть в UI):

| Поле | Значение |
|------|----------|
| Path | `/api/health` |
| Port | тот же, что `PORT` |

7. **Domain** → HTTPS на этот сервис.

---

## Переменные окружения (минимум)

```
VK_TOKEN=...
MONGO_URI=...
MONGO_DB=ras
MONGO_COLLECTION=sessions
VK_APP_SECRET=...
VK_APP_ID=...
PORT=3000
MINIAPP_ENABLED=1
MINIAPP_HOST=0.0.0.0
```

Для доп. авторизации ДГТУ (ЭИОС): `EIOS_ENCRYPTION_KEY=...`

---

## VK Mini App после деплоя

1. URL приложения в VK: `https://ваш-домен/` (тот же домен, что в Dokploy).
2. В настройках мини-приложения VK укажите этот HTTPS-URL.
3. `VK_APP_SECRET` должен совпадать с защищённым ключом в VK.

---

## MongoDB

- Можно поднять **MongoDB** отдельным сервисом в Dokploy в той же сети.
- `MONGO_URI` вида: `mongodb://user:pass@mongodb:27017` (имя сервиса Mongo в compose).

---

## Логи и отладка

- Логи: Dokploy → сервис → **Logs**.
- Бот + Mini App в одном контейнере (`python main.py`).
- Если Mini App не открывается: проверьте `miniapp/static` (в образе собирается из `miniapp/frontend` при build).

---

## Обновление кэша групп (опционально)

На сервере один раз или по cron в контейнере:

```bash
docker exec -it <container> python scripts/fetch_rasp_cache.py
```

Или локально перед push — файлы `bot/data/*.json` уже в репозитории.
