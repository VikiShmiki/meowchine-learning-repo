"""Validate the deterministic site seed without starting the API."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smart_recycling.repository import load_sites  # noqa: E402


def main() -> None:
    path = ROOT / "data" / "seed" / "sites.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        raise ValueError("checked-in seed must be explicitly marked synthetic")
    sites = load_sites(path)
    print(f"valid synthetic seed: {len(sites)} sites")


if __name__ == "__main__":
    main()
