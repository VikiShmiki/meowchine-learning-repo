"""Start the localhost demo with a private reviewer key; never print API credentials."""

import argparse
import os
import secrets
from pathlib import Path

import uvicorn
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    if args.env_file:
        load_dotenv(args.env_file)
    else:
        load_dotenv(root / ".env")
    if not os.getenv("SRA_REVIEW_TOKEN"):
        key_file = root / "runtime" / "reviewer-key.txt"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
        os.environ["SRA_REVIEW_TOKEN"] = key_file.read_text(encoding="utf-8").strip()
        if len(os.environ["SRA_REVIEW_TOKEN"]) < 32:
            raise ValueError("Local reviewer key must contain at least 32 characters")
        print(f"Reviewer key is in {key_file}. Keep this file private.")
    # A loopback-only demo, not a production deployment. Do not trust forwarded IPs here.
    uvicorn.run("smart_recycling.api:app", host="127.0.0.1", port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()
