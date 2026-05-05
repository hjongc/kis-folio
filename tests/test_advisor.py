import pytest

from folio.advisor import AdvisorError, extract_chat_content, parse_cards


def test_parse_cards_accepts_plain_json() -> None:
    cards = parse_cards('{"summary":"ok","risks":["r1"],"watchlist":["w1"]}')

    assert cards.summary == "ok"
    assert cards.risks == ["r1"]
    assert cards.watchlist == ["w1"]


def test_parse_cards_extracts_fenced_json() -> None:
    cards = parse_cards(
        """
        ```json
        {"summary":"ok","risks":["r1","r2","r3","r4"],"watchlist":["w1"]}
        ```
        """
    )

    assert cards.summary == "ok"
    assert cards.risks == ["r1", "r2", "r3"]


def test_extract_chat_content_returns_message_content() -> None:
    raw = {"choices": [{"message": {"content": "report"}}], "usage": {"total_tokens": 1}}

    assert extract_chat_content(raw, "openrouter") == "report"


def test_extract_chat_content_rejects_missing_message() -> None:
    with pytest.raises(AdvisorError, match="omitted chat content"):
        extract_chat_content({"choices": []}, "openrouter")


def test_extract_chat_content_rejects_empty_content() -> None:
    raw = {"choices": [{"message": {"content": "  "}}]}

    with pytest.raises(AdvisorError, match="content was empty"):
        extract_chat_content(raw, "openrouter")
