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

3. **Create your candidate folder.** The easy way: open Claude Code in the repo and run `/onboard`.
   It interviews you with the questionnaire below, section by section, then writes the three candidate
   files from your answers and activates the candidate. You can also paste the whole questionnaire
   into Claude with your answers, or answer it in a text file and hand Claude the path.

   The manual way: copy the template and rename it to a short lowercase slug.

   ```
   cp -r candidates/_template candidates/<name>
   ```

   Either way, the folder ends up with three files:

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

## Onboarding questionnaire

This is what `/onboard` asks. Answer every line; "none" or "not applicable" is a valid answer, a
blank is not. Claude writes `candidate.py`, `profile.md` and `resume.md` from these answers and nothing
else, so anything you leave out cannot appear in a cover letter.

### A. Identity and contact
1. Full legal name as it should appear on applications.
2. Short folder slug (lowercase, no spaces).
3. Email address and phone number with country code.
4. City or area and emirate you live in.
5. Nationality and date of birth (only used to judge visa and licence questions; never written into letters).
6. Links: LinkedIn, portfolio, GitHub, Behance, personal site. Paste each URL or say none.

### B. Visa, permits and availability
7. Current UAE status: Golden Visa, employment visa, family sponsorship, visit visa, outside the UAE, other. If family or employer sponsored, who sponsors it and is it transferable?
8. Does an employer hiring you need to pay for a residence visa or use a visa quota? What exactly is still required (for example a MOHRE work permit only)?
9. Notice period or earliest start date. Are you already in the UAE with Emirates ID and medical done?
10. Is your degree attested or equivalated in the UAE (MOFA, MOHESR)? State which.
11. Professional registrations you hold or lack that employers ask for (Society of Engineers, municipality approval cards, DHA/DOH licence, teaching licence, CPA, PMP, cloud certificates, and so on). For each: held, in progress, or not eligible yet and why.
12. UAE driving licence: yes, in progress, or no. Own car: yes or no.

### C. What you are looking for
13. The 3 to 5 role families you want, in priority order, with the exact job titles employers use for each (for example "Junior Architect", "Architectural Draftsman", "BIM Modeler").
14. Role families that look adjacent but you do NOT want (for example interior design, landscape, sales engineering, pure helpdesk). Be explicit; these become hard rejections.
15. Seniority you will accept: intern, junior, mid, senior, lead. Which is the highest you would apply to?
16. Job title words that should always be rejected (for example "solutions architect" for a building architect, "manager" if you do not want people management).
17. Industries or company types you prefer or refuse (consultancy, contractor, developer, agency, startup, government, and so on).
18. Are hybrid and remote roles in scope? Remote only within the UAE, or anywhere?

### D. Location and money
19. Which emirates can you commute to daily, given where you live and whether you drive?
20. Minimum monthly salary in AED for each: Dubai, Abu Dhabi, Sharjah, Ajman, other emirates, remote. Say what the floor covers (transport, housing) so the numbers make sense.
21. If a posting shows no salary, should it be accepted (recommended) or rejected?
22. Any allowances or arrangements that change the floor (company transport, accommodation, commission on top of base)?

### E. Education
23. Every degree or diploma: title, major, institution, city and country, graduation date, grade or GPA if strong.
24. Relevant coursework, thesis or graduation project: topic, scale, tools used, any grade or award.
25. Courses, bootcamps and certificates with the issuing body and date. Only ones you actually hold.
26. Academic awards, competitions, scholarships, dean's list.

### F. Work history (repeat for every job, internship and freelance engagement)
27. Employer name, city, your title, start and end dates, hours or working days if part-time or short.
28. Team and reporting line: who you reported to and what the department did.
29. For each project or engagement you touched: what the building, product or system was, its scale (floors, users, revenue, headcount, square metres), your exact contribution, the tools used, and the outcome (approved, shipped, launched, saved X, delivered on time).
30. Anything measurable: number of drawings, apps shipped, users served, tickets closed, uptime, money saved, percentage improvements.
31. Any client-facing, authority-facing or site-facing work: what you did in front of clients, government reviewers or contractors.

### G. Skills and tools
32. Every software tool you use professionally, grouped: primary daily tools, competent secondary tools, tools you are currently learning. Be honest about the level; Claude will match postings to this list.
33. Programming languages, frameworks, platforms or engineering methods, with level (professional, working, basic).
34. Hands-on or field skills (site surveying, lab work, equipment, hardware, vehicles, instruments).
35. Tools you do not know but are willing to pick up on the job; these let Claude approve postings that list them as "an advantage".
36. Spoken languages with level (native, fluent, conversational, basic). For each, say whether postings that require it are a plus, neutral, or a blocker.

### H. Personal projects and portfolio
37. Up to five projects that are not part of a job: name, what it does or is, the stack or tools, scale or audience, any award, link if public.
38. Which projects are you proudest of and why? Which should a cover letter lead with?

### I. How Claude should pitch you
39. Your three strongest selling points in one sentence each.
40. Your biggest gap versus typical postings (years of experience, missing certificate, no licence) and how you want it framed. Claude never apologises for a gap; tell it what to offer instead.
41. Sensitive names to never write in a letter (previous employer under NDA, clients, supervisors, specific schools or sites), each with how to describe it by scale and function instead.
42. Claims Claude must never make about you (for example "no paperwork needed", "holds registration", "willing to relocate abroad").
43. Deal-breakers: commission-only pay, roles that ask you to pay for visas or training, unnamed "confidential client" agencies, shift work, travel, anything else.
44. Tone preferences for letters: plain, formal, warm; British or American spelling; anything you dislike in cover letters.

### J. Anything else
45. Drop anything that helps: an existing CV or resume in any format, a portfolio PDF, past cover letters, reference letters, a job posting you loved or hated, screenshots of your work, a LinkedIn export, a list of companies you want to target, or notes on things this questionnaire did not ask. Claude reads all of it and folds it into the three files, and asks before assuming anything the material does not state.

## Daily workflow

Open Claude Code in the repo folder and use the slash commands. Each one asks which candidate to run
for, then works only inside that candidate's folder.

| Command | What happens |
|---|---|
| `/onboard` | Run once per person. Interviews you with the questionnaire above, builds `candidates/<name>/` from the answers, and activates it. |
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
