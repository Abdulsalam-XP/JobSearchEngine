"""Direct ATS scraper: free public JSON endpoints, no API key, no subscription.

Supported boards (slugs configured in engine/config.py):
    Greenhouse  https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
    Lever       https://api.lever.co/v0/postings/{slug}?mode=json

Only postings whose location mentions the UAE (or remote) are kept. Unknown slugs 404 and
are skipped with a warning so a stale config entry never breaks ingestion.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

import requests

from engine import config

log = logging.getLogger(__name__)

TIMEOUT = 20
HEADERS = {"User-Agent": "uae-career-engine/1.0 (+local job screening)"}
_TAG = re.compile(r"<[^>]+>")


def _strip_html(s: str | None) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", html.unescape(s or ""))).strip()


def _uae_location(loc: str | None) -> bool:
    l = (loc or "").lower()
    return any(k in l for k in config.UAE_LOCATION_KEYWORDS)


def _get(url: str) -> dict | list | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 404:
            log.warning("ATS board not found: %s", url)
            return None
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("ATS fetch failed %s: %s", url, exc)
        return None


# ------------------------------------------------------------------ Greenhouse
def fetch_greenhouse(slug: str) -> list[dict]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name")
        if not _uae_location(loc):
            continue
        jobs.append(
            {
                "source": "greenhouse",
                "title": j.get("title"),
                "company": slug.replace("-", " ").title(),
                "url": j.get("absolute_url"),
                "location": loc,
                "description": _strip_html(j.get("content")),
                "salary_text": None,
                "date_posted": (j.get("updated_at") or j.get("first_published") or "")[:10] or None,
            }
        )
    return jobs


# ----------------------------------------------------------------------- Lever
def fetch_lever(slug: str) -> list[dict]:
    data = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not data or not isinstance(data, list):
        return []
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        loc = cats.get("location") or ", ".join(j.get("allLocations") or [])
        if not _uae_location(loc):
            continue
        created = j.get("createdAt")
        posted = datetime.fromtimestamp(created / 1000, tz=timezone.utc).date().isoformat() if created else None
        desc = _strip_html(j.get("descriptionPlain") or j.get("description"))
        for lst in j.get("lists") or []:
            desc += f" {lst.get('text', '')}: {_strip_html(lst.get('content'))}"
        jobs.append(
            {
                "source": "lever",
                "title": j.get("text"),
                "company": slug.replace("-", " ").title(),
                "url": j.get("hostedUrl") or j.get("applyUrl"),
                "location": loc,
                "description": desc,
                "salary_text": None,
                "date_posted": posted,
            }
        )
    return jobs


# ----------------------------------------------------------------------- Ashby
def fetch_ashby(slug: str) -> list[dict]:
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location") or ""
        secondary = ", ".join(s.get("location", "") for s in j.get("secondaryLocations") or [])
        full_loc = ", ".join(x for x in (loc, secondary) if x)
        if j.get("isRemote"):
            full_loc = f"{full_loc}, Remote" if full_loc else "Remote"
        if not _uae_location(full_loc):
            continue
        comp = (j.get("compensation") or {}).get("compensationTierSummary")
        jobs.append(
            {
                "source": "ashby",
                "title": j.get("title"),
                "company": slug.replace("-", " ").title(),
                "url": j.get("jobUrl") or j.get("applyUrl"),
                "location": full_loc,
                "description": _strip_html(j.get("descriptionHtml") or j.get("descriptionPlain")),
                "salary_text": comp,
                "date_posted": (j.get("publishedAt") or "")[:10] or None,
            }
        )
    return jobs


# -------------------------------------------------------------------- Workable
def fetch_workable(slug: str) -> list[dict]:
    url = f"https://apply.workable.com/api/v3/accounts/{slug}/jobs"
    try:
        r = requests.post(url, headers=HEADERS, timeout=TIMEOUT,
                          json={"query": "", "location": [], "department": [], "worktype": [], "remote": []})
        if r.status_code == 404:
            log.warning("ATS board not found: %s", url)
            return []
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.warning("ATS fetch failed %s: %s", url, exc)
        return []
    jobs = []
    for j in data.get("results", []):
        loc_obj = j.get("location") or {}
        loc = ", ".join(x for x in (loc_obj.get("city"), loc_obj.get("country")) if x)
        if j.get("remote"):
            loc = f"{loc}, Remote" if loc else "Remote"
        if not _uae_location(loc):
            continue
        shortcode = j.get("shortcode")
        desc = _strip_html(j.get("description"))
        if not desc and shortcode:  # list endpoint omits the body; fetch detail
            detail = _get(f"https://apply.workable.com/api/v2/accounts/{slug}/jobs/{shortcode}")
            if detail:
                desc = _strip_html(f"{detail.get('description', '')} {detail.get('requirements', '')}")
        jobs.append(
            {
                "source": "workable",
                "title": j.get("title"),
                "company": slug.replace("-", " ").title(),
                "url": f"https://apply.workable.com/{slug}/j/{shortcode}/" if shortcode else None,
                "location": loc,
                "description": desc,
                "salary_text": None,
                "date_posted": (j.get("published") or "")[:10] or None,
            }
        )
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
}


def scrape(boards: dict[str, list[str]] | None = None) -> list[dict]:
    """boards = {"greenhouse": [...], "lever": [...], "ashby": [...], "workable": [...]}"""
    boards = boards if boards is not None else config.ATS_BOARDS
    jobs: list[dict] = []
    for ats, slugs in boards.items():
        fetch = FETCHERS.get(ats)
        if fetch is None:
            log.warning("unknown ATS %r in config.ATS_BOARDS", ats)
            continue
        for slug in slugs:
            batch = fetch(slug)
            log.info("%-10s %-20s -> %d UAE jobs", ats, slug, len(batch))
            jobs.extend(batch)
    return jobs


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = scrape()
    print(json.dumps(out[:3], indent=2, default=str))
    print(f"{len(out)} jobs")
