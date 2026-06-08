from iya_bot.application.memory_consolidation import (
    build_consolidation_messages,
    parse_consolidation,
)


def test_parse_consolidation_extracts_summary_and_facts():
    raw = '{"summary": "Обсудили деплой.", "new_facts": ["Работает над ботом Ия", "Живёт в Москве"]}'
    summary, facts = parse_consolidation(raw)
    assert summary == "Обсудили деплой."
    assert facts == ["Работает над ботом Ия", "Живёт в Москве"]


def test_parse_consolidation_handles_fenced_json():
    raw = '```json\n{"summary": "X", "new_facts": ["a"]}\n```'
    summary, facts = parse_consolidation(raw)
    assert summary == "X"
    assert facts == ["a"]


def test_parse_consolidation_dedupes_facts_case_insensitive():
    raw = '{"summary": "S", "new_facts": ["Любит зиму", "любит зиму  ", "Кофе"]}'
    summary, facts = parse_consolidation(raw)
    assert facts == ["Любит зиму", "Кофе"]


def test_parse_consolidation_tolerates_garbage():
    assert parse_consolidation("не json вовсе") == ("", [])
    assert parse_consolidation("[1,2,3]") == ("", [])
    assert parse_consolidation('{"new_facts": "не список"}') == ("", [])


def test_parse_consolidation_missing_fields():
    summary, facts = parse_consolidation('{"summary": "только выжимка"}')
    assert summary == "только выжимка"
    assert facts == []


def test_build_consolidation_messages_includes_known_facts():
    messages = build_consolidation_messages(
        previous_summary="старая выжимка",
        existing_facts=["уже известный факт"],
        user_text="привет",
        assistant_text="здравствуй",
    )
    assert messages[0].role == "system"
    user_content = messages[1].content
    assert "уже известный факт" in user_content
    assert "старая выжимка" in user_content
    assert "привет" in user_content and "здравствуй" in user_content
