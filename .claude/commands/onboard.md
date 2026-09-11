Interview the user and build a complete candidate folder from their answers. Do NOT scrape or evaluate.

0. Ask for a short lowercase slug for the folder name (letters, digits, hyphens; e.g. `sara`). If
   `candidates/<slug>/` already exists, ask whether to overwrite it or pick another name.
1. Ask every question in the **Onboarding questionnaire** section of `README.md`, section by section,
   in order. Use multiple-choice questions where the README offers options; otherwise ask in plain text.
   Ask follow-ups whenever an answer is vague: a cover letter can only cite concrete facts, so push for
   tool names, project scale, dates, numbers and outcomes. Never guess or fill a gap yourself.
2. After the last section, ask for any extra material: an existing CV or resume (any format, pasted or
   as a file path), a portfolio or LinkedIn or GitHub link, certificates, past cover letters, or anything
   they think matters. Read whatever they give you and use it to enrich the answers.
3. Copy `candidates/_template/` to `candidates/<slug>/` and write the three files from the answers:
   - `candidate.py`: `DISPLAY_NAME`, `SEARCH_TERMS` (8-15 title variants an employer would actually
     post), `SEARCH_LOCATIONS`, `SALARY_FLOORS_AED`, `DEFAULT_SALARY_FLOOR_AED`, `MAX_SENIORITY_LEVEL`,
     `SENIORITY_EXTRA_PATTERNS`, `EXCLUDE_TITLE_KEYWORDS`, `DOMAIN_TRACKS` (2-5 tracks with 5-15
     lowercase keywords each, drawn from the titles and stack they gave), and `ATS_BOARDS` (leave
     empty unless they named companies with public Greenhouse/Lever/Ashby/Workable boards).
   - `profile.md`: follow the template headings exactly. Keep the CRITICAL RULE about years of experience and the
     `## Never name` and `## Deal-breakers` sections; fill them from the answers. Add an
     `## Out of scope` section listing the role types they said they do not want.
   - `resume.md`: follow the template headings. Every bullet must be a concrete, citable fact they
     stated. Mark anything still missing with `TODO-<SLUG>:` so `/apply` knows not to rely on it.
4. Show the user all three files and ask them to confirm or correct. Apply corrections.
5. Run `.venv/Scripts/python run.py candidate set <slug>` (or `.venv/bin/python` on macOS/Linux) and
   confirm the `Candidate: <display name>` line. Tell them the next step is `/ingest`, then `/calibrate`.
