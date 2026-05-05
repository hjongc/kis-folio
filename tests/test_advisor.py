from folio.advisor import parse_cards


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

