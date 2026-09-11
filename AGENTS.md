# UAE Autonomous Career Engine

Local, zero-subscription job discovery and screening agent for the UAE market, driven by an AI coding
assistant that can read files and run shell commands (Claude Code, Codex CLI, Cursor, Windsurf, Gemini
CLI, GitHub Copilot agent mode, or similar). The Python side does deterministic work (scraping, dedupe,
scam filtering, optional semantic ranking). **You, the assistant, are the judge**: you read the survivors,
evaluate them against the active candidate's `profile.md`, write the shortlist, and draft cover letters.

This file is the only instruction file. Full design: `SPEC.md`. Setup: `README.md`.

## Triggering a workflow
There are six workflows, defined in full at the bottom of this file: **onboard**, **ingest**,
**calibrate**, **evaluate**, **apply**, **sent**. When the user types a workflow name, with or without a leading
slash and with an optional job ID for apply (`apply 1a2b3c4d5e6f7a8b`), run that workflow step by step.
Wherever a workflow says "ask a multiple-choice question", use your tool's question feature if it has
one; otherwise list the options as text and wait for the answer.

Workflows are decoupled: each one reads its inputs from `candidates/me/` and never assumes another
workflow ran in the same session.

## The candidate folder
Everything about the user lives in `candidates/me/`: `candidate.py` (search terms, salary floors, hull
knobs), `profile.md`, `resume.md`, `data/` (the SQLite database and taste model) and `reports/`. The
onboard workflow creates it. The folder is gitignored in this public repo (only `candidates/_template/`
is tracked); users who want their data synced keep it in a private fork.

The engine can technically hold several such folders and switch between them with
`run.py candidate set <name>`, but that is not part of the normal flow. Never ask the user which
candidate to use; `me` is always active. If a command complains that no candidate is active, run
`.venv/Scripts/python run.py candidate set me` and continue.

## Git steps inside workflows
The ingest, apply and sent workflows contain commit-and-push steps. They exist so a candidate's
database and cover-letter archive stay in sync across devices through a **private** remote. Before
running them, check `git check-ignore -q candidates/me && echo ignored`. If it prints `ignored` (the
default in this public repo), skip every git step and say so in one line. Never work around the ignore
rule with `git add -f`. Cover letters are only ever removed from disk by the sent workflow, and only
when the folder is tracked; in an ignored folder, sent just updates the database and the user tidies
files as they like.

## Environment
- Python venv at `.venv/`. Run scripts as `.venv/Scripts/python run.py <cmd>` on Windows or
  `.venv/bin/python run.py <cmd>` on macOS and Linux. The workflows below write the Windows form;
  substitute on other systems.
- Engine mode toggle: `engine/config.py` -> `MODE = SUPER_SAIYAN_MODE | EFFICIENT_MODE`.
- Database: `candidates/me/data/career.db` (SQLite, table `jobs`). Never edit it by hand; use `run.py` subcommands.
- Tests: `.venv/Scripts/python -m pytest -q`.

## Pipeline
| Phase | Owner | What |
|---|---|---|
| 1 Ingestion | Python | `scrapers/board_scraper.py` (jobspy: LinkedIn/Indeed/Bayt) + `scrapers/ats_direct.py` (Greenhouse/Lever JSON) |
| 2 Safety net | Python | `engine/cleaner.py` (fuzzy dedupe) -> `algorithms/hull.py` (domain box) -> `engine/uae_detector.py` (fail-open scam/ghost scoring, quarantine at risk >= 50) |
| 3 Mode toggle | Python | SUPER_SAIYAN: all survivors to the assistant. EFFICIENT: `engine/semantic_ranker.py` picks top 15 |
| 4 Delivery | **Assistant** | evaluate writes `reports/daily_shortlist.md`; apply writes cover letters; sent records submissions |

## Conventions
- Never invent job data. If a field is missing, say so in the report.
- Keep `reports/daily_shortlist.md` as the single daily briefing per candidate; do not create dated copies.
- Heavy deps (`torch`, `sentence-transformers`) are optional at runtime; the ranker falls back to
  TF-IDF with a warning if they are absent.
- CRITICAL RULES: never name anything under the candidate profile's `## Never name` heading; describe
  those items by scale and function. Never mention the "UAE Autonomous Career Engine", the AI assistant,
  or any automated tools in any application material.
- No Invented Credentials: never hallucinate, guess, or insert specific certification names, exam numbers
  (e.g., AI-102), or course titles unless they are explicitly written inside the candidate's `resume.md`.
  If a posting demands a cert the résumé does not list, pivot the letter to focus entirely on practical,
  hands-on project experience instead of promising to study for a test.

---

# Workflows

## onboard
Interview the user and build a complete candidate folder from their answers. Do NOT scrape or evaluate.

0. **Time check first.** Tell the user the interview has 44 questions in 10 sections and takes roughly
   25 to 40 minutes to answer properly, that the quality of every shortlist and cover letter depends
   on it, that they can type `save and exit` at any point and pick up later where they stopped, and
   that `edit <number>` changes any earlier answer at any time.
   Ask whether they want to do it now. Offer two alternatives if not: (a) come back later, or
   (b) a 10-minute short form where they hand over an existing CV or LinkedIn export and answer only
   sections B, C, D and I below, with the rest extracted from the CV and gaps marked `TODO:`.
   Proceed with whichever they pick.
1. The folder is always `candidates/me/`.
   - If `candidates/me/onboarding_answers.md` exists, this is a resume. Tell them which sections
     are already complete and which question comes next, ask whether to continue from there or start
     over, and continue accordingly.
   - Otherwise, if `candidates/me/` already exists with a finished profile, ask whether to overwrite it.
2. **Save after every reply.** Keep `candidates/me/onboarding_answers.md` as the running record:
   one heading per section (A to J), one `**Qn.**` line per question with the answer beneath it, and a
   `Next: <section letter><question number>` line at the top. Rewrite the file after every user message,
   before asking the next question, so nothing is lost if the session dies. The folder is gitignored, so
   the file never leaves the machine.
3. Ask the questions below section by section, in order, several per message so it does not drag.
   Use multiple-choice questions where options are listed; otherwise ask in plain text. "None" or "not
   applicable" is a valid answer, a blank is not. Ask follow-ups whenever an answer is vague: a cover
   letter can only cite concrete facts, so push for tool names, project scale, dates, numbers and
   outcomes. Never guess or fill a gap yourself.
   - **Editing earlier answers.** At any point the user can say `edit <question number>` (e.g.
     `edit 20`), `change my answer to <topic>`, or `show my answers`. On `show`, print the saved file.
     On an edit, quote the current answer, take the new one, rewrite that entry in
     `onboarding_answers.md` (keeping the `Next:` pointer where it was), confirm the change, and
     return to the question you were on. Do this with as little ceremony as possible; it should feel
     like correcting a form field, not restarting.
   - If at any point the user says `save and exit`, `stop`, `later`, `pause`, or anything equivalent:
     write the file one last time, confirm the path and the next question number, tell them to type
     `onboard` again to resume, and end the workflow without writing the three
     candidate files.
4. After the last section (J), read whatever extra material they give you and use it to enrich the answers.
5. Copy `candidates/_template/` to `candidates/me/` and write the three files from the answers:
   - `candidate.py`: `DISPLAY_NAME`, `SEARCH_TERMS` (8-15 title variants an employer would actually
     post), `SEARCH_LOCATIONS`, `SALARY_FLOORS_AED`, `DEFAULT_SALARY_FLOOR_AED`, `MAX_SENIORITY_LEVEL`,
     `SENIORITY_EXTRA_PATTERNS`, `EXCLUDE_TITLE_KEYWORDS`, `DOMAIN_TRACKS` (2-5 tracks with 5-15
     lowercase keywords each, drawn from the titles and stack they gave), and `ATS_BOARDS` (leave
     empty unless they named companies with public Greenhouse/Lever/Ashby/Workable boards).
   - `profile.md`: follow the template headings exactly. Keep the CRITICAL RULE about years of
     experience and the `## Never name` and `## Deal-breakers` sections; fill them from the answers.
     Add an `## Out of scope` section listing the role types they said they do not want.
   - `resume.md`: follow the template headings. Every bullet must be a concrete, citable fact they
     stated. Mark anything still missing with `TODO:` so apply knows not to rely on it.
6. Show the user all three files and offer a final review: they can correct anything in the generated
   files directly, or say `edit <question number>` to change an answer, in which case update
   `onboarding_answers.md` and regenerate the affected file. Repeat until they confirm.
7. Run `.venv/Scripts/python run.py candidate set me` and confirm the `Candidate: <display name>`
   line. Leave `onboarding_answers.md` in place as the record of what they said. Tell them the next
   step is ingest, then calibrate.

### Onboarding questions
Nationality and date of birth (A4) are only used to judge visa and licence questions; never write them
into a letter.

#### A. Identity and contact
1. Full legal name as it should appear on applications.
2. Email address and phone number with country code.
3. City or area and emirate you live in.
4. Nationality and date of birth (only used to judge visa and licence questions; never written into letters).
5. Links: LinkedIn, portfolio, GitHub, Behance, personal site. Paste each URL or say none.

#### B. Visa, permits and availability
6. Current UAE status: Golden Visa, employment visa, family sponsorship, visit visa, outside the UAE, other. If family or employer sponsored, who sponsors it and is it transferable?
7. Does an employer hiring you need to pay for a residence visa or use a visa quota? What exactly is still required (for example a MOHRE work permit only)?
8. Notice period or earliest start date. Are you already in the UAE with Emirates ID and medical done?
9. Is your degree attested or equivalated in the UAE (MOFA, MOHESR)? State which.
10. Professional registrations you hold or lack that employers ask for (Society of Engineers, municipality approval cards, DHA/DOH licence, teaching licence, CPA, PMP, cloud certificates, and so on). For each: held, in progress, or not eligible yet and why.
11. UAE driving licence: yes, in progress, or no. Own car: yes or no.

#### C. What you are looking for
12. The 3 to 5 role families you want, in priority order, with the exact job titles employers use for each (for example "Junior Architect", "Architectural Draftsman", "BIM Modeler").
13. Role families that look adjacent but you do NOT want (for example interior design, landscape, sales engineering, pure helpdesk). Be explicit; these become hard rejections.
14. Seniority you will accept: intern, junior, mid, senior, lead. Which is the highest you would apply to?
15. Job title words that should always be rejected (for example "solutions architect" for a building architect, "manager" if you do not want people management).
16. Industries or company types you prefer or refuse (consultancy, contractor, developer, agency, startup, government, and so on).
17. Are hybrid and remote roles in scope? Remote only within the UAE, or anywhere?

#### D. Location and money
18. Which emirates can you commute to daily, given where you live and whether you drive?
19. Minimum monthly salary in AED for each: Dubai, Abu Dhabi, Sharjah, Ajman, other emirates, remote. Say what the floor covers (transport, housing) so the numbers make sense.
20. If a posting shows no salary, should it be accepted (recommended) or rejected?
21. Any allowances or arrangements that change the floor (company transport, accommodation, commission on top of base)?

#### E. Education
22. Every degree or diploma: title, major, institution, city and country, graduation date, grade or GPA if strong.
23. Relevant coursework, thesis or graduation project: topic, scale, tools used, any grade or award.
24. Courses, bootcamps and certificates with the issuing body and date. Only ones you actually hold.
25. Academic awards, competitions, scholarships, dean's list.

#### F. Work history (repeat for every job, internship and freelance engagement)
26. Employer name, city, your title, start and end dates, hours or working days if part-time or short.
27. Team and reporting line: who you reported to and what the department did.
28. For each project or engagement you touched: what the building, product or system was, its scale (floors, users, revenue, headcount, square metres), your exact contribution, the tools used, and the outcome (approved, shipped, launched, saved X, delivered on time).
29. Anything measurable: number of drawings, apps shipped, users served, tickets closed, uptime, money saved, percentage improvements.
30. Any client-facing, authority-facing or site-facing work: what you did in front of clients, government reviewers or contractors.

#### G. Skills and tools
31. Every software tool you use professionally, grouped: primary daily tools, competent secondary tools, tools you are currently learning. Be honest about the level; the assistant will match postings to this list.
32. Programming languages, frameworks, platforms or engineering methods, with level (professional, working, basic).
33. Hands-on or field skills (site surveying, lab work, equipment, hardware, vehicles, instruments).
34. Tools you do not know but are willing to pick up on the job; these let the assistant approve postings that list them as "an advantage".
35. Spoken languages with level (native, fluent, conversational, basic). For each, say whether postings that require it are a plus, neutral, or a blocker.

#### H. Personal projects and portfolio
36. Up to five projects that are not part of a job: name, what it does or is, the stack or tools, scale or audience, any award, link if public.
37. Which projects are you proudest of and why? Which should a cover letter lead with?

#### I. How the assistant should pitch you
38. Your three strongest selling points in one sentence each.
39. Your biggest gap versus typical postings (years of experience, missing certificate, no licence) and how you want it framed. The assistant never apologises for a gap; tell it what to offer instead.
40. Sensitive names to never write in a letter (previous employer under NDA, clients, supervisors, specific schools or sites), each with how to describe it by scale and function instead.
41. Claims the assistant must never make about you (for example "no paperwork needed", "holds registration", "willing to relocate abroad").
42. Deal-breakers: commission-only pay, roles that ask you to pay for visas or training, unnamed "confidential client" agencies, shift work, travel, anything else.
43. Tone preferences for letters: plain, formal, warm; British or American spelling; anything you dislike in cover letters.

#### J. Anything else
44. Drop anything that helps: an existing CV or resume in any format, a portfolio PDF, past cover letters, reference letters, a job posting you loved or hated, screenshots of your work, a LinkedIn export, a list of companies you want to target, or notes on things this questionnaire did not ask. The assistant reads all of it and folds it into the three files, and asks before assuming anything the material does not state.

## ingest
Run Phase 1 + Phase 2 of the pipeline. Do NOT evaluate anything.

0. Every path below is relative to `candidates/me/`.
1. Execute `.venv/Scripts/python run.py -v ingest`. It may take several minutes (jobspy hits
   LinkedIn/Indeed/Bayt for every search term × location). If jobspy is rate-limited, re-run with
   `--skip-boards` so at least the direct ATS boards land.
2. Report back exactly:
   - raw scraped, in-batch duplicates, reposts detected
   - hull rejections (how many, and the 3 most common reasons)
   - **total clean ingested**, **total quarantined** (with the top 5 quarantine reasons)
   - jobs now pending evaluate
3. If quarantine looks wrong for a specific job (e.g. "Golden Visa" flagged), show the offending
   `risk_reasons` line and suggest the regex fix in `engine/uae_detector.py`. Do not apply it unasked.
4. **Commit and push (private forks only).** First run `git check-ignore -q candidates/me && echo ignored`.
   If it prints `ignored`, skip this step and say so in one line. Otherwise run:
   ```
   git add -A
   git commit -m "Ingest <YYYY-MM-DD>: <N> clean, <M> quarantined"
   git push
   ```
   Confirm the push succeeded in your report. When the folder is tracked, this is mandatory after every
   ingest, partial or not.

## calibrate
Run once per candidate, after the first ingest has populated `career.db`.

0. Every path below is relative to `candidates/me/`.
1. Tell the user this is interactive and they will answer `A`, `B`, or `S` (skip) five times.
2. Suggest they run `.venv/Scripts/python run.py calibrate 5` themselves so the prompts land in their
   terminal (in Claude Code, prefix it with `!`). If they prefer, you may run it, but stdin must be
   attached to their terminal.
3. After it finishes, confirm `candidates/me/data/taste_profile.json` exists and echo the
   "You lean towards / away from" term lists it printed.
4. Explain that evaluate will now show a `Taste:` score per job and uses it only as a tie-breaker.
   Re-running calibrate later overwrites the profile with a fresh session.

## evaluate
You are the judge. Follow these steps exactly.

0. Every path below is relative to `candidates/me/`.
1. Run `.venv/Scripts/python run.py pending`. The output is mode-aware
   (`engine/config.py` MODE): SUPER_SAIYAN prints every survivor; EFFICIENT prints the top 15 by
   local semantic similarity. Do not re-rank or re-filter the batch yourself.
2. Read the candidate's `profile.md`. Evaluate every job in the batch. Apply these rules without exception:
   - Years of experience are NOT a hard blocker. 2-4 years requested with a matching stack = approve.
     Reject on experience only for 6+ years AND an explicit leadership/architect scope.
   - Salary floors from the profile's table apply only if a salary is stated. No salary = acceptable.
   - Remote roles are in scope only if the profile says so.
   - The profile's `## Out of scope` and `## Deal-breakers` sections are hard rejections.
   - Use the `Taste:` score, if present, only to break ties.
   - Vocabulary mismatch is not a rejection reason: "Deep Learning" satisfies "Machine Learning",
     "TypeScript/Next.js" satisfies "React", etc.
3. Overwrite `candidates/me/reports/daily_shortlist.md` with:
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
   Include the profile's Strategic Advantage angle in "Why" whenever the posting mentions visa,
   sponsorship, or "must be in UAE".
4. Persist decisions so tomorrow's run does not repeat them:
   ```
   .venv/Scripts/python run.py shortlist <ID> <ID> ...
   .venv/Scripts/python run.py evaluated <remaining IDs from the "IDs in this batch" line>
   ```
5. Reply with the shortlist table and the command to apply to the top pick: `apply <ID>`.

## apply <ID>
Write a hyper-targeted cover letter for one job and mark it applied.

0. Every path below is relative to `candidates/me/`.
1. Run `.venv/Scripts/python run.py show <ID>`. If it reports an unknown id, stop and say so.
2. Read the candidate's `resume.md` and `profile.md`.
3. Write `candidates/me/reports/cover_letters/YYYY-MM-DD-<job-id>-<company-slug>.md` (using
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
4. Run `.venv/Scripts/python run.py applied <ID>` (one ID per call) and confirm the status is now `applied`.
5. **Commit and push (private forks only). Keep the letter on disk.** First run
   `git check-ignore -q candidates/me && echo ignored`. If it prints `ignored`, skip this step and say
   so in one line. Otherwise run:
   ```
   git add -A
   git commit -m "Apply <ID>: <company> - <title>"
   git push
   ```
   Do NOT delete or skip-worktree the letter: `applied` only means the letter is written. The user sends
   it from the local folder and then runs the sent workflow. Never commit a deletion of a cover letter.
6. Reply with the file path and the full letter text.

## sent
Record which cover letters the user has actually submitted. Run only after the user says they sent them.

0. Every path below is relative to `candidates/me/`.
1. Run `.venv/Scripts/python run.py letters`. It lists every cover letter on disk with its job ID, status
   and company. If it prints "No cover letters on disk", say so and stop.
2. Ask the user which of the listed letters they have sent, as a multi-select question with one option
   per letter (company and title) plus "All of them".
3. For the chosen IDs run `.venv/Scripts/python run.py sent <ID> <ID> ...` and confirm each line shows
   `-> sent`.
4. **Archive (private forks only).** Run `git check-ignore -q candidates/me && echo ignored`. If it prints
   `ignored`, stop here; the database is updated and the files stay as they are. Otherwise:
   ```
   git add candidates/me/data/career.db
   git commit -m "Sent <ID> [<ID> ...]: <N> applications submitted"
   git push
   git update-index --skip-worktree candidates/me/reports/cover_letters/<file>
   rm candidates/me/reports/cover_letters/<file>
   ```
   Repeat the last two lines per sent letter. Unticked letters stay on disk. Never commit a deletion of
   a cover letter.
5. Reply with what was marked sent, what is still waiting, and the applied-versus-sent counts from
   `.venv/Scripts/python run.py stats`.
