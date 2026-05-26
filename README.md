# Iya Next Clean

Чистая стартовая версия Ии: Telegram-бот + Postgres + Alembic + OpenAI-compatible LLM API.

Главный принцип этой сборки: сначала устойчивый минимальный контур, потом память, адаптивные режимы, RAG, проактивность и мониторинг.

## Что уже есть

- Telegram polling на `aiogram 3`
- Postgres как основная БД
- Alembic-миграции
- OpenAI-compatible LLM-клиент
- Сохранение пользователей
- Сохранение истории сообщений
- Закреплённая память через `/remember`
- Простые напоминания через `/remind`
- Внешний системный промпт в `prompts/iya_system.md`
- Fallback-промпт внутри Python-пакета
- Базовый owner-mode для диагностических команд
- Docker Compose с явными именами контейнеров, сети и volume

## Структура проекта

```text
.
├── prompts/
│   └── iya_system.md              # внешний системный промпт, удобный для правки на VPS
├── src/iya_bot/
│   ├── application/
│   │   ├── dialogue.py
│   │   ├── prompt_loader.py       # загрузка внешнего промпта + fallback
│   │   └── reminders.py
│   ├── infrastructure/
│   │   ├── db/
│   │   ├── llm/
│   │   ├── scheduler/
│   │   └── telegram/
│   ├── prompts/
│   │   └── iya_system.md          # встроенный fallback-промпт
│   ├── config.py
│   └── main.py
├── migrations/
├── tests/
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Команды бота

```text
/start
/health
/settings      # только владелец
/version       # только владелец
/remember <факт>
/remind 10m <текст>
/remind 2h <текст>
/remind 1d <текст>
```

`/health` для владельца показывает расширенную диагностику. Для остальных пользователей не раскрывает технические детали.

## Системный промпт

Основной файл промпта:

```text
prompts/iya_system.md
```

В Docker Compose эта директория монтируется в контейнер как read-only:

```yaml
volumes:
  - ./prompts:/app/prompts:ro
```

Путь задаётся переменной:

```env
SYSTEM_PROMPT_PATH=/app/prompts/iya_system.md
```

После изменения промпта на VPS достаточно перезапустить контейнер приложения:

```bash
docker compose restart app
```

Пересобирать образ ради правки промпта не нужно. Если внешний файл отсутствует или пустой, приложение попробует загрузить встроенный fallback из `src/iya_bot/prompts/iya_system.md`.

## Быстрый запуск

```bash
cd /opt
unzip iya-next-clean.zip
cd iya-next-clean

cp .env.example .env
nano .env

docker compose up -d --build
docker compose logs -f app
```

Минимально проверь в `.env`:

```env
TELEGRAM_BOT_TOKEN=...
LLM_BASE_URL=...
LLM_API_KEY=...
LLM_MODEL=...
POSTGRES_PASSWORD=...
DATABASE_URL=postgresql+asyncpg://iya:<POSTGRES_PASSWORD>@postgres:5432/iya
OWNER_TELEGRAM_ID=<твой telegram id>
SYSTEM_PROMPT_PATH=/app/prompts/iya_system.md
```

## Проверка БД

```bash
docker compose exec postgres psql -U iya -d iya -c "\dt"
```

## Проверка Telegram token

```bash
set -a
source .env
set +a

curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
echo
```

## Логи

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f postgres
```

## Сброс только этого проекта

```bash
docker compose down -v --remove-orphans
docker image rm iya-next-clean-app:latest 2>/dev/null || true
```

## Локальные тесты

```bash
PYTHONPATH=src pytest -q
```

## Архитектура

```text
Telegram adapter
    ↓
Application services
    ↓
Ports
    ↓
Repositories / LLM client / Scheduler
    ↓
Postgres
```

Это модульный монолит. Его можно развивать без раннего микросервисного усложнения.

## Что сделано в текущем проходе

- Системный промпт вынесен в `prompts/iya_system.md`.
- Добавлен `SYSTEM_PROMPT_PATH`.
- Добавлен безопасный loader системного промпта.
- Добавлена встроенная fallback-копия промпта.
- Добавлены `OWNER_TELEGRAM_ID`, `APP_ENV`, `APP_VERSION`, `BOT_TIMEZONE`.
- Добавлены owner-only команды `/settings` и `/version`.
- Расширен `/health`.
- Добавлены тесты загрузки промпта и owner/config-логики.
