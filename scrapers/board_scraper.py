"""Job-board scraper built on python-jobspy (LinkedIn AE, Indeed AE, Bayt).

Every scrape returns plain dicts with the canonical keys used across the engine:
    source, title, company, url, location, description, salary_text, date_posted
"""
from __future__ import annotations

import logging
from typing import Iterable

from engine import config

log = logging.getLogger(__name__)


def _salary_text(row) -> str | None:
    lo, hi = row.get("min_amount"), row.get("max_amount")
    if _isnan(lo) and _isnan(hi):
        return None
    cur = row.get("currency") or "AED"
    interval = row.get("interval") or "month"
    lo_s = f"{lo:,.0f}" if not _isnan(lo) else ""
    hi_s = f"{hi:,.0f}" if not _isnan(hi) else ""
    rng = f"{lo_s}-{hi_s}".strip("-")
    return f"{cur} {rng} per {interval}"


def _isnan(v) -> bool:
    try:
        return v is None or v != v  # NaN != NaN
    except Exception:
        return True


def _str(v) -> str | None:
    if _isnan(v):
        return None
    s = str(v).strip()
    return s or None


def to_jobs(df) -> list[dict]:
    """Convert a jobspy DataFrame into canonical job dicts."""
    jobs = []
    if df is None or len(df) == 0:
        return jobs
    for _, row in df.iterrows():
        row = row.to_dict()
        jobs.append(
            {
                "source": _str(row.get("site")) or "board",
                "title": _str(row.get("title")),
                "company": _str(row.get("company")),
                "url": _str(row.get("job_url_direct")) or _str(row.get("job_url")),
                "location": _str(row.get("location")),
                "description": _str(row.get("description")) or "",
                "salary_text": _salary_text(row),
                "date_posted": _str(row.get("date_posted")),
            }
        )
    return jobs


def scrape(
    search_terms: Iterable[str] | None = None,
    locations: Iterable[str] | None = None,
    sites: Iterable[str] | None = None,
    results_wanted: int | None = None,
) -> list[dict]:
    """Run jobspy across every (term, location) combination. Per-query failures are logged and skipped."""
    from jobspy import scrape_jobs  # deferred: heavy import

    search_terms = list(search_terms or config.SEARCH_TERMS)
    locations = list(locations or config.SEARCH_LOCATIONS)
    sites = list(sites or config.JOBSPY_SITES)
    results_wanted = results_wanted or config.RESULTS_PER_SEARCH

    all_jobs: list[dict] = []
    for loc in locations:
        for term in search_terms:
            try:
                df = scrape_jobs(
                    site_name=sites,
                    search_term=term,
                    location=loc,
                    results_wanted=results_wanted,
                    hours_old=config.JOBSPY_HOURS_OLD,
                    country_indeed="united arab emirates",
                    linkedin_fetch_description=True,
                    description_format="markdown",
                )
            except Exception as exc:  # network / anti-bot / parser errors
                log.warning("jobspy failed for %r in %r: %s", term, loc, exc)
                continue
            batch = to_jobs(df)
            log.info("jobspy %-32s %-16s -> %d", term, loc, len(batch))
            all_jobs.extend(batch)
    return all_jobs


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    jobs = scrape(search_terms=config.SEARCH_TERMS[:2], locations=config.SEARCH_LOCATIONS[:1], results_wanted=5)
    print(json.dumps(jobs[:3], indent=2, default=str))
    print(f"{len(jobs)} jobs")
