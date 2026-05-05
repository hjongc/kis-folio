from pathlib import Path

FORBIDDEN_SNIPPETS = [
    "order-cash",
    "order-credit",
    "order-rsvn",
    "order-modify",
    "overseas-stock",
]


def test_forbidden_kis_endpoints_are_not_used() -> None:
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(path.read_text(encoding="utf-8") for path in (root / "src").rglob("*.py"))

    for snippet in FORBIDDEN_SNIPPETS:
        assert snippet not in source

