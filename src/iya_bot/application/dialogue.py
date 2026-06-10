from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from iya_bot.application.memory_consolidation import (
    build_consolidation_messages,
    build_summary_messages,
    normalize,
    parse_consolidation,
)
from iya_bot.application.memory_retrieval import MemoryRetrievalService
from iya_bot.application.mode_router import ModeRouter
from iya_bot.application.ports import LLMClient, MemoryRepository, MessageRepository, UserRepository
from iya_bot.application.prompt_builder import PromptBuilder
from iya_bot.application.prompt_loader import load_system_prompt
from iya_bot.application.runtime_context import build_runtime_context, current_time_in
from iya_bot.application.self_state import SelfStateService
from iya_bot.application.tools import ToolContext, ToolRegistry
from iya_bot.domain.enums import LLMRequestKind, RouteProfile
from iya_bot.domain.models import ChatMessage, DialogueResult, MemoryItem, RoutingDecision

logger = logging.getLogger(__name__)

# Колбэк прогресса стриминга: получает накопленный текст ответа целиком.
ProgressCallback = Callable[[str], Awaitable[None]]


class _UserLock:
    """asyncio.Lock + счётчик пользователей лока, чтобы безопасно чистить словарь."""

    __slots__ = ("lock", "refs")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.refs = 0

# Профили, в которых ответ должен быть одним цельным сообщением. Всё личное,
# атмосферное, кризисное и техническое не дробится. Дробить можно только лёгкую
# бытовую болтовню (DEFAULT).
_SINGLE_MESSAGE_PROFILES = {
    RouteProfile.RP,
    RouteProfile.CRISIS,
    RouteProfile.SUPPORT,
    RouteProfile.PERSONAL,
    RouteProfile.TECHNICAL,
    RouteProfile.RESEARCH,
    RouteProfile.ADMIN,
    RouteProfile.REMINDER,
    RouteProfile.IMAGE,
}


def _max_messages_for(profile: str) -> int:
    return 2 if profile == RouteProfile.DEFAULT else 1


class DialogueService:
    def __init__(
        self,
        users: UserRepository,
        messages: MessageRepository,
        memories: MemoryRepository,
        llm: LLMClient,
        history_limit: int,
        system_prompt_path: str | None = None,
        runtime_context_enabled: bool = True,
        timezone_name: str = "Europe/Moscow",
        mode_router: ModeRouter | None = None,
        self_state: SelfStateService | None = None,
        prompt_token_budget: int = 12_000,
        prompt_builder_v2_enabled: bool = True,
        tools: ToolRegistry | None = None,
        tool_max_iterations: int = 4,
        auto_memory_enabled: bool = False,
        auto_memory_max_facts: int = 5,
        memory_retrieval: MemoryRetrievalService | None = None,
    ) -> None:
        self._users = users
        self._messages = messages
        self._memories = memories
        self._llm = llm
        self._history_limit = history_limit
        self._system_prompt = load_system_prompt(system_prompt_path)
        self._runtime_context_enabled = runtime_context_enabled
        self._timezone_name = timezone_name
        self._mode_router = mode_router or ModeRouter()
        self._self_state = self_state
        self._prompt_builder_v2_enabled = prompt_builder_v2_enabled
        self._tools = tools
        self._tool_max_iterations = max(1, tool_max_iterations)
        self._auto_memory_enabled = auto_memory_enabled
        self._auto_memory_max_facts = auto_memory_max_facts
        self._memory_retrieval = memory_retrieval
        self._prompt_builder = PromptBuilder(
            self._system_prompt,
            timezone_name=timezone_name,
            token_budget=prompt_token_budget,
            runtime_context_enabled=runtime_context_enabled,
        )
        self._background_tasks: set[asyncio.Task[None]] = set()
        # Параллельные сообщения одного пользователя сериализуем: иначе два хода
        # читают одну историю/выжимку и пишут ответы вперемешку.
        self._user_locks: dict[int, _UserLock] = {}

    async def register_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        await self._users.upsert_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

    async def remember(self, telegram_user_id: int, content: str) -> None:
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("Нельзя сохранить пустую память.")
        await self._memories.add_memory(telegram_user_id, cleaned)

    async def answer(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        text: str,
        image_data_url: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> DialogueResult:
        # Refcount нужен, чтобы убрать лок из словаря только когда никто не ждёт:
        # простой "if not locked" гоняется с ожидающим, который ещё не проснулся.
        entry = self._user_locks.get(telegram_user_id)
        if entry is None:
            entry = _UserLock()
            self._user_locks[telegram_user_id] = entry
        entry.refs += 1
        try:
            async with entry.lock:
                return await self._answer_locked(
                    telegram_user_id=telegram_user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    text=text,
                    image_data_url=image_data_url,
                    progress=progress,
                )
        finally:
            entry.refs -= 1
            if entry.refs == 0 and self._user_locks.get(telegram_user_id) is entry:
                del self._user_locks[telegram_user_id]

    async def _answer_locked(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        text: str,
        image_data_url: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> DialogueResult:
        await self.register_user(
            telegram_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

        self_state = await self._self_state.get_state(telegram_user_id) if self._self_state else None
        relationship = await self._self_state.get_relationship(telegram_user_id) if self._self_state else None
        routing = self._mode_router.route(
            text,
            has_image=image_data_url is not None,
            self_state=self_state,
            relationship=relationship,
        )

        stored_user_text = text
        if image_data_url is not None:
            stored_user_text = f"{text}\n[Пользователь отправил изображение.]".strip()

        await self._messages.add_message(telegram_user_id, "user", stored_user_text)

        recent = await self._messages.get_recent_messages(
            telegram_user_id=telegram_user_id,
            limit=self._history_limit,
        )
        # Память грузим один раз. Салиентные факты — основной источник; на legacy
        # pinned-память откатываемся, только если фактов нет (или v2 выключен).
        memory_facts = await self._safe_memory_facts(telegram_user_id)
        if self._memory_retrieval is not None and memory_facts:
            memory_facts = await self._memory_retrieval.select_relevant(text, memory_facts)
        if memory_facts and self._prompt_builder_v2_enabled:
            memories: list[str] = []
        else:
            memories = await self._memories.get_memories(telegram_user_id=telegram_user_id)
        summary = await self._memories.get_conversation_summary(telegram_user_id=telegram_user_id)

        prompt_messages = self._build_prompt_messages(
            routing=routing,
            self_state=self_state,
            relationship=relationship,
            memories=memories,
            memory_facts=memory_facts,
            conversation_summary=summary,
            recent=recent,
        )
        if image_data_url is not None:
            prompt_messages = self._with_current_image(
                prompt_messages=prompt_messages,
                user_text=text,
                image_data_url=image_data_url,
            )
        response = await self._generate(
            prompt_messages=prompt_messages,
            has_image=image_data_url is not None,
            telegram_user_id=telegram_user_id,
            progress=progress,
        )

        await self._messages.add_message(telegram_user_id, "assistant", response)
        if self._self_state is not None:
            await self._self_state.update_after_turn(
                telegram_user_id,
                routing,
                now=current_time_in(self._timezone_name),
            )
        # Консолидация долговременной памяти — единственный фоновый LLM-вызов на ход.
        # Он обновляет выжимку и (если включена авто-память) тем же запросом извлекает
        # новые факты, чтобы не плодить два round-trip'а с одинаковым контекстом.
        self._spawn(
            self._consolidate_and_backfill(
                telegram_user_id=telegram_user_id,
                previous_summary=summary,
                memory_facts=memory_facts,
                user_text=stored_user_text,
                assistant_text=response,
            )
        )
        return DialogueResult(text=response, max_messages=_max_messages_for(routing.profile))

    async def _generate(
        self,
        *,
        prompt_messages: list[ChatMessage],
        has_image: bool,
        telegram_user_id: int,
        progress: ProgressCallback | None = None,
    ) -> str:
        # Vision-запросы и режим без инструментов идут прямым одиночным вызовом.
        if has_image or not self._tools:
            kind = LLMRequestKind.VISION if has_image else LLMRequestKind.DIALOGUE
            if progress is not None and not has_image:
                streamed = await self._stream_with_progress(
                    prompt_messages, telegram_user_id=telegram_user_id, progress=progress
                )
                if streamed:
                    return streamed
            return await self._llm.complete(prompt_messages, kind=kind, telegram_user_id=telegram_user_id)
        return await self._run_tool_loop(prompt_messages, telegram_user_id=telegram_user_id)

    async def _stream_with_progress(
        self,
        prompt_messages: list[ChatMessage],
        *,
        telegram_user_id: int,
        progress: ProgressCallback,
    ) -> str | None:
        """Стримим ответ и сообщаем прогресс. Пустой поток или сбой колбэка не роняют ход."""
        parts: list[str] = []
        async for delta in self._llm.complete_stream(
            prompt_messages, kind=LLMRequestKind.DIALOGUE, telegram_user_id=telegram_user_id
        ):
            parts.append(delta)
            try:
                await progress("".join(parts))
            except Exception:
                logger.debug("Streaming progress callback failed", exc_info=True)
        text = "".join(parts).strip()
        return text or None

    async def _run_tool_loop(self, prompt_messages: list[ChatMessage], *, telegram_user_id: int) -> str:
        assert self._tools is not None
        working = list(prompt_messages)
        specs = self._tools.specs()
        ctx = ToolContext(telegram_user_id=telegram_user_id)
        last_content: str | None = None
        for _ in range(self._tool_max_iterations):
            result = await self._llm.complete_tools(
                working,
                tools=specs,
                kind=LLMRequestKind.DIALOGUE,
                telegram_user_id=telegram_user_id,
            )
            last_content = result.content
            if not result.tool_calls:
                if result.content:
                    return result.content
                break
            working.append(
                ChatMessage(role="assistant", content=result.content, tool_calls=result.tool_calls)
            )
            for call in result.tool_calls:
                tool_result = await self._tools.run(call.name, call.arguments, ctx)
                working.append(
                    ChatMessage(role="tool", content=tool_result, tool_call_id=call.id, name=call.name)
                )
        # Итерации исчерпаны (или пустой ответ) — финальный ход без инструментов.
        if last_content:
            return last_content
        final = await self._llm.complete(working, kind=LLMRequestKind.DIALOGUE, telegram_user_id=telegram_user_id)
        return final

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def drain_background_tasks(self) -> None:
        """Дождаться фоновых задач (выжимка). Используется в тестах и при остановке."""
        if self._background_tasks:
            await asyncio.gather(*list(self._background_tasks), return_exceptions=True)

    async def _safe_memory_facts(self, telegram_user_id: int) -> list[MemoryItem]:
        # С семантическим поиском берём широкий пул и ранжируем по релевантности;
        # без него — узкий, отсортированный по salience.
        limit = 200 if self._memory_retrieval is not None else 50
        try:
            return await self._memories.list_memory_items(telegram_user_id, include_archived=False, limit=limit)
        except Exception:
            logger.debug("Failed to load memory_facts; falling back to pinned memories", exc_info=True)
            return []

    def _with_current_image(
        self,
        prompt_messages: list[ChatMessage],
        user_text: str,
        image_data_url: str,
    ) -> list[ChatMessage]:
        if not prompt_messages:
            return prompt_messages

        content = [
            {
                "type": "text",
                "text": user_text.strip() or "Опиши изображение и ответь на него по контексту диалога.",
            },
            {
                "type": "image_url",
                "image_url": {"url": image_data_url},
            },
        ]
        updated = list(prompt_messages)
        updated[-1] = ChatMessage(role="user", content=content)
        return updated

    def _build_prompt_messages(
        self,
        *,
        routing: RoutingDecision,
        self_state: object | None,
        relationship: object | None,
        memories: list[str],
        memory_facts: list[MemoryItem],
        conversation_summary: str | None,
        recent: list[ChatMessage],
    ) -> list[ChatMessage]:
        if self._prompt_builder_v2_enabled:
            return self._prompt_builder.build(
                routing=routing,
                self_state=self_state,  # type: ignore[arg-type]
                relationship=relationship,  # type: ignore[arg-type]
                memories=memories,
                memory_facts=memory_facts,
                conversation_summary=conversation_summary,
                recent=recent,
            )

        blocks = [self._system_prompt]
        if memories:
            memory_block = "\n".join(f"- {item}" for item in memories)
            blocks.append(
                "Закреплённая память о пользователе и проекте. Используй её только когда она действительно релевантна:\n"
                f"{memory_block}"
            )
        if conversation_summary:
            blocks.append(
                "Краткая выжимка предыдущего диалога из базы данных. Учитывай её как долговременный контекст, но не пересказывай пользователю без нужды:\n"
                f"{conversation_summary}"
            )
        messages: list[ChatMessage] = [ChatMessage(role="system", content="\n\n".join(blocks))]
        runtime = self._runtime_context_message()
        if runtime is not None:
            messages.append(runtime)
        messages.extend(recent)
        return messages

    def _runtime_context_message(self) -> ChatMessage | None:
        if not self._runtime_context_enabled:
            return None
        now = current_time_in(self._timezone_name)
        content = build_runtime_context(now=now, timezone_name=self._timezone_name, include_time=now is not None)
        return ChatMessage(role="system", content=content)

    async def _consolidate_and_backfill(
        self,
        telegram_user_id: int,
        previous_summary: str | None,
        memory_facts: list[MemoryItem],
        user_text: str,
        assistant_text: str,
    ) -> None:
        try:
            await self._consolidate_memory(
                telegram_user_id=telegram_user_id,
                previous_summary=previous_summary,
                memory_facts=memory_facts,
                user_text=user_text,
                assistant_text=assistant_text,
            )
        finally:
            # Эмбеддинги добиваем после консолидации: накрывает и свежеизвлечённые
            # факты, и закреплённые вручную через /remember или remember_fact.
            if self._memory_retrieval is not None:
                try:
                    await self._memory_retrieval.backfill(telegram_user_id)
                except Exception:
                    logger.exception("Embedding backfill failed for telegram_user_id=%s", telegram_user_id)

    async def _consolidate_memory(
        self,
        telegram_user_id: int,
        previous_summary: str | None,
        memory_facts: list[MemoryItem],
        user_text: str,
        assistant_text: str,
    ) -> None:
        if not self._auto_memory_enabled:
            await self._update_summary_only(telegram_user_id, previous_summary, user_text, assistant_text)
            return

        existing_texts = [item.text for item in memory_facts if item.status == "active"]
        messages = build_consolidation_messages(
            previous_summary=previous_summary,
            existing_facts=existing_texts,
            user_text=user_text,
            assistant_text=assistant_text,
        )
        try:
            raw = await self._llm.complete(
                messages, kind=LLMRequestKind.MEMORY, telegram_user_id=telegram_user_id
            )
        except Exception:
            logger.exception("Memory consolidation call failed for telegram_user_id=%s", telegram_user_id)
            return

        summary, facts = parse_consolidation(raw)
        if summary:
            try:
                await self._memories.upsert_conversation_summary(telegram_user_id, summary)
            except Exception:
                logger.exception("Failed to upsert summary for telegram_user_id=%s", telegram_user_id)

        existing_norm = {normalize(text) for text in existing_texts}
        stored = 0
        for fact in facts:
            if stored >= self._auto_memory_max_facts:
                break
            key = normalize(fact)
            if not key or key in existing_norm:
                continue
            existing_norm.add(key)
            try:
                await self._memories.add_extracted_fact(telegram_user_id, fact)
                stored += 1
            except Exception:
                logger.exception("Failed to store extracted fact for telegram_user_id=%s", telegram_user_id)
        if stored:
            logger.info("Auto-memory stored %s new fact(s) for telegram_user_id=%s", stored, telegram_user_id)

    async def _update_summary_only(
        self,
        telegram_user_id: int,
        previous_summary: str | None,
        user_text: str,
        assistant_text: str,
    ) -> None:
        messages = build_summary_messages(previous_summary, user_text, assistant_text)
        try:
            updated_summary = await self._llm.complete(
                messages, kind=LLMRequestKind.SUMMARY, telegram_user_id=telegram_user_id
            )
            cleaned = updated_summary.strip()
            if cleaned:
                await self._memories.upsert_conversation_summary(telegram_user_id, cleaned)
        except Exception:
            logger.exception("Failed to update conversation summary for telegram_user_id=%s", telegram_user_id)
