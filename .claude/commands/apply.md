---
description: Write a hyper-targeted cover letter for job $ARGUMENTS and mark it applied
argument-hint: <job ID from the shortlist>
---
Target job ID: `$ARGUMENTS`

0. **Pick the candidate (always ask).** Run `.venv/Scripts/python run.py candidate` to list the
   valid names, then ask the user which candidate to apply for using a multiple-choice question.
   Run `.venv/Scripts/python run.py candidate set <name>`. State the candidate's display name in your
   reply. Every path below is relative to `candidates/<name>/`.
1. Run `.venv/Scripts/python run.py show $ARGUMENTS`. If it reports an unknown id, stop and say so.
2. Read the candidate's `resume.md` and `profile.md`.
3. Write `candidates/<name>/reports/cover_letters/YYYY-MM-DD-<job-id>-<company-slug>.md` (using
   today's date, the full job ID, and lower-kebab-case company name). The file MUST start with this
   exact header block:
   ```markdown
   # Cover Letter - {Company Name}

   **Role:** {Exact Job Title}, {Location}
   **Job ID (career.db):** {ID}
   **Posting:** {URL}

   ---
   ```
   Then the letter itself. Structure, max 350 words (header excluded):
   - **Hook (2-3 sentences):** something specific from the posting or company. No "I am writing to apply".
   - **Stack match (1 paragraph):** map each required technology or skill to a concrete résumé item
     (internship, freelance client, project). Name the items; do not list skills generically.
   - **Experience bridge (1 paragraph, only if the posting asks for more years than the candidate has):**
     state plainly that tenure is shorter, then show breadth, shipped outcomes, and the adaptability
     stated in the profile. Never apologise.
   - **Strategic Advantage (its own paragraph, aggressive):** pitch the `## Strategic Advantage`
     section of the candidate's `profile.md`. Use only claims that section makes. Quantify the
     employer's saving in time if the posting mentions visa/sponsorship.
   - **CTA (1-2 sentences):** propose a short technical conversation this week.
   - **Guardrails:** never name anything listed under `## Never name` in the candidate's
     `profile.md`; describe those items by scale and function instead. Never mention automated or
     AI tooling used to find or write the application. Never invent certifications, exam numbers, or
     course titles that are not written in `resume.md`.
4. Run `.venv/Scripts/python run.py applied $ARGUMENTS` and confirm the status is now `applied`.
5. **Commit, push, then remove the letter locally (private forks only).** First run
   `git check-ignore -q candidates/<name> && echo ignored`. If it prints `ignored`, skip this step, leave the
   letter on disk, and say so in one line. Otherwise run:
   ```
   git add -A
   git commit -m "Apply <name>/$ARGUMENTS: <company> - <title>"
   git push
   git update-index --skip-worktree candidates/<name>/reports/cover_letters/<file>
   rm candidates/<name>/reports/cover_letters/<file>
   ```
   Confirm the push succeeded and the local file is gone in your reply. The skip-worktree flag stops
   git from staging the deletion, so the letter stays on GitHub while the local folder stays empty.
   Never commit a deletion of a cover letter. When the folder is tracked, this is mandatory after every apply.
6. Reply with the file path and the full letter text.
