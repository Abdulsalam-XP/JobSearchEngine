---
description: Evaluate un-evaluated survivors in career.db against profile.md and write reports/daily_shortlist.md
---
You are the judge. Follow these steps exactly.

0. **Pick the candidate (always ask).** Run `.venv/Scripts/python run.py candidate` to list the
   valid names, then ask the user which candidate to evaluate for using a multiple-choice question.
   Run `.venv/Scripts/python run.py candidate set <name>`. State the candidate's display name in your
   reply. Every path below is relative to `candidates/<name>/`.
1. Run `.venv/Scripts/python run.py pending`. The output is mode-aware
   (`engine/config.py` MODE): SUPER_SAIYAN prints every survivor; EFFICIENT prints the top 15 by
   local semantic similarity. Do not re-rank or re-filter the batch yourself.
2. Read the candidate's `profile.md`. Evaluate every job in the batch. Apply these rules without exception:
   - Years of experience are NOT a hard blocker. 2-4 years requested with a matching stack = approve.
     Reject on experience only for 6+ years AND an explicit leadership/architect scope.
   - Salary floors from the profile's table apply only if a salary is stated.
   - Remote roles are in scope only if the profile says so.
   - Use the `Taste:` score, if present, only to break ties.
   - Vocabulary mismatch is not a rejection reason: "Deep Learning" satisfies "Machine Learning",
     "TypeScript/Next.js" satisfies "React", etc.
3. Overwrite `candidates/<name>/reports/daily_shortlist.md` with:
   ```
   # Daily Shortlist - <YYYY-MM-DD>
   Candidate: <display name>
   Mode: <SUPER_SAIYAN|EFFICIENT> | Evaluated: <n> | Shortlisted: <k>

   ## Top matches
   | # | ID | Title | Company | Location | Fit /10 | Why | Risk |
   ...

   ## Rejected
   - <ID> <Title> @ <Company>: <≤5-word reason>
   ```
   Include the profile's Strategic Advantage angle in "Why" whenever the posting mentions visa, sponsorship, or
   "must be in UAE".
4. Persist decisions so tomorrow's run does not repeat them:
   ```
   .venv/Scripts/python run.py shortlist <ID> <ID> ...
   .venv/Scripts/python run.py evaluated <remaining IDs from the "IDs in this batch" line>
   ```
5. Reply with the shortlist table and the command to apply to the top pick: `/apply <ID>`.
