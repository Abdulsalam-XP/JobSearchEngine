# UAE Autonomous Career Engine

A local, zero-subscription job discovery and screening agent for the UAE market that runs inside
[Claude Code](https://claude.com/claude-code). Python does the deterministic work (scraping LinkedIn,
Indeed, Bayt and direct ATS boards; fuzzy dedupe; a scam and ghost-job safety net; optional semantic
ranking). Claude does the judging: it reads every surviving posting against your `profile.md`, writes a
ranked daily shortlist, and drafts a targeted cover letter for each job you choose.

It supports several candidates in one checkout, one active at a time, and works for tech and
non-tech fields alike (the per-candidate knobs decide what counts as "in domain").

Full design notes are in `SPEC.md`. The operating rules Claude follows are in `CLAUDE.md` and the
slash commands in `.claude/commands/`.

## Requirements

- Windows, macOS or Linux with Python 3.11 or newer (developed on 3.12).
- [Claude Code](https://claude.com/claude-code) installed and signed in. The engine is driven by its
  slash commands; there is no other UI.
- Git.
- Optional: about 2 GB of disk for `torch` and `sentence-transformers` if you want EFFICIENT mode. Without
  them the ranker falls back to TF-IDF with a warning and everything still works.

## Setup

1. **Fork or clone.** Everything under `candidates/` except `_template/` is gitignored, so your profile,
   resume, database and cover letters never leave your machine unless you push them to a remote you
   control. If you want your data synced across devices, make a **private** fork and commit inside it.

   ```
   git clone https://github.com/<you>/JobSearchEngine.git
   cd JobSearchEngine
   ```

2. **Create the virtual environment and install dependencies.**

   Windows:
   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
   macOS / Linux:
   ```
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
   `torch` and `sentence-transformers` are the heavy entries in `requirements.txt`. Remove those two lines
   before installing if you only intend to use SUPER_SAIYAN mode.

3. **Create your candidate folder.** Copy the template and rename it to a short lowercase slug.

   ```
   cp -r candidates/_template candidates/<name>
   ```

   Then fill in the three files inside it:

   | File | What it is | Who reads it |
   |---|---|---|
   | `candidate.py` | Search terms, locations, salary floors, seniority cap, domain keyword tracks, direct ATS boards | Python (scraper and hull filter) |
   | `profile.md` | Your focus areas, stack, languages, location and salary table, strategic advantage, things never to name, deal-breakers | Claude, during `/evaluate` and `/apply` |
   | `resume.md` | Concrete achievements with tools and metrics | Claude, during `/apply` (the only source of claims a cover letter may make) |

   Every placeholder is wrapped in `<angle brackets>`. Replace all of them. Claude will refuse to invent
   credentials or achievements that are not in `resume.md`, so the more concrete that file is, the better
   the letters.

4. **Activate the candidate.**

   ```
   .venv/Scripts/python run.py candidate set <name>      # Windows
   .venv/bin/python run.py candidate set <name>          # macOS / Linux
   ```

   The active name is stored in a gitignored `.active_candidate` file, so each machine can have its own.
   Every command prints `Candidate: <display name>` as its first line; check it.

5. **Pick an engine mode** in `engine/config.py`:

   - `SUPER_SAIYAN_MODE` (default): every posting that survives the safety net goes to Claude. Best
     coverage, more tokens. Suits a Claude Max plan.
   - `EFFICIENT_MODE`: a local SentenceTransformer ranks survivors against `profile.md` and only the top 15
     go to Claude. Suits a Claude Pro plan.

6. **Run the tests** to confirm the install:

   ```
   .venv/Scripts/python -m pytest -q
   ```

## Daily workflow

Open Claude Code in the repo folder and use the slash commands. Each one asks which candidate to run
for, then works only inside that candidate's folder.

| Command | What happens |
|---|---|
| `/ingest` | Scrapes every search term × location, dedupes, applies the domain hull and the scam/ghost safety net, stores clean jobs in `candidates/<name>/data/career.db`. Takes several minutes. |
| `/calibrate` | Run once after your first ingest. Five pairwise A/B questions in the terminal teach a Bradley-Terry taste model that later acts as a tie-breaker. |
| `/evaluate` | Claude reads every pending job against `profile.md` and writes `candidates/<name>/reports/daily_shortlist.md`, a ranked table with fit scores, one-line reasons and risks, plus a rejected list. Decisions are persisted so nothing is re-read tomorrow. |
| `/apply <ID>` | Claude reads the posting, `resume.md` and `profile.md`, then writes a sub-350-word cover letter to `candidates/<name>/reports/cover_letters/` and marks the job applied. |

Underneath, everything is `run.py` subcommands, so you can also drive it by hand:

```
python run.py ingest                 scrape -> dedupe -> hull -> safety net -> career.db
python run.py pending                print un-evaluated survivors as Markdown (mode-aware)
python run.py calibrate [N]          interactive Bradley-Terry taste session
python run.py show <ID>              print one job in full
python run.py shortlist <ID> [...]   mark as shortlisted
python run.py evaluated <ID> [...]   mark as evaluated without shortlisting
python run.py applied <ID>           mark as applied
python run.py stats                  database counters
python run.py candidate [set NAME]   show or change the active candidate
```

Add `-v` before the subcommand for per-job reasons, or `--candidate NAME` to override the active
candidate for one run.

## How the filtering works

1. **Ingestion**: `scrapers/board_scraper.py` (python-jobspy) plus `scrapers/ats_direct.py` (Greenhouse,
   Lever, Ashby and Workable public JSON endpoints).
2. **Dedupe**: `engine/cleaner.py` fuzzy-matches title and company to collapse reposts.
3. **Hull**: `algorithms/hull.py` keeps only UAE or remote locations, titles inside your
   `DOMAIN_TRACKS`, and seniority at or below `MAX_SENIORITY_LEVEL`.
4. **Safety net**: `engine/uae_detector.py` scores visa-fee traps, sub-floor wages, commission-only roles,
   unnamed agencies and ghost postings. Anything at risk 50 or above is quarantined, never deleted. It
   fails open: no salary listed means acceptable.
5. **Judgement**: Claude, guided by `profile.md`. Years of experience are never a hard blocker on their own.

## Privacy

- `candidates/*` is gitignored except `_template/`. Check `git status` before your first push to a public
  remote.
- Cover letters name real companies and contain your contact details. Keep them in a private remote.
- The engine never submits applications. It writes letters; you send them.

## Adding a second person

Copy `candidates/_template/` again under a new name and fill it in. The two candidates share nothing:
separate database, reports, taste model and hull knobs. Switch with `run.py candidate set <name>`.
