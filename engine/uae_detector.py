"""UAE-specific scam / ghost-job detector.

Philosophy: FAIL-OPEN. A job is innocent until explicitly proven guilty. Missing or
ambiguous data never adds risk. Only concrete regex hits and hard dates add penalties.

Penalties (from SPEC.md section 4):
    visa trap      60   employer charges candidate for the visa
    wage trap      70   commission-only / direct sales / salary below floor
    ghost          40   posted > GHOST_DAYS ago, or identical repost
    agency         35   unnamed "confidential client" style headhunter

risk_score >= QUARANTINE_THRESHOLD (50) -> is_ghost = True (quarantined).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from engine import config

# --------------------------------------------------------------------------- #
# 1. Illegal visa traps. Golden Visa / Spouse Visa / NOC are NOT penalised.     #
# --------------------------------------------------------------------------- #
VISA_TRAP_PATTERNS = [
    r"\bvisa\s+(charges?|fees?|costs?|deposit|payment)\b",
    r"\bpay(?:ing)?\s+for\s+(?:your|the|own)?\s*visa\b",
    r"\b(?:candidate|applicant|employee)s?\s+(?:will|must|should|to)\s+(?:pay|bear|cover)\s+(?:for\s+)?(?:the\s+)?visa\b",
    r"\bvisa\s+(?:cost|fee|charge)s?\s+(?:will\s+be\s+)?(?:deducted|borne\s+by\s+(?:the\s+)?(?:candidate|employee))\b",
    r"\b(?:security|refundable)\s+deposit\s+(?:is\s+)?required\b",
    r"\bregistration\s+fee\b",
    r"\bprocessing\s+fee\b",
    r"\btraining\s+fee\s+(?:is\s+)?(?:required|applicable|payable)\b",
]
VISA_SAFE_PATTERNS = [
    r"\bgolden\s+visa\b",
    r"\bspouse\s+visa\b",
    r"\bfamily\s+visa\b",
    r"\bown\s+visa\b",
    r"\bvisa\s+(?:will\s+be\s+)?(?:provided|sponsored|covered)\b",
    r"\bcompany\s+(?:will\s+)?(?:provide|sponsor)s?\s+(?:the\s+)?visa\b",
    r"\bnoc\b",
]

# --------------------------------------------------------------------------- #
# 2. Sub-market wage / commission traps                                        #
# --------------------------------------------------------------------------- #
WAGE_TRAP_PATTERNS = [
    r"\bcommission[\s-]+only\b",
    r"\bonly\s+commission\b",
    r"\bcommission[\s-]+based\s+(?:only|role|position|pay|salary)\b",
    r"\bdirect\s+sales\b",
    r"\bno\s+(?:basic|base|fixed)\s+salary\b",
    r"\bunpaid\b",
    r"\bincentive[\s-]+only\b",
]

# --------------------------------------------------------------------------- #
# 4. Unnamed third-party harvesting agencies                                   #
# --------------------------------------------------------------------------- #
AGENCY_COMPANY_PATTERNS = [
    r"\bconfidential\b",
    r"\bundisclosed\b",
    r"\bleading\s+(?:recruitment|staffing|manpower)\s+(?:agency|firm|company)\b",
    r"\b(?:recruitment|staffing|manpower)\s+(?:agency|consultancy|consultants?|firm)\b",
    r"\bhead\s*hunters?\b",
    r"\bclient\s+of\b",
    r"^(?:n/?a|unknown|private|company)$",
]
AGENCY_DESC_PATTERNS = [
    r"\b(?:our|a|the)\s+(?:confidential|prestigious|reputed|leading)\s+client\b",
    r"\bon\s+behalf\s+of\s+(?:our|a|the)\s+client\b",
    r"\bclient\s+(?:name|details?)\s+(?:is|are|will\s+be)\s+(?:confidential|undisclosed|withheld)\b",
]

# Salary extraction -------------------------------------------------------- #
_SALARY_RE = re.compile(
    r"(?:aed|dhs?|dirhams?)\s*\.?\s*([0-9][0-9,\.]{2,})(?:\s*(?:-|to|–)\s*([0-9][0-9,\.]{2,}))?"
    r"|([0-9][0-9,\.]{2,})(?:\s*(?:-|to|–)\s*([0-9][0-9,\.]{2,}))?\s*(?:aed|dhs?|dirhams?)",
    re.IGNORECASE,
)
_ANNUAL_RE = re.compile(r"\b(per\s+annum|annual|annually|yearly|per\s+year|p\.?a\.?)\b", re.IGNORECASE)
_HOURLY_RE = re.compile(r"\b(per\s+hour|hourly|/\s*hr|/\s*hour)\b", re.IGNORECASE)


@dataclass
class RiskAssessment:
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def quarantined(self) -> bool:
        return self.score >= config.QUARANTINE_THRESHOLD

    def add(self, penalty: int, reason: str) -> None:
        self.score += penalty
        self.reasons.append(reason)


def _any(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0)
    return None


def _to_number(s: str) -> float | None:
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def extract_monthly_salary_aed(text: str | None) -> float | None:
    """Return the *upper* bound of the first AED salary figure found, normalised to monthly.

    Returns None when nothing parseable exists (fail-open). Upper bound is deliberate:
    we only reject when even the best case is below the floor.
    """
    if not text:
        return None
    m = _SALARY_RE.search(text)
    if not m:
        return None
    lo, hi = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    values = [v for v in (_to_number(lo), _to_number(hi) if hi else None) if v is not None]
    if not values:
        return None
    amount = max(values)
    window = text[max(0, m.start() - 40): m.end() + 40]
    if _ANNUAL_RE.search(window) or amount >= 40000:
        amount /= 12.0
    elif _HOURLY_RE.search(window) or amount < 500:
        # hourly or an unparseable fragment (e.g. "500 employees"); treat as unknown
        return None
    return amount


def salary_floor_for(location: str | None) -> int:
    loc = (location or "").lower()
    if "remote" in loc:
        return config.SALARY_FLOORS_AED["remote"]
    for key, floor in config.SALARY_FLOORS_AED.items():
        if key in loc:
            return floor
    return config.DEFAULT_SALARY_FLOOR_AED


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def assess(job: dict, *, today: date | None = None, is_repost: bool = False) -> RiskAssessment:
    """Score a job dict. Keys used: title, company, description, location, salary_text, date_posted."""
    today = today or datetime.now(timezone.utc).date()
    title = job.get("title") or ""
    company = job.get("company") or ""
    desc = job.get("description") or ""
    text = f"{title}\n{desc}"
    result = RiskAssessment()

    # 1. Visa traps. Strip explicitly safe phrases first so "Golden Visa" never triggers.
    scrubbed = text
    for safe in VISA_SAFE_PATTERNS:
        scrubbed = re.sub(safe, " ", scrubbed, flags=re.IGNORECASE)
    hit = _any(VISA_TRAP_PATTERNS, scrubbed)
    if hit:
        result.add(config.PENALTY_VISA_TRAP, f"visa trap: '{hit.strip()}'")

    # 2. Wage / commission traps.
    hit = _any(WAGE_TRAP_PATTERNS, text)
    if hit:
        result.add(config.PENALTY_WAGE_TRAP, f"commission/direct-sales: '{hit.strip()}'")
    else:
        salary = extract_monthly_salary_aed(job.get("salary_text")) or extract_monthly_salary_aed(desc)
        if salary is not None:
            floor = salary_floor_for(job.get("location"))
            if floor and salary < floor:
                result.add(
                    config.PENALTY_WAGE_TRAP,
                    f"salary {salary:,.0f} AED/month below floor {floor:,} for {job.get('location') or 'UAE'}",
                )

    # 3. Ghost stagnation.
    posted = _parse_date(job.get("date_posted"))
    if posted is not None and (today - posted).days > config.GHOST_DAYS:
        result.add(config.PENALTY_GHOST, f"stale: posted {(today - posted).days} days ago")
    elif is_repost:
        result.add(config.PENALTY_GHOST, "identical repost of an already-seen posting")

    # 4. Harvesting agencies.
    hit = _any(AGENCY_COMPANY_PATTERNS, company.strip()) or _any(AGENCY_DESC_PATTERNS, desc)
    if hit:
        result.add(config.PENALTY_AGENCY, f"unnamed agency: '{hit.strip()}'")

    return result


def apply_safety_net(jobs: list[dict], *, repost_ids: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Annotate each job with risk_score / risk_reasons / is_ghost. Returns (clean, quarantined)."""
    repost_ids = repost_ids or set()
    clean, quarantined = [], []
    for job in jobs:
        r = assess(job, is_repost=job.get("id") in repost_ids)
        job["risk_score"] = r.score
        job["risk_reasons"] = "; ".join(r.reasons)
        job["is_ghost"] = r.quarantined
        (quarantined if r.quarantined else clean).append(job)
    return clean, quarantined
