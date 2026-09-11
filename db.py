"""SQLite persistence for the career engine.

Schema (table `jobs`):
    id             TEXT PRIMARY KEY   sha1(normalised company + normalised title)
    source         TEXT               linkedin / indeed / bayt / greenhouse / lever
    title          TEXT
    company        TEXT
    url            TEXT
    location       TEXT
    description    TEXT
    salary_text    TEXT               raw salary string if the board exposed one
    date_posted    TEXT               ISO date if known
    risk_score     INTEGER            output of engine/uae_detector.py
    risk_reasons   TEXT               semicolon-joined human readable flags
    is_ghost       INTEGER            1 if quarantined by the safety net
    status         TEXT               ingested | shortlisted | applied | sent
    evaluated      INTEGER            0 until /evaluate has looked at it
    semantic_score REAL               EFFICIENT_MODE cosine similarity (nullable)
    first_seen     TEXT               ISO timestamp of first ingestion
    last_seen      TEXT               ISO timestamp of most recent ingestion
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from engine import config

STATUS_INGESTED = "ingested"
STATUS_SHORTLISTED = "shortlisted"
STATUS_APPLIED = "applied"
STATUS_SENT = "sent"
VALID_STATUSES = {STATUS_INGESTED, STATUS_SHORTLISTED, STATUS_APPLIED, STATUS_SENT}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    title          TEXT NOT NULL,
    company        TEXT NOT NULL,
    url            TEXT,
    location       TEXT,
    description    TEXT,
    salary_text    TEXT,
    date_posted    TEXT,
    risk_score     INTEGER NOT NULL DEFAULT 0,
    risk_reasons   TEXT NOT NULL DEFAULT '',
    is_ghost       INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'ingested',
    evaluated      INTEGER NOT NULL DEFAULT 0,
    semantic_score REAL,
    first_seen     TEXT NOT NULL,
    last_seen      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_pending ON jobs(is_ghost, evaluated);
"""

# Columns added after the initial schema; applied idempotently by init_db().
MIGRATIONS = {
    "semantic_score": "ALTER TABLE jobs ADD COLUMN semantic_score REAL",
    "evaluated": "ALTER TABLE jobs ADD COLUMN evaluated INTEGER NOT NULL DEFAULT 0",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalise(text: str | None) -> str:
    """Lower-case, strip punctuation and collapse whitespace for hashing."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def job_id(company: str | None, title: str | None) -> str:
    """Stable id: sha1 of normalised company + title. Same posting on two boards -> same id."""
    key = f"{normalise(company)}|{normalise(title)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        for column, ddl in MIGRATIONS.items():
            if column not in existing:
                conn.execute(ddl)


def upsert_jobs(jobs: Iterable[dict], db_path: Path | str | None = None) -> tuple[int, int]:
    """Insert new jobs or refresh last_seen on existing ones.

    Returns (inserted, refreshed). Never downgrades status/evaluated on an existing row.
    """
    inserted = refreshed = 0
    now = _now()
    with connect(db_path) as conn:
        for job in jobs:
            jid = job.get("id") or job_id(job.get("company"), job.get("title"))
            row = conn.execute("SELECT id FROM jobs WHERE id = ?", (jid,)).fetchone()
            desc = job.get("description") or ""
            if row:
                conn.execute(
                    "UPDATE jobs SET last_seen = ?, url = COALESCE(url, ?), "
                    "description = CASE WHEN length(description) < length(?) THEN ? ELSE description END "
                    "WHERE id = ?",
                    (now, job.get("url"), desc, desc, jid),
                )
                refreshed += 1
                continue
            conn.execute(
                """INSERT INTO jobs (id, source, title, company, url, location, description, salary_text,
                                     date_posted, risk_score, risk_reasons, is_ghost, status, evaluated,
                                     semantic_score, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    jid,
                    job.get("source", "unknown"),
                    job.get("title") or "",
                    job.get("company") or "",
                    job.get("url"),
                    job.get("location"),
                    desc,
                    job.get("salary_text"),
                    job.get("date_posted"),
                    int(job.get("risk_score", 0)),
                    job.get("risk_reasons", ""),
                    int(bool(job.get("is_ghost", False))),
                    job.get("status", STATUS_INGESTED),
                    int(bool(job.get("evaluated", False))),
                    job.get("semantic_score"),
                    now,
                    now,
                ),
            )
            inserted += 1
    return inserted, refreshed


def known_ids(db_path: Path | str | None = None) -> set[str]:
    with connect(db_path) as conn:
        return {r["id"] for r in conn.execute("SELECT id FROM jobs")}


def known_titles(db_path: Path | str | None = None) -> list[tuple[str, str, str]]:
    """(id, company, title) for every stored job - used for repost/duplicate detection."""
    with connect(db_path) as conn:
        return [(r["id"], r["company"], r["title"]) for r in conn.execute("SELECT id, company, title FROM jobs")]


def pending_jobs(db_path: Path | str | None = None) -> list[dict]:
    """Clean (non-ghost) jobs that /evaluate has not yet looked at."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE is_ghost = 0 AND evaluated = 0 ORDER BY first_seen DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def all_jobs(db_path: Path | str | None = None) -> list[dict]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY first_seen DESC")]


def get_job(jid: str, db_path: Path | str | None = None) -> dict | None:
    """Fetch by exact id, falling back to unique prefix match."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone()
        if row is None:
            rows = conn.execute("SELECT * FROM jobs WHERE id LIKE ?", (jid + "%",)).fetchall()
            row = rows[0] if len(rows) == 1 else None
    return dict(row) if row else None


def mark_evaluated(ids: Iterable[str], db_path: Path | str | None = None) -> int:
    with connect(db_path) as conn:
        cur = conn.executemany("UPDATE jobs SET evaluated = 1 WHERE id = ?", [(i,) for i in ids])
        return cur.rowcount


def set_status(jid: str, status: str, db_path: Path | str | None = None) -> bool:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status {status!r}; expected one of {sorted(VALID_STATUSES)}")
    with connect(db_path) as conn:
        cur = conn.execute("UPDATE jobs SET status = ?, evaluated = 1 WHERE id = ?", (status, jid))
        return cur.rowcount == 1


def set_semantic_scores(scores: dict[str, float], db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.executemany(
            "UPDATE jobs SET semantic_score = ? WHERE id = ?", [(s, i) for i, s in scores.items()]
        )


def stats(db_path: Path | str | None = None) -> dict:
    with connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        ghost = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_ghost = 1").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_ghost = 0 AND evaluated = 0").fetchone()[0]
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")
        }
    return {"total": total, "quarantined": ghost, "pending_evaluation": pending, "by_status": by_status}
