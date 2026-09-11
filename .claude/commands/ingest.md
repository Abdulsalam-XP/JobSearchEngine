---
description: Scrape UAE tech jobs, dedupe, apply the scam/ghost safety net, store clean jobs in career.db
---
Run Phase 1 + Phase 2 of the pipeline. Do NOT evaluate anything.

0. **Pick the candidate (always ask).** Run `.venv/Scripts/python run.py candidate` to list the
   valid names, then ask the user which candidate to ingest for using a multiple-choice question.
   Run `.venv/Scripts/python run.py candidate set <name>`. Every later step runs for that candidate
   and every path below is relative to `candidates/<name>/`.
1. Execute:
   ```
   .venv/Scripts/python run.py ingest -v
   ```
   It may take several minutes (jobspy hits LinkedIn/Indeed/Bayt for every search term × location).
   If jobspy is rate-limited, re-run with `--skip-boards` so at least the direct ATS boards land.
2. Report back exactly:
   - raw scraped, in-batch duplicates, reposts detected
   - hull rejections (how many, and the 3 most common reasons)
   - **total clean ingested**, **total quarantined** (with the top 5 quarantine reasons)
   - jobs now pending `/evaluate`
3. If quarantine looks wrong for a specific job (e.g. "Golden Visa" flagged), show the offending
   `risk_reasons` line and suggest the regex fix in `engine/uae_detector.py`. Do not apply it unasked.
4. **Commit and push (private forks only).** First run `git check-ignore -q candidates/<name> && echo ignored`.
   If it prints `ignored`, skip this step and say so in one line. Otherwise run:
   ```
   git add -A
   git commit -m "Ingest <name> <YYYY-MM-DD>: <N> clean, <M> quarantined"
   git push
   ```
   Confirm the push succeeded in your report. When the folder is tracked, this is mandatory after every ingest, partial or not.
