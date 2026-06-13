from __future__ import annotations

from iya_bot.application.ports import NotesProvider
from iya_bot.domain.models import NoteRef


class InMemoryNotesProvider(NotesProvider):
    """Mock-vault в памяти: путь -> текст заметки.

    Замена реального адаптера к примонтированному Obsidian-vault на время
    сборки фундамента. Поиск — простое совпадение подстроки (регистронезависимо)
    по пути и содержимому.
    """

    def __init__(self, notes: dict[str, str] | None = None) -> None:
        self._notes: dict[str, str] = dict(notes or {})

    async def search(self, query: str, limit: int = 10) -> list[NoteRef]:
        needle = query.strip().lower()
        if not needle:
            return []
        results: list[NoteRef] = []
        for path, content in self._notes.items():
            haystack = f"{path}\n{content}".lower()
            position = haystack.find(needle)
            if position == -1:
                continue
            results.append(NoteRef(path=path, title=_title_of(path), snippet=_snippet(content, needle)))
            if len(results) >= limit:
                break
        return results

    async def read_note(self, path: str) -> str | None:
        return self._notes.get(path)

    async def write_note(self, path: str, content: str) -> None:
        self._notes[path] = content

    async def append_note(self, path: str, text: str) -> None:
        existing = self._notes.get(path)
        if existing is None:
            self._notes[path] = text
        else:
            separator = "" if existing.endswith("\n") else "\n"
            self._notes[path] = f"{existing}{separator}{text}"

    async def list_notes(self, folder: str | None = None) -> list[str]:
        if folder is None:
            return sorted(self._notes)
        prefix = folder if folder.endswith("/") else f"{folder}/"
        return sorted(path for path in self._notes if path.startswith(prefix))


def _title_of(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return name[:-3] if name.endswith(".md") else name


def _snippet(content: str, needle: str, *, width: int = 80) -> str:
    position = content.lower().find(needle)
    if position == -1:
        return content[:width].strip()
    start = max(0, position - width // 2)
    return content[start : start + width].strip()
