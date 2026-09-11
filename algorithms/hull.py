"""The Convex Hull filter: a loose bounding box around the candidate's eligible domain.

    Hull(J) = { j in J | Loc(j) in UAE
                        AND Seniority(j) <= MaxLevel
                        AND Track(j) ∩ Domain != ∅ }

Deliberately loose (fail-open): unknown location, unknown seniority, or an unrecognised
track keeps the job. Only *explicit* out-of-hull signals reject.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from engine import config

SENIORITY_LEVELS: list[tuple[int, list[str]]] = [
    (4, [r"\b(principal|staff|distinguished|head of|director|vp|vice president|cto|chief|manager|supervisor)\b"]),
    (3, [r"\b(senior|sr\.?|lead|leader|team lead|tech lead)\b"]),
    (2, [r"\b(mid|mid-level|intermediate|associate)\b"]),
    (1, [r"\b(junior|jr\.?|entry|graduate|fresher|early career)\b"]),
    (0, [r"\b(intern|internship|trainee|apprentice)\b"]),
]

_YEARS_RE = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:-|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


@dataclass
class HullDecision:
    inside: bool
    reason: str
    seniority: int | None
    tracks: list[str]


def seniority_of(title: str | None, description: str | None = None) -> int | None:
    """Infer seniority from the title. Returns None when nothing explicit is found."""
    t = (title or "").lower()
    extra = getattr(config, "SENIORITY_EXTRA_PATTERNS", {})
    for level, patterns in SENIORITY_LEVELS:
        merged = list(patterns) + list(extra.get(level, []))
        if any(re.search(p, t) for p in merged):
            return level
    return None


def in_uae(location: str | None) -> bool | None:
    """True if UAE/remote, False if clearly elsewhere, None if unknown."""
    loc = (location or "").strip().lower()
    if not loc:
        return None
    if any(k in loc for k in config.UAE_LOCATION_KEYWORDS):
        return True
    return False


def tracks_of(title: str | None, description: str | None = None, min_hits: int = 1) -> list[str]:
    """Tracks whose keywords appear at least `min_hits` distinct times in title+description."""
    text = f"{title or ''} {description or ''}".lower()
    hits = []
    for track, keywords in config.DOMAIN_TRACKS.items():
        if sum(1 for k in keywords if k in text) >= min_hits:
            hits.append(track)
    return hits


def decide(job: dict) -> HullDecision:
    title, desc, loc = job.get("title"), job.get("description"), job.get("location")

    uae = in_uae(loc)
    if uae is False:
        return HullDecision(False, f"outside UAE: {loc}", None, [])

    kw = _excluded_keyword(title)
    if kw:
        return HullDecision(False, f"excluded title keyword: {kw}", None, [])

    level = seniority_of(title, desc)
    if level is not None and level > config.MAX_SENIORITY_LEVEL:
        return HullDecision(False, f"seniority level {level} > max {config.MAX_SENIORITY_LEVEL}", level, [])

    # A single keyword in the title is enough. Without title evidence the description must
    # carry strong evidence (>= DESC_MIN_HITS distinct keywords for one track) so a passing
    # mention of "quality assurance" in an ops posting does not pull it inside the hull.
    title_tracks = tracks_of(title)
    if _is_clearly_non_tech(title) and not title_tracks:
        return HullDecision(False, f"non-tech title: {title}", level, [])
    tracks = title_tracks or tracks_of(None, desc, min_hits=DESC_MIN_HITS)
    if not tracks:
        return HullDecision(False, "no overlap with candidate domain tracks", level, [])

    return HullDecision(True, "inside hull", level, tracks)


DESC_MIN_HITS = 3


def _is_clearly_non_tech(title: str | None) -> bool:
    return bool(re.search(config.NON_TECH_TITLE_PATTERN, title or "", re.IGNORECASE))


def _excluded_keyword(title: str | None) -> str | None:
    t = (title or "").lower()
    for kw in getattr(config, "EXCLUDE_TITLE_KEYWORDS", []):
        if kw.lower() in t:
            return kw
    return None


def filter_hull(jobs: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Return (inside, [(job, reason) for rejected])."""
    inside, rejected = [], []
    for job in jobs:
        d = decide(job)
        (inside.append(job) if d.inside else rejected.append((job, d.reason)))
    return inside, rejected
