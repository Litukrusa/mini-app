# DGTU RASPISANYE BOT

Весь проект (бот VK, Mini App, Docker) в папке **`new/`**.

## Dokploy (быстрый старт)

1. Залейте репозиторий на GitHub.
2. Dokploy → **Compose** → файл **`docker-compose.yml`** в **корне** репозитория  
   *(собирает образ из `./new`)*
3. Переменные из [`new/.env.example`](new/.env.example) → Environment в Dokploy.
4. Домен + HTTPS, порт контейнера = `PORT` (например `3000`).

Подробно: **[new/DOKPLOY.md](new/DOKPLOY.md)**

## Локально

```bash
cd new
cp .env.example .env   # заполните
pip install -r requirements.txt
python main.py
```

Документация: [new/README.md](new/README.md)
