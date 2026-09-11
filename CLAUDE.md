# UAE Autonomous Career Engine

Local, zero-subscription job discovery and screening agent for the UAE market, running
natively inside Claude Code. The Python side does deterministic work (scraping, dedupe, scam
filtering, optional semantic ranking). **You, Claude, are the judge**: you read the survivors,
evaluate them against the active candidate's `profile.md`, write the shortlist, and draft cover letters.

Full design: `SPEC.md`. Setup: `README.md`.

## Candidates
The engine runs for one candidate at a time. Each lives in `candidates/<name>/` with `candidate.py`
(search terms, salary floors, hull knobs), `profile.md`, `resume.md`, `data/`, and `reports/`. The
active candidate is stored per machine in `.active_candidate` (gitignored). `run.py candidate` shows
it, `run.py candidate set <name>` changes it, and `--candidate <name>` overrides it for one run.
Every `run.py` command prints `Candidate: <display name>` as its first line; check it.
Every slash command always asks which candidate before doing anything. To add a
person, copy `candidates/_template/`. Real candidate folders are gitignored in this public repo (only `_template/` is tracked); keep your own data in a private fork or a private remote.

## Environment
- Python venv at `.venv/`. Always run scripts as `.venv/Scripts/python run.py <cmd>` (Windows).
- Engine mode toggle: `engine/config.py` -> `MODE = SUPER_SAIYAN_MODE | EFFICIENT_MODE`.
- Database: `candidates/<name>/data/career.db` (SQLite, table `jobs`). Never edit it by hand; use `run.py` subcommands.
- Tests: `.venv/Scripts/python -m pytest -q`.

## Pipeline
| Phase | Owner | What |
|---|---|---|
| 1 Ingestion | Python | `scrapers/board_scraper.py` (jobspy: LinkedIn/Indeed/Bayt) + `scrapers/ats_direct.py` (Greenhouse/Lever JSON) |
| 2 Safety net | Python | `engine/cleaner.py` (fuzzy dedupe) -> `algorithms/hull.py` (domain box) -> `engine/uae_detector.py` (fail-open scam/ghost scoring, quarantine at risk >= 50) |
| 3 Mode toggle | Python | SUPER_SAIYAN: all survivors to Claude. EFFICIENT: `engine/semantic_ranker.py` picks top 15 |
| 4 Delivery | **Claude** | `/evaluate` writes `reports/daily_shortlist.md`; `/apply` writes cover letters |

## Slash commands (see `.claude/commands/`)
Commands are decoupled: each one asks which candidate, reads its inputs from that candidate's `career.db`,
and never assumes another command ran in the same session. Paths below are relative to `candidates/<name>/`.

### `/onboard`  (run once per new person, before anything else)
0. Ask for a folder slug, then interview the user with the questionnaire in `README.md`, section by section.
1. Ask for extra material (existing CV, portfolio, LinkedIn, GitHub) and fold it in.
2. Copy `candidates/_template/` to `candidates/<slug>/`, write `candidate.py`, `profile.md`, `resume.md` from the answers only, mark gaps `TODO-<SLUG>:`, show the files for confirmation, then `run.py candidate set <slug>`.

### `/ingest`
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `.venv/Scripts/python run.py ingest` (add `-v` for per-job reasons).
2. Report the final line: total ingested, quarantined, and pending evaluation. Do not evaluate.
3. **Commit and push after every ingest.** Stage `data/career.db` plus anything else changed and
   commit with `Ingest <name> YYYY-MM-DD: N clean, M quarantined`, then `git push`. This keeps
   the database in sync across devices. Do not skip this step even if the scrape was partial.

### `/evaluate`
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `.venv/Scripts/python run.py pending`. The script already honours `engine/config.py` MODE
   (EFFICIENT ranks with SentenceTransformers and returns only the top 15). Do not re-rank.
2. Read `profile.md`. Evaluate **every** job in the output against it. Rules:
   - **Years of experience are NOT a blocker.** A few years asked + matching stack = approve.
   - Salary floors from the profile's table apply only when a salary is stated. No salary = acceptable.
   - Use `Taste:` score (if present) as a tie-breaker, never as the primary signal.
   - Remote roles are in scope only if the profile says so.
3. Write `reports/daily_shortlist.md` (overwrite; it is wiped daily) with: candidate, date, mode, count
   evaluated, then a ranked table of the top matches (ID, title, company, location, fit 1-10,
   one-line why, one-line risk), followed by a short "Rejected" list with a 5-word reason each.
4. Persist decisions: `run.py shortlist <ID>...` for picks, `run.py evaluated <ID>...` for the rest.
   Use the "IDs in this batch" line from step 1 so nothing is re-evaluated tomorrow.

### `/calibrate`  (run once per candidate, after their first `/ingest`)
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `.venv/Scripts/python run.py calibrate 5`. It is interactive: the user answers A/B/S in the terminal.
2. Confirm `data/taste_profile.json` exists and echo the "lean towards / away from" terms.

### `/apply [ID]`
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `.venv/Scripts/python run.py show <ID>` and read `resume.md` + `profile.md`.
2. Write `reports/cover_letters/YYYY-MM-DD-<job-id>-<company-slug>.md`. The letter MUST:
   - Open with a specific hook about the company/product from the posting, not a template line.
   - **Aggressively pitch the profile's `## Strategic Advantage` section** as a named paragraph, not a
     footnote, using only the claims that section makes.
   - **Bridge any years-of-experience gap** explicitly: map the posting's required stack to concrete
     items in `resume.md` (internship, freelance, projects) and frame breadth + adaptability as the
     substitute for tenure. Never apologise for the gap.
   - Stay under 350 words, plain professional tone, no buzzword padding, end with a clear CTA.
3. Run `.venv/Scripts/python run.py applied <ID>` and confirm the status change.
4. **Commit, push, then remove the letter locally.** Stage the new cover letter and `data/career.db`,
   commit with `Apply <name>/<ID>: <company> - <title>`, and `git push`. Then flag the letter with
   `git update-index --skip-worktree <file>` and delete it from disk. GitHub is the archive for every
   letter; the local folder stays empty. Never commit a deletion of a cover letter. To read an old
   letter, use `git show origin/main:candidates/<name>/reports/cover_letters/<file>`.

## Conventions
- Never invent job data. If a field is missing, say so in the report.
- Keep `reports/daily_shortlist.md` as the single daily briefing per candidate; do not create dated copies.
- Heavy deps (`torch`, `sentence-transformers`) are optional at runtime; the ranker falls back to
  TF-IDF with a warning if they are absent.
- CRITICAL RULES: never name anything under the candidate profile's `## Never name` heading; describe
  those items by scale and function. Never mention the "UAE Autonomous Career Engine", Claude Code, or
  any automated tools in any application material.
- No Invented Credentials: Never hallucinate, guess, or insert specific certification names, exam numbers
  (e.g., AI-102), or course titles unless they are explicitly written inside the candidate's `resume.md`.
  If a posting demands a cert the résumé does not list, pivot the letter to focus entirely on practical,
  hands-on project experience instead of promising to study for a test.
