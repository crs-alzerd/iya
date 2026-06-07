# Как применить refactor overlay

Положи `iya_manifest_v2_refactor_overlay.zip` рядом с локальной копией репозитория `iya`.

```bash
cd ~/path/to/iya

git status
git checkout -b manifest-v2-core

# распаковать overlay поверх текущего репозитория
unzip /path/to/iya_manifest_v2_refactor_overlay.zip -d .

# перенести переменные из .env.example.manifest_v2_additions в настоящий .env
nvim .env

# проверить синтаксис и тесты
PYTHONPATH=src pytest -q

# локально / на VPS
docker compose up -d --build
docker compose logs -f app
```

## Перед VPS deploy

```bash
docker compose exec postgres pg_dump -U iya -d iya > iya_before_manifest_v2.sql
```

## Что должно появиться после старта

```text
memory_facts
memory_snapshots
self_state
self_memories
relationship_state
llm_requests
mode_events
```

## Telegram owner checks

```text
/health
/settings
/memory
/summary
/whoami_to_you
/memory_backup
```
