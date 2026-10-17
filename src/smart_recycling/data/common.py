"""Small shared helpers for pipeline stages."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def normalize_whitespace(value: object) -> str:
    return " ".join(str(value).split())


def normalize_key(value: object) -> str:
    text = normalize_whitespace(value).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def stable_id(*parts: object) -> str:
    value = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
