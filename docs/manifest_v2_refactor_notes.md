# Manifest v2 architecture refactor

Этот overlay переводит текущую Ию с «бота с большим промптом» на первый инженерный срез manifest v2:

- салиентная память `memory_facts` поверх старых `pinned_memories`;
- `memory_snapshots` перед destructive reflection;
- команды `/memory`, `/summary`, `/forget`, `/memory_backup`, `/whoami_to_you`;
- `self_state` и `relationship_state` с deterministic update rules;
- `ModeRouter` как rule-based v1, который выдаёт профиль + modulation vector;
- `PromptBuilder` с persona anchor и приблизительным token budget;
- `LLMRouter` и таблица `llm_requests` для latency/status logging;
- idempotency-поля `dedup_key` и `fired_at` для `proactive_events`;
- vision fallback через `VISION_ENABLED`.

## Что сознательно не сделано в этом PR

Не добавлены RAG, pgvector, voice, полноценный motivated proactive scoring, automatic fact extractor и golden-dialog eval runner. Это следующий слой. Цель этого прохода — безопасный фундамент: память, состояние, маршрутизация, сборка промпта и диагностика.

## Как применить

Из корня локального репозитория:

```bash
# 1. Сначала новая ветка
git checkout -b manifest-v2-core

# 2. Распаковать overlay поверх репозитория
unzip iya_manifest_v2_refactor_overlay.zip -d .

# 3. Добавить переменные из .env.example.manifest_v2_additions в свой .env
nvim .env

# 4. Прогнать тесты/миграции локально или на VPS
PYTHONPATH=src pytest -q

docker compose up -d --build
docker compose logs -f app
```

После старта приложение выполнит:

```bash
alembic upgrade head
```

и применит `0002_manifest_v2_core`.

## Проверка после деплоя

В Telegram от owner:

```text
/health
/settings
/memory
/summary
/whoami_to_you
/memory_backup
```

В БД:

```bash
docker compose exec postgres psql -U iya -d iya -c "\dt"
docker compose exec postgres psql -U iya -d iya -c "select kind,status,count(*) from llm_requests group by kind,status;"
```

## Риск

Это архитектурный refactor. Перед деплоем на production VPS сделай backup volume/Postgres:

```bash
docker compose exec postgres pg_dump -U iya -d iya > iya_before_manifest_v2.sql
```

Откат кода: вернуть предыдущий commit. Откат БД после миграции лучше делать через restore dump, а не downgrade, если в таблицах уже появились новые данные.
