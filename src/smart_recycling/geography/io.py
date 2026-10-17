"""Verified downloads and deterministic, portable artifact serialization."""

import gzip
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    """Hash a file without loading a national extract into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(url: str, destination: Path, expected_sha256: str) -> None:
    """Download with bounded retries; never accept changed or partially fetched inputs."""
    if destination.exists():
        if sha256(destination) != expected_sha256:
            raise ValueError(f"Checksum mismatch: {destination}; restore the pinned source")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "SmartRecyclingAccess-data/1.0"}
            )
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                temporary.open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
            if sha256(temporary) != expected_sha256:
                raise ValueError(f"Downloaded checksum mismatch for {url}; source may have changed")
            temporary.replace(destination)
            return
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
        finally:
            temporary.unlink(missing_ok=True)


def write_json(path: Path, value: Any) -> None:
    """Write stable UTF-8 JSON, using timestamp-free gzip when requested."""
    payload = (
        json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode()
    if path.suffix == ".gz":
        payload = gzip.compress(payload, mtime=0)
    path.write_bytes(payload)


def read_json(path: Path) -> Any:
    """Read a plain or gzip JSON artifact."""
    payload = path.read_bytes()
    if path.suffix == ".gz":
        payload = gzip.decompress(payload)
    return json.loads(payload)
