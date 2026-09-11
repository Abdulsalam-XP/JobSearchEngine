# SPECIFICATION: UAE AUTONOMOUS CAREER ENGINE (Claude Code Native)

## 1. Project Background & Inspiration
This project is an autonomous, local job discovery and screening agent engineered specifically for the **UAE tech market** (Dubai, Abu Dhabi, Sharjah, UAE-Remote). 

**Architectural Lineage:**
1. **Reddit Concept (`r/ClaudeCode - elliottdehn/open-jobs`)**: Inspired by Elliott Dehn's system of feeding pre-scraped ATS jobs into Claude Code via an `AGENTS.md` interface, utilizing Bradley-Terry pairwise comparisons to learn candidate taste without resorting to automated spam bots.
2. **Pinloop (`pinloop-cli` & `pinloop.ai`)**: Modeled after Pinloop's orchestration framework, which uses CLI tooling and skill injection to pull direct ATS postings and employs Claude as a multi-stage judge to eliminate ghost jobs.

**Objective:** Build a zero-subscription (100% free external tools) evaluation engine running natively inside Claude Code CLI. It is personalised per candidate through `candidates/<name>/profile.md`; the original build targeted a Junior/Mid Full-Stack & AI Engineer, and the same engine now runs for non-tech candidates (e.g. architecture) through per-candidate knobs.

---

## 2. The Dual-Mode Execution Pipeline
To solve the "Vocabulary Mismatch Problem" without burning unnecessary tokens, the engine features a configurable execution toggle, allowing the user to switch modes based on their Claude Plan (Pro vs. Max).

**Phase 1: Raw Ingestion** (Scrapes ~200 UAE tech jobs via JobSpy and direct ATS).
**Phase 2: The Safety Net** (Deterministic, Fail-Open blocklist drops the 120 obvious scams, unlisted agencies, and SQLite duplicates).

**Phase 3: The Engine Mode Toggle (Configurable via `engine/config.py`)**
* **Option A: `SUPER_SAIYAN_MODE` (Full LLM Fidelity)**
  Bypasses local sorting. Hands all 80 surviving jobs directly to Claude Code. Claude reads every single listing, ensuring absolutely zero legitimate jobs are missed due to keyword mismatch. (Recommended for Claude Max tier).
* **Option B: `EFFICIENT_MODE` (Local Semantic AI)**
  Uses HuggingFace `SentenceTransformers` (`all-MiniLM-L6-v2`) running locally on the CPU. It computes the semantic cosine similarity between the job descriptions and `profile.md`. It understands that "Machine Learning" equals "Deep Learning." It sorts the 80 jobs by semantic meaning, and only passes the Top 15 to Claude for final evaluation. (Recommended for Claude Pro tier).

**Phase 4: Agentic Delivery** (Claude writes the dashboard and generates targeted cover letters).

---

## 3. Algorithms & Math Models

### A. The Convex Hull Filter (`algorithms/hull.py`)
Establishes a loose geometric bounding box of the candidate's eligible domain to prevent scraping irrelevant domains.
`Hull(J) = {j in J | Loc(j) in UAE AND Seniority(j) <= MaxLevel AND Track(j) intersect Domain != empty}`

### B. Pairwise Preference Learning (`algorithms/taste_model.py`)
To calibrate the user's initial taste without arbitrary 0-100 scoring:
- Uses the Bradley-Terry Probabilistic Ranking model: `P(i > j) = sigmoid(w^T * (x_i - x_j))`
- The agent presents 5-10 terminal prompts: "Job A vs Job B: Which do you prefer?"
- It extracts TF-IDF features, uses Active Learning to find pairs with maximum uncertainty, and learns the user's taste weight vector (`w`), storing it in `data/taste_profile.json`.

---

## 4. UAE-Specific Scam Detection & Safety Net (`engine/uae_detector.py`)
Implements a strict blocklist using a "Fail-Open" philosophy: A job is innocent until explicitly proven guilty. If data is missing or ambiguous, it survives to Phase 3. 
If `RiskScore >= 50`, the job is flagged as `quarantine`.

1. **Illegal Visa Traps (Penalty: 60):** Regex detects employers illegally charging candidates (`"visa charges"`, `"pay for visa"`, `"visa deposit"`). 
   *CRITICAL RULE:* Do NOT penalize jobs asking for "Golden Visa", "Spouse Visa", or "NOC". The candidate has a Golden Visa, which is a massive advantage.
2. **Sub-Market Wage / Commission Traps (Penalty: 70):** Flags `"commission only"`, `"direct sales"`, or anything explicitly listed below the candidate's floor. (If no salary is listed, fail-open and approve).
3. **Ghost Stagnation (Penalty: 40):** Active on job boards for >40 days or detected as an identical repost.
4. **Third-Party Harvesting Agency (Penalty: 35):** Postings from unnamed generic headhunters (`"confidential client"`, `"leading recruitment agency"`).

---

## 5. Candidate Profile Injection (`profile.md`)
The system must generate `profile.md` with these exact parameters:
- **Core Focus:** Full-Stack Web Development, QA/Automation, and AI/Machine Learning.
- **Tech Stack Flexibility:** Proficient in Python, C++, JavaScript, Java, TypeScript, React, React Native, Convex. Highly adaptable (willing to learn Go, Rust, etc., on the job).
- **Experience Philosophy:** Junior/Mid-level (Graduate + 4mo Internship + Freelance). 
  *CRITICAL CLAUDE RULE:* Do not treat "years of experience" as a hard blocker. If a job asks for 2-4 years but the core tech stack aligns, approve it. 
- **Location & Salary Floors:** 
  - Abu Dhabi (On-site/Hybrid): Minimum 8,000 AED
  - Dubai (On-site/Hybrid): Minimum 6,000 AED
  - Sharjah/Ajman (On-site/Hybrid): Minimum 5,000 AED
  - Remote: Anywhere globally accepted.
- **Strategic Advantage:** Holds a UAE Golden Visa (No MOHRE quota, no corporate sponsorship fees, immediate start).

---

## 6. Directory & File Architecture

```text
uae-career-engine/
├── CLAUDE.md                   # Agent system execution loop & slash commands
├── profile.md                  # Candidate technical profile & constraints
├── resume.md                   # Candidate Markdown resume
├── data/
│   ├── career.db               # SQLite database with state tracking
│   └── taste_profile.json      # Learned Bradley-Terry weight vector
├── scrapers/
│   ├── board_scraper.py        # python-jobspy (LinkedIn AE, Indeed AE, Bayt)
│   └── ats_direct.py           # Direct JSON endpoints for UAE tech companies
├── algorithms/
│   ├── hull.py                 # Loose candidate boundary generator
│   └── taste_model.py          # Bradley-Terry active learner & ranker
├── engine/
│   ├── config.py               # Holds SUPER_SAIYAN_MODE vs EFFICIENT_MODE toggle
│   ├── db.py                   # SQLite schema, migrations, hashing
│   ├── cleaner.py              # Fuzzy deduplication (Levenshtein) & normalization
│   ├── uae_detector.py         # UAE market red-flag & regex heuristics
│   └── semantic_ranker.py      # SentenceTransformers semantic CPU sorter (Option B)
├── reports/
│   ├── daily_shortlist.md      # Auto-wiped daily briefing output
│   └── cover_letters/          # Directory for generated applications
└── requirements.txt