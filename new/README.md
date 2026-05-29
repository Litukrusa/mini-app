# DGTY Timetable VK Bot

Бот для ВКонтакте для просмотра расписания занятий студентов и преподавателей ДГТУ и ПИ ДГТУ.

## Возможности

- 👥 Выбор и закрепление своей группы при первом запуске
- 📅 Просмотр расписания на сегодня, завтра и неделю
- 📱 **VK Mini App** — то же расписание в мини-приложении ВКонтакте (общая MongoDB с ботом)
- 🏫 Поддержка двух университетов: ДГТУ и ПИ ДГТУ
- 💾 Хранилище данных на MongoDB

## Требования

- Python 3.8+
- Токен VK-бота (сообщества)
- MongoDB (локально или удаленно)

## Установка

1. Перейдите в папку проекта и установите зависимости:
```bash
cd new
pip install -r requirements.txt
```

2. Установите переменные окружения:
```env
VK_TOKEN=ваш_токен_бота
UNIVERSITY_TYPE=T
MONGO_URI=mongodb://log:pass@ip:port
MONGO_DB=vk
MONGO_COLLECTION=sessions
```

3. Запустите бота:
```bash
python main.py
```

## Переменные окружения

| Переменная | Описание | Обязательна | По умолчанию |
|------------|----------|-------------|--------------|
| `VK_TOKEN` | Токен VK-сообщества | Да | - |
| `UNIVERSITY_TYPE` | `T` — ПИ ДГТУ, `D` — ДГТУ | Нет | `T` |
| `DGTU_API_TOKEN` | Опционально: Bearer-токен, если API начнёт требовать авторизацию для списков | Нет | - |
| `MONGO_URI` | URI подключения к MongoDB | Нет | `mongodb://localhost:27017/` |
| `MONGO_DB` | Название базы данных | Нет | `ras` |
| `MONGO_COLLECTION` | Название коллекции | Нет | `sessions` |
| `EIOS_ENCRYPTION_KEY` | Ключ Fernet для шифрования логина/пароля ЭИОС в MongoDB (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) | Да, для доп. авторизации | - |
| `MONGO_EIOS_COLLECTION` | Коллекция учётных данных ЭИОС (vk_id, eios_id, шифр. логин/пароль) | Нет | `eios_credentials` |
| `MINIAPP_ENABLED` | Запуск HTTP-сервера Mini App | Нет | `1` |
| `MINIAPP_HOST` | Хост привязки сервера | Нет | `0.0.0.0` |
| `MINIAPP_PORT` | Порт Mini App | Нет | `8080` |
| `VK_APP_SECRET` | Защищённый ключ приложения VK (для проверки `sign`) | Да* | - |
| `VK_APP_ID` | ID мини-приложения (для документации / кнопок) | Нет | - |
| `MINIAPP_ALLOW_UNSIGNED` | Разрешить API без подписи (только dev) | Нет | `0` |

\* Обязателен для продакшена Mini App. Без него запросы к API будут отклоняться.

## VK Mini App — как добавить

Мини-приложение раздаётся тем же процессом, что и бот (`python main.py`), по HTTPS на порту `8080` (или за reverse proxy).

### 1. Создать приложение VK

1. Откройте [vk.com/editapp?act=create](https://vk.com/editapp?act=create) → тип **Мини-приложение**.
2. Запомните **ID приложения** (`VK_APP_ID`).
3. В настройках приложения → **Настройки** скопируйте **Защищённый ключ** → `VK_APP_SECRET`.
4. Укажите **URL приложения** (обязательно **HTTPS**), например:
   - `https://raspis.example.com/` — главная страница отдаёт `miniapp/static/index.html`
   - при деплое в Docker пробросьте порт `8080` и повесьте nginx/Caddy с TLS.

### 2. Переменные окружения

```env
MINIAPP_ENABLED=1
MINIAPP_PORT=8080
VK_APP_SECRET=ваш_защищённый_ключ
VK_APP_ID=12345678
# те же MONGO_* и DGTU_API_TOKEN, что у бота — профиль общий
EIOS_ENCRYPTION_KEY=...   # для «Дополнительной авторизации» ДГТУ (бот и Mini App)
```

### Дополнительная авторизация ЭИОС (только ДГТУ)

Для части групп (например, ИПБТ11) API без входа в ЭИОС отдаёт неполное расписание. В боте и Mini App доступна кнопка **«Дополнительная авторизация»** — логин/пароль от edu.donstu.ru сохраняются в MongoDB в зашифрованном виде; все запросы к API ДГТУ идут с токеном пользователя. При **«Сбросить профиль»** / **«Сменить профиль»** данные ЭИОС удаляются.

### 3. Деплой

```bash
docker build -t dgty-vk-bot .
docker run -p 8080:8080 \
  -e VK_TOKEN=... \
  -e VK_APP_SECRET=... \
  -e MONGO_URI=... \
  dgty-vk-bot
```

Проверка: `curl https://ваш-домен/api/health` → `{"ok": true, "service": "dgtu-miniapp"}`.

### 4. Привязать к сообществу

1. Управление сообществом → **Приложения** → **Добавить приложение** → выберите созданное мини-приложение.
2. Либо в чате бота: **Управление** → **Настройки для бота** → раздел мини-приложений.
3. Опционально — кнопка в клавиатуре бота (тип `open_app` в VK API) с `app_id` = `VK_APP_ID` и `owner_id` = ID сообщества.

### 5. Как это работает

- Пользователь открывает Mini App → VK передаёт launch-параметры (`vk_user_id`, `sign`, …).
- Фронтенд (`miniapp/static/`) отправляет их в заголовке `X-VK-Launch-Params`.
- Бэкенд (`bot/miniapp/`) проверяет подпись и использует тот же `vk_user_id`, что и peer_id в личке с ботом — **профиль и расписание синхронизированы**.

### Каталог групп (файлы + API)

Списки групп загружаются с API ДГТУ и кэшируются в `bot/data/`:

- `bot/data/groups_T.json` — ПИ ДГТУ  
- `bot/data/groups_D.json` — ДГТУ  

Обновить вручную:

```bash
python3 scripts/fetch_rasp_cache.py
```

В Mini App: **Профиль → Группа** — сразу показывается список из файла; поиск фильтрует по названию. Расписание — через API `/Rasp` по `id` группы.

### Сборка фронтенда (VKUI)

```bash
cd miniapp/frontend
npm install
npm run build   # результат → miniapp/static/
```

Тема: автоматически **тёмная** в VK (`VKWebAppGetConfig`) или при локальном тесте на `localhost`. Светлая тема — если так настроено в клиенте VK.

### Структура Mini App

```
miniapp/frontend/   # React + VKUI (исходники)
miniapp/static/     # собранный фронтенд
bot/miniapp/        # API, проверка sign, работа с MongoDB
```

## Структура проекта

```
new/
├── main.py                 # Бот + Mini App
├── run_miniapp_dev.py      # Только HTTP (локально)
├── start_miniapp.sh
├── bot/
│   ├── vk_bot.py, vk_handlers.py, …
│   ├── miniapp/            # aiohttp API, vk_auth, service
│   ├── data/               # groups_*.json, teachers_*.json, …
│   └── api/timetable.py
├── miniapp/
│   ├── frontend/           # React + VKUI
│   └── static/             # Сборка (в Docker — из frontend)
├── scripts/fetch_rasp_cache.py
├── Dockerfile
└── requirements.txt
```

## Получение токена VK

1. Создайте сообщество ВКонтакте
2. Перейдите в "Управление" → "Работа с API"
3. Создайте ключ доступа с правами:
   - `messages` - доступ к сообщениям
4. Включите "Возможности" → "Сообщения" → "Разрешить отправку сообщений"
5. Настройте LongPoll для получения событий

## Деплой

### Docker

Образ сам собирает фронтенд miniapp. **Порт не зашит в образ** — укажите в Dokploy (или в `docker run`):

| Переменная | Описание |
|------------|----------|
| `PORT` | Порт HTTP (часто выставляет Dokploy автоматически) |
| `MINIAPP_PORT` | То же, если удобнее явное имя (приоритет над `PORT`) |

В Dokploy: **Root Directory** = `new`, **Ports** = тот же номер, что в `PORT` / `MINIAPP_PORT`.

```bash
cd new
docker build -t dgty-vk-bot .
docker run -p 3000:3000 \
  -e PORT=3000 \
  -e VK_TOKEN=ваш_токен \
  -e MONGO_URI=ваш_uri \
  -e MONGO_DB=ras \
  -e MONGO_COLLECTION=sessions \
  -e VK_APP_SECRET=ключ_мини_приложения \
  -e EIOS_ENCRYPTION_KEY=ключ_fernet \
  dgty-vk-bot
```

Проверка: `curl http://localhost:3000/api/health`

## Лицензия

MIT License
