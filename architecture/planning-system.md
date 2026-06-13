# Planning-система Ии: Obsidian + календарь + планы и привычки

## Цель

Дать Ие способность работать как личный координатор владельца:

- держать в контексте Obsidian-vault, календарь и общие планы;
- планировать расписание (раскладывать задачи по свободным слотам календаря);
- напоминать о привычках и вести их серии (streak);
- координировать многошаговые действия.

Развёртывание — VPS, LLM — nanogpt (OpenAI-совместимый, уже поддержан существующим LLM-слоем).

## Принцип: ports & adapters, реальные интеграции — за портами

Подсистема построена так, чтобы **бизнес-логика не зависела от конкретных внешних
сервисов**. Доступ к календарю, vault, движку координации, доставке и LLM описан
портами (`application/ports.py`). На этом этапе подключены **mock-адаптеры**;
реальные провайдеры (CalDAV/Google/Obsidian-ФС/aiogram/nanogpt) добавляются позже
без изменения сервисов и тестов.

```
Telegram / scheduler (ПОКА НЕ ПОДКЛЮЧЕНО — следующий шаг)
        │
        ▼
application/planning/  ──►  PlanningService (оркестратор)
   ├─ CalendarService          │
   ├─ ReminderService          ├─ зависит только от портов и domain-моделей
   ├─ NotesService             │
   └─ (compute_streak, assign_slots — чистые функции)
        │
        ▼  ports (ABC)
CalendarProvider · NotesProvider · WorkflowEngine · NotificationProvider · ModelProvider
   + PlanningRepository · ReminderRepository · HabitRepository · CalendarRepository · NoteLinkRepository
        │
        ▼  adapters
[mock]  InMemoryCalendarProvider · InMemoryNotesProvider · DeterministicWorkflowEngine ·
        CollectingNotificationProvider · CannedModelProvider
[db]    SqlAlchemy*Repository (Postgres, миграция 0004)
[real]  CalDAV/Google/ICS · Obsidian-FS · aiogram · nanogpt   ← ПРЕДСТОИТ
```

## Доменные сущности (`domain/models.py`)

| Модель | Назначение |
|---|---|
| `PlanningItem` | Задача/подзадача (`parent_id` — дерево декомпозиции), `scheduled_for`/`due_at`. |
| `Reminder` | Напоминание; `kind` ∈ one_off/recurring/habit_nudge, `recurrence_rule`, `habit_id`. |
| `Habit` | Привычка: `cadence`, `schedule_time`, `target_per_period`, `current_streak`. |
| `HabitCompletion` | Факт выполнения привычки — источник истины для streak. |
| `CalendarEvent` | Событие; `external_id` у провайдера, `binding_id` — к какому календарю. |
| `CalendarBinding` | Подключённый календарь; `credentials_ref` — ссылка на секрет, не пароль. |
| `NoteLink` | Связь задачи/привычки/напоминания с заметкой Obsidian по пути. |
| `NoteRef`, `WorkflowStep` | Результаты поиска по vault и шага координации. |

Строковые значения статусов/видов вынесены в `domain/enums.py` и продублированы
CheckConstraint'ами в миграции `0004`, чтобы код и схема не разъезжались.

## Порты (`application/ports.py`)

- **`CalendarProvider`** — `list_events / create_event / update_event / delete_event`.
- **`NotesProvider`** — `search / read_note / write_note / append_note / list_notes`.
- **`WorkflowEngine`** — `plan(goal) -> [WorkflowStep]`, `advance(steps, done_title)`.
- **`NotificationProvider`** — `notify(owner_id, chat_id, text)`.
- **`ModelProvider`** — `generate / structured` (LLM для планирования, отдельно от диалогового `LLMClient`).
- Репозитории: `PlanningRepository`, `ReminderRepository`, `HabitRepository`, `CalendarRepository`, `NoteLinkRepository`.

## Сервисы (`application/planning/`)

- **`CalendarService`** — события через провайдера + кэш в БД; `free_slots()` и `is_busy()` для раскладки.
- **`ReminderService`** — `schedule / cancel / fire_due`; повторения через `next_occurrence()` (daily/weekly/monthly).
- **`NotesService`** — поиск/чтение/запись заметок; `write_plan_note()` связывает план с заметкой (`NoteLink`).
- **`PlanningService`** — оркестратор: цель → `WorkflowEngine.plan` → дерево `PlanningItem`; раскладка по `free_slots` (`assign_slots`); привычки и `compute_streak`; habit-nudge-напоминания; краткое резюме через `ModelProvider`.

Чистые функции `compute_streak()` и `assign_slots()` вынесены отдельно — это ядро
бизнес-логики, протестированное без БД и сети.

## Хранилище

Postgres-таблицы создаёт миграция `migrations/versions/0004_planning_system.py`:
`planning_items`, `habits`, `habit_completions`, `calendar_bindings`,
`calendar_events`, `note_links`; плюс к существующей `reminders` (из `0001`)
добавлены `kind`, `recurrence_rule`, `habit_id`.

## Статус: что замокано и что предстоит подключить

| Контур | Сейчас | Предстоит |
|---|---|---|
| Календарь | `InMemoryCalendarProvider` | CalDAV (универсально), Google API или ICS (RO) |
| Obsidian vault | `InMemoryNotesProvider` | Адаптер к ФС примонтированного vault (RO/RW), путь-безопасность |
| Координация | `DeterministicWorkflowEngine` | Движок поверх `ModelProvider`/nanogpt |
| Доставка | `CollectingNotificationProvider` | Адаптер поверх aiogram `Bot` |
| LLM планировщика | `CannedModelProvider` | Адаптер поверх `LLMRouter` → nanogpt |
| Рантайм | **не подключено** | tools в tool-loop, команды в `handlers.py`, DI в `main.py`, job в APScheduler для `fire_due` |

## Следующий шаг (вне текущего объёма)

1. Реальные адаптеры провайдеров + секреты/credentials в конфиге (`config.py`, `.env`).
2. Монтирование Obsidian-vault в `docker-compose.yml` (volume, RO или RW).
3. DI новых сервисов в `main.py`; APScheduler-job, вызывающий `ReminderService.fire_due()`.
4. Tools (`obsidian_search`, `calendar_*`, `schedule_reminder`, `create_habit`, ...) в tool-loop `DialogueService` и owner-команды в `handlers.py`.
5. Подмешивание агенды (календарь + задачи + привычки) в контекст промпта.

## Тесты

`PYTHONPATH=src pytest -q` — вся бизнес-логика проверяется на mock-провайдерах и
in-memory fake-репозиториях (`tests/planning_fakes.py`), без сети и БД:
`test_planning_service.py`, `test_calendar_service.py`, `test_reminder_service.py`,
`test_notes_service.py`, `test_workflow_engine.py`.
