"""Filled in by the onboard workflow into candidates/me/. Uppercase names override engine/config.py."""

DISPLAY_NAME = "<Full Name>"

SEARCH_TERMS = ["<job title 1>", "<job title 2>"]
SEARCH_LOCATIONS = ["Dubai, UAE", "Abu Dhabi, UAE", "Sharjah, UAE"]

# Direct ATS boards. Leave empty if none apply to this candidate's field.
ATS_BOARDS: dict[str, list[str]] = {}

SALARY_FLOORS_AED = {"abu dhabi": 0, "dubai": 0, "sharjah": 0, "ajman": 0, "remote": 0}
DEFAULT_SALARY_FLOOR_AED = 0

# 0 intern, 1 junior, 2 mid, 3 senior, 4 lead/principal. Jobs above this are rejected.
MAX_SENIORITY_LEVEL = 3
# Tech candidates keep {4: [r"\barchitect\b"]}; architecture candidates set {}.
SENIORITY_EXTRA_PATTERNS: dict[int, list[str]] = {}
# Titles containing any of these are rejected outright.
EXCLUDE_TITLE_KEYWORDS: list[str] = []

# At least one keyword from one track must appear in the title (or 3 in the description).
DOMAIN_TRACKS = {"<track>": ["<keyword>", "<keyword>"]}

# Optional: regex for off-domain titles. Omit to inherit the tech default.
# NON_TECH_TITLE_PATTERN = r"\b(sales|marketing)\b"
