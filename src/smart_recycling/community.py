"""Persistent, bounded community reports and provider request allowances.

The source dataset stays immutable. Pending reports can only affect their reporter;
reviewed reports expire and never turn a source-closed asset into an available one.
"""

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path


class AllowanceExceeded(Exception):
    pass


class CommunityStore:
    def __init__(self, path: Path):
        self.path = path
        self._schema_lock = threading.Lock()
        self._initialized_paths: set[Path] = set()

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("PRAGMA foreign_keys=ON")
            self._initialize(db)
            # Read-only connections should not acquire the SQLite writer lock.
            # Preserve deletion-on-access semantics, but write only when rows expired.
            expired = db.execute(
                "SELECT EXISTS(SELECT 1 FROM reports WHERE created < ?) OR "
                "EXISTS(SELECT 1 FROM usage WHERE expires < ?) OR "
                "EXISTS(SELECT 1 FROM sessions WHERE expires < ?)",
                (time.time() - 30 * 86400, time.time(), time.time()),
            ).fetchone()[0]
            if expired:
                db.execute("DELETE FROM reports WHERE created < ?", (time.time() - 30 * 86400,))
                db.execute("DELETE FROM usage WHERE expires < ?", (time.time(),))
                db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
                db.commit()
            yield db
            db.commit()
        finally:
            db.close()

    def _initialize(self, db):
        path = self.path.resolve()
        with self._schema_lock:
            if path in self._initialized_paths:
                return
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, asset_id TEXT,
                    condition TEXT, latitude REAL, longitude REAL, description TEXT NOT NULL,
                    client TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending', reviewed REAL, photo BLOB
                );
                CREATE INDEX IF NOT EXISTS report_asset ON reports(asset_id, created);
                CREATE TABLE IF NOT EXISTS usage (
                    bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL
                    REFERENCES accounts(id) ON DELETE CASCADE, expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dropoffs (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL
                    REFERENCES accounts(id) ON DELETE CASCADE,
                    materials TEXT NOT NULL, created REAL NOT NULL, recycling INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS dropoffs_user ON dropoffs(user_id, created);
            """)
            db.execute("INSERT OR IGNORE INTO meta VALUES ('secret', ?)", (secrets.token_hex(32),))
            db.commit()
            self._initialized_paths.add(path)

    def client_key(self, peer: str) -> str:
        with self.connection() as db:
            secret = db.execute("SELECT value FROM meta WHERE key='secret'").fetchone()[0]
        # A daily rotating pseudonym, not a stored IP address or location history.
        message = f"{int(time.time() // 86400)}:{peer}"
        return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def visitor(self, cookie: str) -> tuple[str, str]:
        with self.connection() as db:
            secret = db.execute("SELECT value FROM meta WHERE key='secret'").fetchone()[0]
        identifier, _, signature = cookie.partition(".")

        def sign(value):
            return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()

        if len(identifier) != 32 or not secrets.compare_digest(
            sign(identifier).encode(), signature.encode()
        ):
            identifier = secrets.token_hex(16)
        return sign("visitor:" + identifier), identifier + "." + sign(identifier)

    def reserve(self, service: str, client: str, daily: int, per_client: int, hourly: int):
        now = time.time()
        day, hour = int(now // 86400), int(now // 3600)
        buckets = [
            (f"{service}:day:{day}", daily, (day + 1) * 86400),
            (f"{service}:client:{client}:{day}", per_client, (day + 1) * 86400),
            (f"{service}:hour:{client}:{hour}", hourly, (hour + 1) * 3600),
        ]
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for key, limit, _ in buckets:
                row = db.execute("SELECT count FROM usage WHERE bucket=?", (key,)).fetchone()
                if limit <= 0 or (row and row[0] >= limit):
                    raise AllowanceExceeded
            for key, _, expiry in buckets:
                db.execute(
                    """INSERT INTO usage VALUES (?,1,?) ON CONFLICT(bucket)
                              DO UPDATE SET count=count+1""",
                    (key, expiry),
                )

    def submit(self, kind: str, client: str, **fields) -> dict:
        now = time.time()
        ttl = {"full": 12, "inaccessible": 24, "damaged": 72, "available": 12}
        expires = now + (ttl.get(fields.get("condition"), 30 * 24) * 3600)
        identifier = secrets.token_hex(16)
        description = fields.get("description", "").strip()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            # Repeat submissions from the same browser/network are idempotent for five minutes.
            existing = db.execute(
                """SELECT * FROM reports WHERE client=? AND kind=?
                AND COALESCE(asset_id,'')=? AND COALESCE(condition,'')=?
                AND description=? AND COALESCE(latitude,0)=? AND COALESCE(longitude,0)=?
                AND created>? AND state='pending' ORDER BY created DESC LIMIT 1""",
                (
                    client,
                    kind,
                    fields.get("asset_id", ""),
                    fields.get("condition", ""),
                    description,
                    fields.get("latitude", 0),
                    fields.get("longitude", 0),
                    now - 300,
                ),
            ).fetchone()
            if existing:
                return self.public(existing)
            db.execute(
                """INSERT INTO reports
                (id,kind,asset_id,condition,latitude,longitude,description,client,created,expires)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    identifier,
                    kind,
                    fields.get("asset_id"),
                    fields.get("condition"),
                    fields.get("latitude"),
                    fields.get("longitude"),
                    description,
                    client,
                    now,
                    expires,
                ),
            )
            return self.public(
                db.execute("SELECT * FROM reports WHERE id=?", (identifier,)).fetchone()
            )

    @staticmethod
    def public(row) -> dict:
        return {
            k: row[k]
            for k in (
                "id",
                "kind",
                "asset_id",
                "condition",
                "latitude",
                "longitude",
                "description",
                "created",
                "expires",
                "state",
            )
        }

    def reports(self, review=False) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                """SELECT * FROM reports WHERE expires>? AND
                (? OR (kind='dumping' AND state IN ('approved','cleared')))
                ORDER BY created DESC LIMIT 500""",
                (time.time(), review),
            ).fetchall()
            return [dict(self.public(row), has_photo=bool(row["photo"])) for row in rows]

    def moderate(self, identifier: str, state: str) -> bool:
        with self.connection() as db:
            row = db.execute("SELECT * FROM reports WHERE id=?", (identifier,)).fetchone()
            if not row or (state == "cleared" and row["kind"] != "dumping"):
                return False
            db.execute(
                "UPDATE reports SET state=?, reviewed=? WHERE id=?",
                (state, time.time(), identifier),
            )
            return True

    def attach_photo(self, identifier: str, client: str, photo: bytes) -> bool:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            total = db.execute("SELECT COALESCE(SUM(length(photo)),0) FROM reports").fetchone()[0]
            if total + len(photo) > 64 * 1024 * 1024:
                raise AllowanceExceeded
            result = db.execute(
                """UPDATE reports SET photo=? WHERE id=? AND client=?
                AND kind='dumping' AND state='pending' AND created>?""",
                (photo, identifier, client, time.time() - 3600),
            )
            return bool(result.rowcount)

    def photo(self, identifier: str) -> bytes | None:
        with self.connection() as db:
            row = db.execute("SELECT photo FROM reports WHERE id=?", (identifier,)).fetchone()
            return row[0] if row else None

    def statuses(self, client: str = "") -> tuple[dict, str]:
        with self.connection() as db:
            rows = db.execute(
                """SELECT * FROM reports WHERE kind='container' AND expires>?
                AND (state='approved' OR (state='pending' AND client=?))
                ORDER BY created,id""",
                (time.time(), client),
            ).fetchall()
        accepted, personal = {}, {}
        for row in rows:
            value = {
                "condition": row["condition"],
                "reported_at": row["created"],
                "expires": row["expires"],
                "source": "reviewed_community" if row["state"] == "approved" else "your_report",
            }
            (accepted if row["state"] == "approved" else personal)[row["asset_id"]] = value
        for asset_id, value in personal.items():
            # Personal positive reports cannot reopen a globally reported problem.
            if (
                value["condition"] != "available"
                and value["reported_at"] > accepted.get(asset_id, {"reported_at": 0})["reported_at"]
            ):
                accepted[asset_id] = value
        version = hashlib.sha256(json.dumps(accepted, sort_keys=True).encode()).hexdigest()[:16]
        return accepted, version
