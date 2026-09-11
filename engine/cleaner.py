"""Normalisation and fuzzy deduplication of scraped jobs.

Two layers:
    1. Exact: identical id (sha1 of normalised company+title) collapses in-batch and against the DB.
    2. Fuzzy: thefuzz token_set_ratio on "company | title" >= FUZZY_DUPLICATE_THRESHOLD collapses
       near-identical postings ("Sr. Software Engineer" vs "Senior Software Engineer").

Jobs that match something already in the DB are reported as *reposts* so the detector can
apply the ghost penalty, rather than being silently dropped.
"""
from __future__ import annotations

import re
from typing import Iterable

from thefuzz import fuzz

from engine import config
from engine.db import job_id, normalise

_WS = re.compile(r"\s+")
_HTML_TAG = re.compile(r"<[^>]+>")
_TITLE_NOISE = re.compile(
    r"\b(urgent(?:ly)?|hiring|immediate(?:ly)?|required|wanted|needed|vacancy|job|position|opening)\b",
    re.IGNORECASE,
)
_ABBREVIATIONS = [
    (re.compile(r"\bsr\b\.?", re.IGNORECASE), "Senior"),
    (re.compile(r"\bjr\b\.?", re.IGNORECASE), "Junior"),
    (re.compile(r"\bdev\b\.?", re.IGNORECASE), "Developer"),
    (re.compile(r"\beng\b\.?", re.IGNORECASE), "Engineer"),
    (re.compile(r"\bswe\b", re.IGNORECASE), "Software Engineer"),
    (re.compile(r"\bfull[\s-]?stack\b", re.IGNORECASE), "Full Stack"),
    (re.compile(r"\bfront[\s-]?end\b", re.IGNORECASE), "Frontend"),
    (re.compile(r"\bback[\s-]?end\b", re.IGNORECASE), "Backend"),
]
_COMPANY_SUFFIX = re.compile(
    r"\b(llc|l\.l\.c|fzc|fze|fz-llc|fzco|dmcc|ltd|limited|inc|plc|co|company|group|holdings?)\b\.?",
    re.IGNORECASE,
)


def clean_text(text: str | None) -> str:
    text = _HTML_TAG.sub(" ", text or "")
    text = text.replace("\xa0", " ")
    return _WS.sub(" ", text).strip()


def clean_title(title: str | None) -> str:
    title = clean_text(title)
    title = _TITLE_NOISE.sub("", title)
    for pattern, full in _ABBREVIATIONS:
        title = pattern.sub(full, title)
    title = re.sub(r"[\-–|:]+\s*$", "", title)  # trailing separators left by noise removal
    return _WS.sub(" ", title).strip(" -–|:")


def clean_company(company: str | None) -> str:
    company = clean_text(company)
    company = _COMPANY_SUFFIX.sub("", company)
    return _WS.sub(" ", company).strip(" ,.-")


def normalise_job(job: dict) -> dict:
    """Return a shallow copy with cleaned title/company/description and a stable id."""
    out = dict(job)
    out["title"] = clean_title(job.get("title"))
    out["company"] = clean_company(job.get("company"))
    out["description"] = clean_text(job.get("description"))
    out["location"] = clean_text(job.get("location"))
    out["id"] = job_id(out["company"], out["title"])
    return out


def _fuzzy_key(company: str, title: str) -> tuple[str, str]:
    return (normalise(company), normalise(title))


def _is_fuzzy_dup(key: tuple[str, str], seen_keys: Iterable[tuple[str, str]]) -> bool:
    """Company and title are compared separately so 'QA Engineer' and 'Software Engineer' at the
    same company never collapse. token_sort_ratio tolerates word order and abbreviations."""
    company, title = key
    t = config.FUZZY_DUPLICATE_THRESHOLD
    return any(
        fuzz.token_sort_ratio(company, c) >= t and fuzz.token_sort_ratio(title, k) >= t
        for c, k in seen_keys
    )


def dedupe(jobs: list[dict], existing: list[tuple[str, str, str]] | None = None) -> tuple[list[dict], set[str], int]:
    """Deduplicate a batch.

    Args:
        jobs:     raw scraped dicts.
        existing: (id, company, title) rows already in the DB.

    Returns:
        (unique_jobs, repost_ids, dropped_count)
        unique_jobs  - normalised, first occurrence of each (fuzzy) posting in this batch
        repost_ids   - ids in unique_jobs that fuzzy-match something already in the DB
        dropped      - number of in-batch duplicates removed
    """
    existing = existing or []
    existing_ids = {e[0] for e in existing}
    existing_keys = [_fuzzy_key(e[1], e[2]) for e in existing]

    unique: list[dict] = []
    seen_ids: set[str] = set()
    seen_keys: list[tuple[str, str]] = []
    reposts: set[str] = set()
    dropped = 0

    for raw in jobs:
        job = normalise_job(raw)
        if not job["title"] or not job["company"]:
            dropped += 1
            continue
        key = _fuzzy_key(job["company"], job["title"])
        if job["id"] in seen_ids or _is_fuzzy_dup(key, seen_keys):
            dropped += 1
            continue
        seen_ids.add(job["id"])
        seen_keys.append(key)
        if job["id"] in existing_ids or _is_fuzzy_dup(key, existing_keys):
            reposts.add(job["id"])
        unique.append(job)

    return unique, reposts, dropped
