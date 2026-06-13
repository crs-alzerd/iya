from __future__ import annotations

from iya_bot.application.ports import NotesProvider, NoteLinkRepository
from iya_bot.domain.enums import NoteRelation
from iya_bot.domain.models import NoteLink, NoteRef


class NotesService:
    """Чтение/поиск/запись заметок Obsidian-vault и связывание их с планами.

    NotesProvider абстрагирует доступ к vault (на этом этапе — in-memory mock,
    позже — файловая система примонтированного vault). NoteLinkRepository хранит
    связи «задача/привычка/напоминание ↔ заметка».
    """

    def __init__(self, notes: NotesProvider, links: NoteLinkRepository | None = None) -> None:
        self._notes = notes
        self._links = links

    async def search(self, query: str, limit: int = 10) -> list[NoteRef]:
        return await self._notes.search(query, limit=limit)

    async def read(self, path: str) -> str | None:
        return await self._notes.read_note(path)

    async def write(self, path: str, content: str) -> None:
        await self._notes.write_note(path, content)

    async def append(self, path: str, text: str) -> None:
        await self._notes.append_note(path, text)

    async def link_note(
        self,
        owner_id: int,
        note_path: str,
        *,
        relation: str = NoteRelation.REFERENCE,
        note_title: str | None = None,
        planning_item_id: int | None = None,
        reminder_id: int | None = None,
        habit_id: int | None = None,
    ) -> NoteLink | None:
        """Зафиксировать связь сущности с заметкой. None, если хранилище связей не задано."""
        if self._links is None:
            return None
        return await self._links.add_link(
            NoteLink(
                id=0,
                owner_id=owner_id,
                note_path=note_path,
                relation=relation,
                note_title=note_title,
                planning_item_id=planning_item_id,
                reminder_id=reminder_id,
                habit_id=habit_id,
            )
        )

    async def write_plan_note(
        self,
        owner_id: int,
        path: str,
        content: str,
        *,
        planning_item_id: int | None = None,
    ) -> NoteLink | None:
        """Записать заметку с планом и связать её с задачей (если задана)."""
        await self._notes.write_note(path, content)
        return await self.link_note(
            owner_id,
            path,
            relation=NoteRelation.PLAN,
            planning_item_id=planning_item_id,
        )
