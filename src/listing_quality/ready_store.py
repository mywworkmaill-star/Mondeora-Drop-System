"""Local, persistent buffer of prepared listing artifacts; never publishes remotely."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


def _json(value):
    def validate(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                validate(child)
        elif isinstance(item, list):
            for child in item:
                validate(child)
        elif type(item) not in (str, int, float, bool, type(None)):
            raise ValueError("Value is not a JSON type")

    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _identity(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{6,}", value) is None:
        raise ValueError("product_id must contain at least six ASCII digits")
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _now(value):
    return datetime.now(timezone.utc) if value is None else _utc(value)


class ReadyStore:
    """SQLite artifact queue; ``path`` is the local database file as a Path.

    The preparation layer owns vetting. This store treats artifact dictionaries
    as opaque and uses only explicit blockers to assign initial readiness.
    Claim/side-effect history is permanent: put never requeues attempted work.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS ready_listings (
                product_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                artifact TEXT NOT NULL,
                artifact_hash TEXT NOT NULL,
                prepared_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                blockers TEXT NOT NULL,
                detail TEXT,
                side_effect_started INTEGER NOT NULL DEFAULT 0
            )""")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _record(row, now=None):
        record = dict(row)
        side_effect_started = record.pop("side_effect_started", 0)
        errors = []
        try:
            _identity(record["product_id"])
        except ValueError:
            errors.append("invalid_product_id")
        for key in ("artifact", "blockers", "detail"):
            try:
                record[key] = json.loads(record[key], object_pairs_hook=_unique_object) if record[key] is not None else None
                _json(record[key])
            except (ValueError, TypeError, RecursionError):
                errors.append("invalid_" + key)
                record[key] = None
        try:
            if not isinstance(record["artifact"], dict):
                raise ValueError("Artifact must be a dictionary")
            digest = hashlib.sha256(_json(record["artifact"]).encode("utf-8")).hexdigest()
            if digest != record["artifact_hash"]:
                raise ValueError("Artifact hash mismatch")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            errors.append("artifact_hash_mismatch")
            record["artifact"] = None
        if not isinstance(record["blockers"], list) or any(
            not isinstance(reason, str) or not reason.strip() for reason in record["blockers"]
        ):
            errors.append("invalid_blockers")
            record["blockers"] = []
        dates = {}
        for key in ("prepared_at", "expires_at", "updated_at"):
            try:
                dates[key] = _utc(datetime.fromisoformat(record[key]))
            except (ValueError, TypeError, OverflowError):
                errors.append("invalid_" + key)
        if now is not None and dates.get("prepared_at", now) > now:
            errors.append("future_prepared_at")
        if side_effect_started not in (0, 1):
            errors.append("invalid_side_effect_state")
        if record["status"] not in ("ready", "blocked", "stale", "published", "publishing", "needs_reconciliation"):
            errors.append("unknown_status")
            record["status"] = "needs_reconciliation"
        if record["status"] == "ready" and side_effect_started != 0:
            errors.append("side_effect_already_started")
            record["status"] = "needs_reconciliation"
        if record["status"] == "ready" and record["blockers"]:
            errors.append("ready_has_blockers")
        if errors:
            record["blockers"] = list(dict.fromkeys(record["blockers"] + errors))
            detail = record["detail"]
            record["detail"] = {**(detail if isinstance(detail, dict) else {"stored_detail": detail}),
                                "integrity_errors": list(dict.fromkeys(errors))}
            if record["status"] == "ready":
                record["status"] = "blocked"
        if now is not None and record["status"] == "ready" and dates["expires_at"] <= now:
            record["status"] = "expired"
        return record

    def put(self, product_id, artifact, blockers=(), ttl_seconds=86400, now=None):
        """Prepare/replace unattempted work, or return protected work unchanged."""
        product_id = _identity(product_id)
        if not isinstance(blockers, (tuple, list)) or any(
            not isinstance(reason, str) or not reason.strip() for reason in blockers
        ):
            raise ValueError("blockers must be a list/tuple of non-empty strings")
        now = _now(now)
        if not isinstance(artifact, dict):
            raise ValueError("artifact must be a JSON dictionary")
        payload = _json(artifact)
        record = {
            "product_id": product_id,
            "status": "ready" if not blockers else "blocked",
            "artifact": payload,
            "artifact_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "prepared_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
            "updated_at": now.isoformat(),
            "blockers": _json(list(blockers)),
            "detail": None,
        }
        with self._connect() as db:
            db.execute("""INSERT INTO ready_listings
                (product_id, status, artifact, artifact_hash, prepared_at, expires_at,
                 updated_at, blockers, detail)
                VALUES (:product_id, :status, :artifact, :artifact_hash, :prepared_at,
                        :expires_at, :updated_at, :blockers, :detail)
                ON CONFLICT(product_id) DO UPDATE SET
                    status=excluded.status, artifact=excluded.artifact,
                    artifact_hash=excluded.artifact_hash, prepared_at=excluded.prepared_at,
                    expires_at=excluded.expires_at, updated_at=excluded.updated_at,
                    blockers=excluded.blockers, detail=excluded.detail
                WHERE ready_listings.status IN ('ready', 'blocked', 'stale')
                  AND ready_listings.side_effect_started = 0""", record)
            row = db.execute("SELECT * FROM ready_listings WHERE product_id = ?", (product_id,)).fetchone()
        return self._record(row)

    def get(self, product_id):
        """Return the persisted record (including artifact) for reconciliation, or None."""
        product_id = _identity(product_id)
        with self._connect() as db:
            row = db.execute("SELECT * FROM ready_listings WHERE product_id = ?", (product_id,)).fetchone()
        return self._record(row) if row is not None else None

    def mark(self, product_id, status, detail=None, now=None):
        """Record a local outcome; only put may create a ready record."""
        product_id = _identity(product_id)
        if status not in ("published", "blocked", "stale", "needs_reconciliation", "publishing"):
            raise ValueError("Unsupported status")
        now = _now(now)
        encoded_detail = _json(detail) if detail is not None else None
        with self._connect() as db:
            changed = db.execute("""UPDATE ready_listings
                SET side_effect_started = CASE
                        WHEN ? IN ('publishing', 'published', 'needs_reconciliation')
                          OR status NOT IN ('ready', 'blocked', 'stale') THEN 1
                        ELSE side_effect_started END,
                    status = ?, detail = ?, updated_at = ? WHERE product_id = ?""",
                (status, status, encoded_detail, now.isoformat(), product_id))
            if not changed.rowcount:
                raise KeyError(product_id)
            row = db.execute("SELECT * FROM ready_listings WHERE product_id = ?", (product_id,)).fetchone()
        return self._record(row)

    def ready(self, limit=10, now=None):
        """Return eligible artifacts without claiming; expiration is a derived view."""
        now = _now(now)
        with self._connect() as db:
            rows = db.execute("""SELECT * FROM ready_listings
                WHERE status = 'ready' ORDER BY prepared_at, product_id""").fetchall()
        records = [self._record(row, now) for row in rows]
        return [record for record in records if record["status"] == "ready"][:limit]

    def claim(self, limit=10, now=None):
        """Atomically move up to ten eligible products into publishing, across processes."""
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("limit must be an integer from 1 through 10")
        explicit_now = _utc(now) if now is not None else None
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = _now(explicit_now)
            records = [self._record(row, now) for row in db.execute("""SELECT * FROM ready_listings
                WHERE status = 'ready' ORDER BY prepared_at, product_id""")]
            claimed = [record for record in records if record["status"] == "ready"][:limit]
            for record in claimed:
                db.execute("""UPDATE ready_listings SET status = 'publishing', side_effect_started = 1, updated_at = ?
                    WHERE product_id = ? AND status = 'ready'""", (now.isoformat(), record["product_id"]))
                record.update(status="publishing", updated_at=now.isoformat())
        return claimed

    def published_since(self, since: datetime) -> int:
        """Count published product IDs at/after since; bad dates raise, never undercount."""
        since = _utc(since)
        with self._connect() as db:
            rows = db.execute("SELECT product_id, updated_at FROM ready_listings WHERE status = 'published'")
            return len({_identity(row["product_id"]) for row in rows
                        if _utc(datetime.fromisoformat(row["updated_at"])) >= since})

    def summary(self, target=10, now=None):
        """Count products, not variants; content_prepared_count is not a vetting count.

        Compact items omit artifacts/raw responses. Expired counts apply to
        formerly-ready work only; blocked/publishing/outcome statuses survive TTL.
        """
        now = _now(now)
        with self._connect() as db:
            records = [self._record(row, now) for row in db.execute(
                "SELECT * FROM ready_listings ORDER BY prepared_at, product_id"
            )]
        report: dict[str, Any] = {status + "_count": sum(row["status"] == status for row in records)
                  for status in ("ready", "blocked", "expired", "publishing", "published", "needs_reconciliation", "stale")}
        report["shortfall"] = max(0, target - report["ready_count"])
        report["content_prepared_count"] = sum(row["artifact"] is not None for row in records)
        report["items"] = [{key: row[key] for key in (
            "product_id", "status", "expires_at", "prepared_at", "updated_at", "blockers", "detail"
        )} for row in records]
        reasons = {}
        for row in records:
            if row["status"] == "blocked":
                for reason in set(row["blockers"]):
                    reasons[reason] = reasons.get(reason, 0) + 1
        report["blocked_reasons"] = reasons
        return report
