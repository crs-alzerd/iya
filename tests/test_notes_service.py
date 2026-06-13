from iya_bot.application.planning.notes_service import NotesService
from iya_bot.domain.enums import NoteRelation
from iya_bot.infrastructure.notes.mock import InMemoryNotesProvider
from planning_fakes import FakeNoteLinkRepo


async def test_search_finds_by_content_substring():
    provider = InMemoryNotesProvider({"daily/2026-06-13.md": "Сегодня пробежка и отчёт"})
    service = NotesService(provider)

    results = await service.search("пробежка")

    assert len(results) == 1
    assert results[0].path == "daily/2026-06-13.md"
    assert results[0].title == "2026-06-13"


async def test_append_creates_then_appends():
    provider = InMemoryNotesProvider()
    service = NotesService(provider)

    await service.append("log.md", "первая строка")
    await service.append("log.md", "вторая строка")

    content = await service.read("log.md")
    assert content == "первая строка\nвторая строка"


async def test_write_plan_note_creates_link():
    provider = InMemoryNotesProvider()
    links = FakeNoteLinkRepo()
    service = NotesService(provider, links)

    link = await service.write_plan_note(7, "plans/launch.md", "# План\n- шаг 1", planning_item_id=42)

    assert await service.read("plans/launch.md") == "# План\n- шаг 1"
    assert link is not None
    assert link.relation == NoteRelation.PLAN
    assert link.planning_item_id == 42
    assert links.list_links and (await links.list_links(7, planning_item_id=42))[0].note_path == "plans/launch.md"


async def test_link_note_without_repo_returns_none():
    service = NotesService(InMemoryNotesProvider())
    assert await service.link_note(1, "note.md") is None


async def test_list_notes_filters_by_folder():
    provider = InMemoryNotesProvider({"a/one.md": "x", "a/two.md": "y", "b/three.md": "z"})
    service = NotesService(provider)

    assert await provider.list_notes("a") == ["a/one.md", "a/two.md"]
