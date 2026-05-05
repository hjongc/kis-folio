from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PATTERNS = [
    ("openrouter_key", re.compile(r"sk-or-[A-Za-z0-9_-]{20,}")),
    ("generic_sk_key", re.compile(r"sk-[A-Za-z0-9_-]{24,}")),
    ("kis_app_secret_assignment", re.compile(r"KIS_APP_SECRET_[A-Z0-9_]*=.+")),
    ("kis_app_key_assignment", re.compile(r"KIS_APP_KEY_[A-Z0-9_]*=.+")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("access_token_json", re.compile(r'"access_token"\s*:\s*"[^"]{10,}"')),
]

ALLOWLIST_VALUES = {
    "sk-your-key",
    "sk-or-your-key",
    "your_kis_app_key",
    "your_kis_app_secret",
}

ALLOWLIST_PATHS = {
    ".env.example",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def is_allowed(path: Path, line: str) -> bool:
    if any(value in line for value in ALLOWLIST_VALUES):
        return True
    if str(path) in ALLOWLIST_PATHS:
        return True
    if "redact(" in line or "PLACEHOLDER" in line:
        return True
    return False


def scan_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[str] = []
    for number, line in enumerate(content.splitlines(), start=1):
        if is_allowed(path, line):
            continue
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{number}: {name}")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        findings.extend(scan_file(path))
    if findings:
        print("Potential secrets found in tracked files:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("secret audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
