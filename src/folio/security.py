from __future__ import annotations

import os
from pathlib import Path


def ensure_private_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600)
    os.chmod(path, 0o600)


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)

