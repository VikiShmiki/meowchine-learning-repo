"""Local-demo accounts and self-reported drop-offs; never store route locations."""

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time

from smart_recycling.community import CommunityStore

SESSION_SECONDS = 7 * 86400
MATERIALS = {
    "glass": "glass",
    "empty_glass_packaging": "glass",
    "plastic_metal": "plastic_metal",
    "empty_plastic_bottle": "plastic_metal",
    "empty_metal_can": "plastic_metal",
    "paper_tetrapak": "paper_tetrapak",
    "clean_paper": "paper_tetrapak",
    "clean_cardboard": "paper_tetrapak",
    "empty_tetrapak": "paper_tetrapak",
    "general": "general",
    "ordinary_residual": "general",
    "electronics": "electronics",
    "small_electronics": "electronics",
    "clothes": "clothes",
    "wearable_clothes": "clothes",
}


def password_hash(password: str, salt: str | None = None) -> str:
    """OWASP scrypt minimum; fixed work parameters, no parameters accepted from users."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=2**17,
        r=8,
        p=1,
        maxmem=256 * 1024 * 1024,
        dklen=32,
    ).hex()
    return f"scrypt-v1${salt}${digest}"


def password_matches(password: str, encoded: str) -> bool:
    return hmac.compare_digest(password_hash(password, encoded.split("$")[1]), encoded)


def session_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Accounts:
    def __init__(self, store: CommunityStore):
        self.store = store

    def register(self, username: str, password: str) -> str | None:
        encoded = password_hash(password)
        user_id = secrets.token_hex(16)
        try:
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO accounts VALUES (?,?,?,?)",
                    (user_id, username, encoded, time.time()),
                )
        except sqlite3.IntegrityError:
            return None
        return user_id

    def authenticate(self, username: str, password: str) -> str | None:
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
        # Equal KDF work for unknown usernames, avoiding an inexpensive timing oracle.
        encoded = row["password_hash"] if row else f"scrypt-v1${'0' * 32}${'0' * 64}"
        valid = password_matches(password, encoded)
        return row["id"] if row and valid else None

    def start_session(self, user_id: str, previous: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.store.connection() as db:
            db.execute("DELETE FROM sessions WHERE digest=?", (session_digest(previous),))
            # Bound session storage; a fresh login replaces the oldest after five devices.
            db.execute(
                """DELETE FROM sessions WHERE user_id=? AND digest NOT IN
                (SELECT digest FROM sessions WHERE user_id=? ORDER BY expires DESC LIMIT 4)""",
                (user_id, user_id),
            )
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?)",
                (session_digest(token), user_id, time.time() + SESSION_SECONDS),
            )
        return token

    def user(self, token: str) -> dict | None:
        if not token or len(token) > 128:
            return None
        with self.store.connection() as db:
            row = db.execute(
                """SELECT a.id,a.username FROM accounts a JOIN sessions s
                ON a.id=s.user_id WHERE s.digest=? AND s.expires>?""",
                (session_digest(token), time.time()),
            ).fetchone()
            return dict(row) if row else None

    def logout(self, token: str):
        with self.store.connection() as db:
            db.execute("DELETE FROM sessions WHERE digest=?", (session_digest(token),))

    def delete(self, user_id: str):
        with self.store.connection() as db:
            db.execute("DELETE FROM accounts WHERE id=?", (user_id,))

    def summary(self, user: dict) -> dict:
        today = int(time.time() // 86400)
        with self.store.connection() as db:
            db.execute("BEGIN")
            total = db.execute(
                "SELECT COUNT(*) FROM dropoffs WHERE user_id=? AND recycling=1", (user["id"],)
            ).fetchone()[0]
            rows = db.execute(
                """SELECT materials,created,recycling FROM dropoffs
                WHERE user_id=? ORDER BY created DESC,id DESC LIMIT 50""",
                (user["id"],),
            ).fetchall()
            history_count = db.execute(
                "SELECT COUNT(*) FROM dropoffs WHERE user_id=?", (user["id"],)
            ).fetchone()[0]
            materials = db.execute(
                """SELECT j.value AS material, COUNT(*) AS count, MIN(d.created) AS first
                FROM dropoffs d, json_each(d.materials) j WHERE d.user_id=?
                AND j.value!='general' GROUP BY j.value""",
                (user["id"],),
            ).fetchall()
            milestones = db.execute(
                """SELECT created FROM dropoffs WHERE user_id=? AND recycling=1
                ORDER BY created,id LIMIT 25""",
                (user["id"],),
            ).fetchall()
            daily = dict(
                db.execute(
                    """SELECT CAST(created/86400 AS INTEGER),COUNT(*) FROM dropoffs
                WHERE user_id=? AND recycling=1 AND created>=? AND created<?
                GROUP BY CAST(created/86400 AS INTEGER)""",
                    (user["id"], (today - 27) * 86400, (today + 1) * 86400),
                ).fetchall()
            )
        material_counts = {row["material"]: row["count"] for row in materials}
        firsts = {row["material"]: row["first"] for row in materials}
        achievements = []
        for identifier, title, target in [
            ("first_dropoff", "First drop-off", 1),
            ("ten_dropoffs", "Ten drop-offs", 10),
            ("twentyfive_dropoffs", "Twenty-five", 25),
        ]:
            achievements.append(
                {
                    "id": identifier,
                    "title": title,
                    "progress": min(total, target),
                    "target": target,
                    "requirement": (
                        f"Complete {target} recycling drop-off{'s' if target > 1 else ''}."
                    ),
                    "earned_at": milestones[target - 1]["created"] if total >= target else None,
                }
            )
        achievements.append(
            {
                "id": "full_circle",
                "title": "Full circle",
                "progress": len(material_counts),
                "target": 5,
                "requirement": "Drop off all five recycling and donation categories.",
                "earned_at": max(firsts.values()) if len(firsts) == 5 else None,
            }
        )
        for identifier, title, material, requirement in [
            ("second_life", "Second life", "clothes", "Donate wearable clothes."),
            ("tech_return", "Tech return", "electronics", "Drop off electronics for recycling."),
        ]:
            achievements.append(
                {
                    "id": identifier,
                    "title": title,
                    "progress": int(material in firsts),
                    "target": 1,
                    "requirement": requirement,
                    "earned_at": firsts.get(material),
                }
            )
        return {
            "user": user,
            "recycling_count": total,
            "badges": {"first_dropoff": total >= 1, "ten_dropoffs": total >= 10},
            "achievements": achievements,
            "activity": {
                "material_counts": material_counts,
                "days": [
                    {"date": (today - 27 + i) * 86400, "count": daily.get(today - 27 + i, 0)}
                    for i in range(28)
                ],
            },
            "history_count": history_count,
            "history": [
                {
                    "materials": json.loads(r["materials"]),
                    "created": r["created"],
                    "recycling": bool(r["recycling"]),
                }
                for r in rows
            ],
        }

    def _sign(self, payload: str) -> str:
        with self.store.connection() as db:
            secret = db.execute("SELECT value FROM meta WHERE key='secret'").fetchone()[0]
        return hmac.new(
            secret.encode(), ("dropoff:" + payload).encode(), hashlib.sha256
        ).hexdigest()

    def ticket(self, user_id: str, kinds: list[str]) -> str:
        payload = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "id": secrets.token_hex(16),
                    "user": user_id,
                    "materials": sorted({MATERIALS[k] for k in kinds}),
                    "expires": time.time() + 86400,
                },
                separators=(",", ":"),
            ).encode()
        ).decode()
        return payload + "." + self._sign(payload)

    def complete(self, user_id: str, ticket: str) -> bool:
        payload, _, signature = ticket.partition(".")
        if not hmac.compare_digest(self._sign(payload).encode(), signature.encode()):
            raise ValueError("Invalid drop-off. Plan a new route.")
        try:
            data = json.loads(base64.urlsafe_b64decode(payload))
            if data["user"] != user_id or data["expires"] <= time.time():
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise ValueError(
                "Drop-off expired or belongs to another account. Plan a new route."
            ) from None
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT id FROM accounts WHERE id=?", (user_id,)).fetchone():
                raise ValueError("Account no longer exists. Sign in again.")
            # Replays (including a retry after a lost response) never increase the total.
            result = db.execute(
                "INSERT OR IGNORE INTO dropoffs VALUES (?,?,?,?,?)",
                (
                    data["id"],
                    user_id,
                    json.dumps(data["materials"]),
                    time.time(),
                    int(any(m != "general" for m in data["materials"])),
                ),
            )
            return bool(result.rowcount)
