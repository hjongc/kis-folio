from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def external_call(service: str, operation: str) -> Iterator[None]:
    start = time.monotonic()
    print(f"[folio] external_call start service={service} operation={operation}", file=sys.stderr)
    try:
        yield
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        print(
            f"[folio] external_call error service={service} operation={operation} "
            f"elapsed_ms={elapsed_ms} error={exc.__class__.__name__}",
            file=sys.stderr,
        )
        raise
    else:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        print(
            f"[folio] external_call ok service={service} operation={operation} "
            f"elapsed_ms={elapsed_ms}",
            file=sys.stderr,
        )

