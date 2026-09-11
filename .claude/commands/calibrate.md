---
description: Day-1 taste calibration - 5 pairwise A/B job questions in the terminal (Bradley-Terry)
---
Run once, after the first `/ingest` has populated `career.db`.

0. **Pick the candidate (always ask).** Run `.venv/Scripts/python run.py candidate` to list the
   valid names, then ask the user which candidate to calibrate for using a multiple-choice question.
   Run `.venv/Scripts/python run.py candidate set <name>`. State the candidate's display name in your
   reply. Every path below is relative to `candidates/<name>/`.
1. Tell the user this is interactive and they will answer `A`, `B`, or `S` (skip) five times.
2. Suggest they run it themselves so the prompts land in their terminal:
   ```
   ! .venv/Scripts/python run.py calibrate 5
   ```
   (If they prefer, you may run it through Bash, but stdin must be attached to their terminal.)
3. After it finishes, confirm `candidates/<name>/data/taste_profile.json` exists and echo the
   "You lean towards / away from" term lists it printed.
4. Explain that `/evaluate` will now show a `Taste:` score per job and uses it only as a tie-breaker.
   Re-running `/calibrate` later overwrites the profile with a fresh session.
