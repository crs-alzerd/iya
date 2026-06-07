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
- Долговременная выжимка диалога в `conversation_summaries`
- Рефлексия памяти: периодическая очистка закреплённой памяти и выжимки
- Простые напоминания через `/remind`
- Спонтанные сообщения через планировщик `proactive_events`
- Обработка изображений в Telegram-чате через мультимодальный LLM-запрос
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
/reflect       # только владелец
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

## Память

В запрос к LLM отправляются:

- системный промпт;
- закреплённая память из `pinned_memories`;
- краткая выжимка предыдущего диалога из `conversation_summaries`;
- последние сообщения из `messages` в пределах `HISTORY_LIMIT`.

После ответа ассистента сервис обновляет `conversation_summaries`: LLM получает прежнюю выжимку и последний обмен сообщениями, возвращает новую сжатую версию, а репозиторий сохраняет её через upsert. Ошибка обновления выжимки логируется и не ломает отправку уже полученного ответа пользователю.

Периодическая рефлексия включается переменной `REFLECTION_ENABLED=true`. Она просит LLM очистить `pinned_memories` и `conversation_summaries` от дублей, временного шума и устаревших деталей. Владелец может вручную запустить очистку своей памяти командой `/reflect`.

## Спонтанные сообщения

Если `PROACTIVE_ENABLED=true`, после диалога с пользователем Ия планирует одно будущее событие `check_in` в `proactive_events`. Когда событие наступает, scheduler генерирует короткое уместное сообщение по памяти и недавнему контексту, отправляет его в тот же чат и планирует следующее.

Основные переменные:

```env
PROACTIVE_ENABLED=true
PROACTIVE_SCAN_INTERVAL_SECONDS=60
PROACTIVE_MIN_DELAY_MINUTES=180
PROACTIVE_MAX_DELAY_MINUTES=720
REFLECTION_ENABLED=true
REFLECTION_INTERVAL_MINUTES=360
REFLECTION_USER_LIMIT=20
REFLECTION_KEEP_RECENT_MESSAGES=200
TELEGRAM_IMAGE_MAX_BYTES=5000000
```

## Изображения

В Telegram можно отправить фото с подписью или без неё. Бот скачивает крупнейшую версию фото, кодирует её как `data:image/jpeg;base64,...` и отправляет текущий ход в OpenAI-compatible `chat/completions` как multimodal content. В базу сохраняется только текстовый маркер о том, что изображение было отправлено, без base64.

<<<<<<< HEAD
## Что сделано в текущем проходе
=======
## Что сделано в проходе «человечность» (v0.2.0)

Цель прохода — убрать ощущение «ограниченного» бота и зацикливания на одних и тех же фразах и жестах.

- **Анти-повтор на уровне сэмплинга.** В запрос к LLM добавлены `presence_penalty` и `frequency_penalty`, `temperature` поднята до 0.85. Это главная причина, почему раньше бот дословно повторял одни и те же действия. Penalty-параметры опциональны и отправляются только если заданы, чтобы не ломать совместимость с разными бэкендами (включая отдельные модели NanoGPT).
- **Постоянные поведенческие директивы.** В каждый запрос отдельным system-блоком подмешиваются правила: не повторять жесты и формулировки два хода подряд, не долбить один и тот же отказ, варьировать длину, а при неоднозначности — сначала коротко переспрашивать. Эти правила живут в коде (`runtime_context.py`) и работают, даже если переписать внешний промпт.
- **Ощущение времени.** Бот получает реальное время суток и день недели (по `BOT_TIMEZONE`), поэтому «ночная» персона теперь действительно знает, ночь ли сейчас. То же подмешивается в спонтанные сообщения.
- **Человеческая подача в Telegram.** Длинный ответ дробится на 1–3 коротких реплики и отправляется с имитацией набора текста (`typing`-индикатор и небольшие задержки), как пишет живой собеседник. Логика чистая и протестированная (`humanize.py`), отправка — в telegram-слое.
- **Безопасная нарезка по лимиту Telegram (4096).** Раньше очень длинный ответ мог упасть при отправке.

Новые переменные окружения (все с дефолтами, см. `.env.example`):

```env
LLM_TEMPERATURE=0.85
LLM_TOP_P=
LLM_PRESENCE_PENALTY=0.4
LLM_FREQUENCY_PENALTY=0.5
LLM_MAX_TOKENS=
HUMANIZE_ENABLED=true
HUMANIZE_MAX_CHUNKS=3
HUMANIZE_MS_PER_CHAR=22
HUMANIZE_MIN_DELAY_SECONDS=0.6
HUMANIZE_MAX_DELAY_SECONDS=4.0
RUNTIME_CONTEXT_ENABLED=true
```

Схема БД не менялась — новых миграций не требуется. Обновление на VPS:

```bash
docker compose up -d --build
docker compose logs -f app
```

Если какой-то LLM-бэкенд не принимает penalty-параметры, оставь `LLM_PRESENCE_PENALTY=` и `LLM_FREQUENCY_PENALTY=` пустыми — они не будут отправлены.

## Что сделано в первом проходе
>>>>>>> 1917e25 (Rebuilt full)

- Системный промпт вынесен в `prompts/iya_system.md`.
- Добавлен `SYSTEM_PROMPT_PATH`.
- Добавлен безопасный loader системного промпта.
- Добавлена встроенная fallback-копия промпта.
- Добавлены `OWNER_TELEGRAM_ID`, `APP_ENV`, `APP_VERSION`, `BOT_TIMEZONE`.
- Добавлены owner-only команды `/settings` и `/version`.
- Расширен `/health`.
- Добавлены тесты загрузки промпта и owner/config-логики.
