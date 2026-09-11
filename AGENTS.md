# UAE Autonomous Career Engine

Local, zero-subscription job discovery and screening agent for the UAE market, driven by an AI coding
assistant that can read files and run shell commands (Claude Code, Codex CLI, Cursor, Windsurf, Gemini
CLI, GitHub Copilot agent mode, or similar). The Python side does deterministic work (scraping, dedupe,
scam filtering, optional semantic ranking). **You, the assistant, are the judge**: you read the survivors,
evaluate them against the active candidate's `profile.md`, write the shortlist, and draft cover letters.

Full design: `SPEC.md`. Setup: `README.md`.

## Workflows and how to trigger them
The five workflows are written as step-by-step files in `.claude/commands/`:
`onboard.md`, `ingest.md`, `calibrate.md`, `evaluate.md`, `apply.md`.

- In Claude Code they are slash commands: `/onboard`, `/ingest`, `/calibrate`, `/evaluate`, `/apply <ID>`.
- In any other tool there are no slash commands. When the user says `onboard`, `ingest`, `calibrate`,
  `evaluate`, or `apply <ID>` (with or without a leading slash), open the matching file in
  `.claude/commands/` and follow it step by step. Wherever a file says "ask a multiple-choice question",
  list the options in plain text and wait for the answer.
- Where a workflow says `.venv/Scripts/python`, use `.venv/bin/python` on macOS and Linux.

Workflows are decoupled: each one asks which candidate, reads its inputs from that candidate's `career.db`,
and never assumes another workflow ran in the same session.

## Candidates
The engine runs for one candidate at a time. Each lives in `candidates/<name>/` with `candidate.py`
(search terms, salary floors, hull knobs), `profile.md`, `resume.md`, `data/`, and `reports/`. The
active candidate is stored per machine in `.active_candidate` (gitignored). `run.py candidate` shows
it, `run.py candidate set <name>` changes it, and `--candidate <name>` overrides it for one run.
Every `run.py` command prints `Candidate: <display name>` as its first line; check it.
Every workflow always asks which candidate before doing anything. To add a person, run the onboard
workflow or copy `candidates/_template/`. Real candidate folders are gitignored in this public repo
(only `_template/` is tracked); users who want their data synced keep it in a private fork or remote.

## Git steps inside workflows
The ingest and apply workflows contain commit-and-push steps. They exist so a candidate's database and
cover-letter archive stay in sync across devices through a **private** remote. Before running them,
check `git check-ignore -q candidates/<name> && echo ignored`. If the folder is ignored (the default in
this public repo), skip every git step, say so in one line, and leave the cover letter on disk instead of
deleting it. Never work around the ignore rule with `git add -f`.

## Environment
- Python venv at `.venv/`. Run scripts as `.venv/Scripts/python run.py <cmd>` (Windows) or
  `.venv/bin/python run.py <cmd>` (macOS/Linux).
- Engine mode toggle: `engine/config.py` -> `MODE = SUPER_SAIYAN_MODE | EFFICIENT_MODE`.
- Database: `candidates/<name>/data/career.db` (SQLite, table `jobs`). Never edit it by hand; use `run.py` subcommands.
- Tests: `.venv/Scripts/python -m pytest -q`.

## Pipeline
| Phase | Owner | What |
|---|---|---|
| 1 Ingestion | Python | `scrapers/board_scraper.py` (jobspy: LinkedIn/Indeed/Bayt) + `scrapers/ats_direct.py` (Greenhouse/Lever JSON) |
| 2 Safety net | Python | `engine/cleaner.py` (fuzzy dedupe) -> `algorithms/hull.py` (domain box) -> `engine/uae_detector.py` (fail-open scam/ghost scoring, quarantine at risk >= 50) |
| 3 Mode toggle | Python | SUPER_SAIYAN: all survivors to the assistant. EFFICIENT: `engine/semantic_ranker.py` picks top 15 |
| 4 Delivery | **Assistant** | evaluate writes `reports/daily_shortlist.md`; apply writes cover letters |

## Workflow summaries (the files in `.claude/commands/` are authoritative)
Paths below are relative to `candidates/<name>/`.

### onboard  (run once per new person, before anything else)
0. Ask for a folder slug, then interview the user with the questionnaire in `README.md`, section by section.
1. Ask for extra material (existing CV, portfolio, LinkedIn, GitHub) and fold it in.
2. Copy `candidates/_template/` to `candidates/<slug>/`, write `candidate.py`, `profile.md`, `resume.md` from the answers only, mark gaps `TODO-<SLUG>:`, show the files for confirmation, then `run.py candidate set <slug>`.

### ingest
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `run.py ingest` (add `-v` before `ingest` for per-job reasons).
2. Report the final line: total ingested, quarantined, and pending evaluation. Do not evaluate.
3. Git sync (only if the candidate folder is not gitignored, see above): stage `data/career.db` plus
   anything else changed, commit `Ingest <name> YYYY-MM-DD: N clean, M quarantined`, then `git push`.

### evaluate
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `run.py pending`. The script already honours `engine/config.py` MODE
   (EFFICIENT ranks with SentenceTransformers and returns only the top 15). Do not re-rank.
2. Read `profile.md`. Evaluate **every** job in the output against it. Rules:
   - **Years of experience are NOT a blocker.** A few years asked + matching stack = approve.
   - Salary floors from the profile's table apply only when a salary is stated. No salary = acceptable.
   - Use `Taste:` score (if present) as a tie-breaker, never as the primary signal.
   - Remote roles are in scope only if the profile says so.
   - Respect the profile's `## Out of scope` and `## Deal-breakers` sections as hard rejections.
3. Write `reports/daily_shortlist.md` (overwrite; it is wiped daily) with: candidate, date, mode, count
   evaluated, then a ranked table of the top matches (ID, title, company, location, fit 1-10,
   one-line why, one-line risk), followed by a short "Rejected" list with a 5-word reason each.
4. Persist decisions: `run.py shortlist <ID>...` for picks, `run.py evaluated <ID>...` for the rest.
   Use the "IDs in this batch" line from step 1 so nothing is re-evaluated tomorrow.

### calibrate  (run once per candidate, after their first ingest)
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `run.py calibrate 5`. It is interactive: the user answers A/B/S in the terminal.
2. Confirm `data/taste_profile.json` exists and echo the "lean towards / away from" terms.

### apply <ID>
0. Always ask which candidate (multiple choice), then `run.py candidate set <name>`.
1. Run `run.py show <ID>` and read `resume.md` + `profile.md`.
2. Write `reports/cover_letters/YYYY-MM-DD-<job-id>-<company-slug>.md`. The letter MUST:
   - Open with a specific hook about the company/product from the posting, not a template line.
   - **Aggressively pitch the profile's `## Strategic Advantage` section** as a named paragraph, not a
     footnote, using only the claims that section makes.
   - **Bridge any years-of-experience gap** explicitly: map the posting's required stack to concrete
     items in `resume.md` (internship, freelance, projects) and frame breadth + adaptability as the
     substitute for tenure. Never apologise for the gap.
   - Stay under 350 words, plain professional tone, no buzzword padding, end with a clear CTA.
3. Run `run.py applied <ID>` (one ID per call) and confirm the status change.
4. Git sync (only if the candidate folder is not gitignored, see above): stage the new cover letter and
   `data/career.db`, commit `Apply <name>/<ID>: <company> - <title>`, `git push`, then flag the letter
   with `git update-index --skip-worktree <file>` and delete it from disk so the remote is the archive.
   Never commit a deletion of a cover letter. To read an old letter, use
   `git show origin/main:candidates/<name>/reports/cover_letters/<file>`.

## Conventions
- Never invent job data. If a field is missing, say so in the report.
- Keep `reports/daily_shortlist.md` as the single daily briefing per candidate; do not create dated copies.
- Heavy deps (`torch`, `sentence-transformers`) are optional at runtime; the ranker falls back to
  TF-IDF with a warning if they are absent.
- CRITICAL RULES: never name anything under the candidate profile's `## Never name` heading; describe
  those items by scale and function. Never mention the "UAE Autonomous Career Engine", the AI assistant,
  or any automated tools in any application material.
- No Invented Credentials: Never hallucinate, guess, or insert specific certification names, exam numbers
  (e.g., AI-102), or course titles unless they are explicitly written inside the candidate's `resume.md`.
  If a posting demands a cert the résumé does not list, pivot the letter to focus entirely on practical,
  hands-on project experience instead of promising to study for a test.
