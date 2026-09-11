"""Central configuration for the UAE Career Engine.

Flip MODE to switch between the two Phase-3 strategies:

  SUPER_SAIYAN_MODE  - every surviving job goes to Claude (Claude Max).
  EFFICIENT_MODE     - local SentenceTransformers ranks first, top N go to Claude (Claude Pro).
"""
from pathlib import Path

SUPER_SAIYAN_MODE = "SUPER_SAIYAN"
EFFICIENT_MODE = "EFFICIENT"

# >>> THE TOGGLE <<<
MODE = SUPER_SAIYAN_MODE

# How many jobs EFFICIENT_MODE forwards to Claude for final evaluation.
EFFICIENT_TOP_N = 15

# Local embedding model used by engine/semantic_ranker.py (runs on CPU).
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "career.db"
TASTE_PROFILE_PATH = DATA_DIR / "taste_profile.json"
PROFILE_PATH = ROOT / "profile.md"
RESUME_PATH = ROOT / "resume.md"
REPORTS_DIR = ROOT / "reports"
SHORTLIST_PATH = REPORTS_DIR / "daily_shortlist.md"
COVER_LETTER_DIR = REPORTS_DIR / "cover_letters"

# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
SEARCH_TERMS = [
    "software engineer",
    "full stack developer",
    "frontend developer",
    "backend developer",
    "react developer",
    "python developer",
    "machine learning engineer",
    "AI engineer",
    "QA automation engineer",
    "react native developer",
    "IT support",
    "system administrator",
    "IT operations",
]
SEARCH_LOCATIONS = ["Dubai, UAE", "Abu Dhabi, UAE", "Sharjah, UAE"]
JOBSPY_SITES = ["linkedin", "indeed", "bayt", "google"]
RESULTS_PER_SEARCH = 60
JOBSPY_HOURS_OLD = 72  # look back far enough to detect ghost jobs

# Direct ATS boards (free public JSON endpoints). Slugs below were verified live on 2026-09-07.
# Only postings whose location mentions the UAE / remote are kept, so global boards are safe to list.
ATS_BOARDS = {
    "greenhouse": ["careem", "tamara", "kitchenpark", "binance", "bybit", "okx", "bitpanda", "noon", "talabat", "anghami", "swvl", "tabby", "kitopi"],
    "lever": ["derq", "trukkr"],
    "ashby": ["deliveroo", "ziina", "rain", "leantech", "vivid", "posthog", "tldraw"],
    "workable": ["invygo", "syarah"],
}

# ---------------------------------------------------------------------------
# Candidate constraints (mirrors profile.md)
# ---------------------------------------------------------------------------
SALARY_FLOORS_AED = {
    "abu dhabi": 8000,
    "dubai": 6000,
    "sharjah": 5000,
    "ajman": 5000,
    "remote": 0,
}
DEFAULT_SALARY_FLOOR_AED = 5000

# ---------------------------------------------------------------------------
# Safety net (engine/uae_detector.py)
# ---------------------------------------------------------------------------
QUARANTINE_THRESHOLD = 50
GHOST_DAYS = 40
PENALTY_VISA_TRAP = 60
PENALTY_WAGE_TRAP = 70
PENALTY_GHOST = 40
PENALTY_AGENCY = 35

# ---------------------------------------------------------------------------
# Deduplication (engine/cleaner.py)
# ---------------------------------------------------------------------------
FUZZY_DUPLICATE_THRESHOLD = 90

# ---------------------------------------------------------------------------
# Hull (algorithms/hull.py)
# ---------------------------------------------------------------------------
UAE_LOCATION_KEYWORDS = [
    "uae", "united arab emirates", "dubai", "abu dhabi", "sharjah", "ajman",
    "ras al khaimah", "fujairah", "umm al quwain", "al ain", "remote",
]
MAX_SENIORITY_LEVEL = 3  # 0=intern, 1=junior, 2=mid, 3=senior, 4=lead/principal. Senior kept: title inflation is common.
DOMAIN_TRACKS = {
    "fullstack": ["full stack", "full-stack", "fullstack", "web developer", "software engineer",
                  "software developer", "frontend", "front-end", "front end", "backend", "back-end",
                  "back end", "react", "node", "typescript", "javascript", "python", "java", "c++",
                  "react native", "mobile"],
    "qa": ["qa", "quality assurance", "test automation", "automation engineer", "sdet", "tester"],
    "ai": ["machine learning", "deep learning", "ai engineer", "artificial intelligence", "data scientist",
           "nlp", "computer vision", "llm", "mlops"],
    # General IT / Microsoft-stack operations roles (highly desirable, added 2026-09-07).
    "it_ops": ["it support", "it engineer", "it specialist", "it technician", "it administrator", "it officer",
               "it executive", "it operations", "it ops", "system administrator", "systems administrator",
               "sysadmin", "system engineer", "systems engineer", "desktop support", "service desk",
               "help desk", "helpdesk", "technical support", "network administrator", "infrastructure engineer",
               "active directory", "microsoft 365", "office 365", "m365", "windows server", "intune", "azure ad",
               "entra", "sccm", "exchange online", "sharepoint"],
}

# ---------------------------------------------------------------------------
# Per-candidate knobs (shared defaults; a candidate.py may override any of them)
# ---------------------------------------------------------------------------
DISPLAY_NAME = "(shared defaults, no candidate loaded)"
# Titles containing any of these phrases are rejected by the hull before track matching.
EXCLUDE_TITLE_KEYWORDS: list[str] = []
# Regex source: titles matching this are rejected unless a domain track keyword is also in the title.
NON_TECH_TITLE_PATTERN = (
    r"\b(sales|marketing|accountant|accounting|receptionist|driver|nurse|teacher|chef|cashier|"
    r"telecaller|telesales|real estate|property consultant|customer service|hr |recruiter|"
    r"security guard|cleaner|barista|waiter|waitress)\b"
)
# Extra seniority patterns merged into algorithms/hull.py SENIORITY_LEVELS. Tech candidates treat
# "architect" as a lead-tier title; an architecture candidate sets this to {}.
SENIORITY_EXTRA_PATTERNS: dict[int, list[str]] = {4: [r"\barchitect\b"]}

# ---------------------------------------------------------------------------
# Candidate workspaces
# ---------------------------------------------------------------------------
CANDIDATES_DIR = ROOT / "candidates"
ACTIVE_FILE = ROOT / ".active_candidate"
CANDIDATE_NAME: str | None = None
CANDIDATE_DIR: Path | None = None


class NoActiveCandidate(RuntimeError):
    """No --candidate flag, CANDIDATE env var, or .active_candidate file."""


class UnknownCandidate(RuntimeError):
    """The requested candidate folder does not exist or lacks candidate.py."""


def list_candidates(candidates_dir: Path | None = None) -> list[str]:
    base = Path(candidates_dir or CANDIDATES_DIR)
    if not base.is_dir():
        return []
    return sorted(
        p.name for p in base.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "candidate.py").is_file()
    )


def _validate_name(name: str, candidates_dir: Path | None) -> str:
    valid = list_candidates(candidates_dir)
    if name not in valid:
        raise UnknownCandidate(f"unknown candidate {name!r}; valid: {', '.join(valid) or '(none)'}")
    return name


def resolve_candidate_name(
    explicit: str | None = None, *, candidates_dir: Path | None = None, active_file: Path | None = None
) -> str:
    import os

    if explicit:
        return _validate_name(explicit, candidates_dir)
    env = os.environ.get("CANDIDATE", "").strip()
    if env:
        return _validate_name(env, candidates_dir)
    af = Path(active_file or ACTIVE_FILE)
    if af.is_file():
        stored = af.read_text(encoding="utf-8").strip()
        if stored:
            return _validate_name(stored, candidates_dir)
    raise NoActiveCandidate(
        "no active candidate: pass --candidate NAME, set CANDIDATE, or run `run.py candidate set NAME`"
    )


def set_active_candidate(name: str, *, candidates_dir: Path | None = None, active_file: Path | None = None) -> None:
    _validate_name(name, candidates_dir)
    Path(active_file or ACTIVE_FILE).write_text(name + "\n", encoding="utf-8")


def load_candidate(
    name: str | None = None, *, candidates_dir: Path | None = None, active_file: Path | None = None
) -> str:
    """Overlay candidates/<name>/candidate.py onto this module and point all paths at that folder."""
    import importlib.util
    import sys as _sys

    base = Path(candidates_dir or CANDIDATES_DIR)
    resolved = resolve_candidate_name(name, candidates_dir=base, active_file=active_file)
    cdir = base / resolved

    spec = importlib.util.spec_from_file_location(f"candidate_{resolved}", cdir / "candidate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    me = _sys.modules[__name__]
    for key, value in vars(module).items():
        if key.isupper() and not key.startswith("_"):
            setattr(me, key, value)

    me.CANDIDATE_NAME = resolved
    me.CANDIDATE_DIR = cdir
    me.DATA_DIR = cdir / "data"
    me.DB_PATH = me.DATA_DIR / "career.db"
    me.TASTE_PROFILE_PATH = me.DATA_DIR / "taste_profile.json"
    me.PROFILE_PATH = cdir / "profile.md"
    me.RESUME_PATH = cdir / "resume.md"
    me.REPORTS_DIR = cdir / "reports"
    me.SHORTLIST_PATH = me.REPORTS_DIR / "daily_shortlist.md"
    me.COVER_LETTER_DIR = me.REPORTS_DIR / "cover_letters"
    me.DATA_DIR.mkdir(parents=True, exist_ok=True)
    me.COVER_LETTER_DIR.mkdir(parents=True, exist_ok=True)
    return resolved
