# UAE Autonomous Career Engine

A local, zero-subscription job discovery and screening agent for the UAE market, driven by whatever AI
coding assistant you already use (Claude Code, Codex CLI, Cursor, Windsurf, Gemini CLI, Copilot agent
mode). Python does the deterministic work (scraping LinkedIn, Indeed, Bayt and direct ATS boards; fuzzy
dedupe; a scam and ghost-job safety net; optional semantic ranking). The assistant does the judging: it
reads every surviving posting against your `profile.md`, writes a ranked daily shortlist, and drafts a
targeted cover letter for each job you choose.

It supports several candidates in one checkout, one active at a time, and works for tech and
non-tech fields alike (the per-candidate knobs decide what counts as "in domain").

Full design notes are in `SPEC.md`. Every rule and workflow the assistant follows is in one file, `AGENTS.md`.

## Requirements

- Windows, macOS or Linux with Python 3.11 or newer (developed on 3.12).
- An AI coding assistant that can read files and run shell commands in the repo folder.
  [Claude Code](https://claude.com/claude-code) and the others read the same `AGENTS.md`; see "Which assistant" below. There is no other UI.
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

3. **Create your candidate folder.** Open your AI assistant in the repo folder and type `onboard`.
   It first tells you how long the interview takes and asks whether you want to do it now, then walks
   you through the questions section by section (identity, visa status, target roles, salary floors,
   education, work history, tools, projects, how to pitch you) and asks for any CV, portfolio or links
   you already have. Your answers are saved after every reply, so you can type `save and exit` at any
   point and run `onboard` again later to continue. At the end it writes the three candidate files and
   activates the candidate.

   The manual way: copy the template and rename it to a short lowercase slug.

   ```
   cp -r candidates/_template candidates/<name>
   ```

   Either way, the folder ends up with three files:

   | File | What it is | Who reads it |
   |---|---|---|
   | `candidate.py` | Search terms, locations, salary floors, seniority cap, domain keyword tracks, direct ATS boards | Python (scraper and hull filter) |
   | `profile.md` | Your focus areas, stack, languages, location and salary table, strategic advantage, things never to name, deal-breakers | the assistant, during evaluate and apply |
   | `resume.md` | Concrete achievements with tools and metrics | the assistant, during apply (the only source of claims a cover letter may make) |

   Every placeholder is wrapped in `<angle brackets>`. Replace all of them. The assistant will refuse to invent
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

   - `SUPER_SAIYAN_MODE` (default): every posting that survives the safety net goes to the assistant.
     Best coverage, more tokens. Suits a generous plan (for example Claude Max).
   - `EFFICIENT_MODE`: a local SentenceTransformer ranks survivors against `profile.md` and only the top 15
     go to the assistant. Suits a tighter plan (for example Claude Pro).

6. **Run the tests** to confirm the install:

   ```
   .venv/Scripts/python -m pytest -q
   ```

## Daily workflow

Open your AI assistant in the repo folder and type a workflow name (a leading slash is fine too). Each one asks which candidate to run
for, then works only inside that candidate's folder.

| Command | What happens |
|---|---|
| `onboard` | Run once per person. Interviews you, builds `candidates/<name>/` from the answers, and activates it. |
| `ingest` | Scrapes every search term × location, dedupes, applies the domain hull and the scam/ghost safety net, stores clean jobs in `candidates/<name>/data/career.db`. Takes several minutes. |
| `calibrate` | Run once after your first ingest. Five pairwise A/B questions in the terminal teach a Bradley-Terry taste model that later acts as a tie-breaker. |
| `evaluate` | The assistant reads every pending job against `profile.md` and writes `candidates/<name>/reports/daily_shortlist.md`, a ranked table with fit scores, one-line reasons and risks, plus a rejected list. Decisions are persisted so nothing is re-read tomorrow. |
| `apply <ID>` | The assistant reads the posting, `resume.md` and `profile.md`, then writes a sub-350-word cover letter to `candidates/<name>/reports/cover_letters/` and marks the job applied. |

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
5. **Judgement**: the assistant, guided by `profile.md`. Years of experience are never a hard blocker on their own.

## Which assistant

Everything the assistant needs is in one file, `AGENTS.md`: the rules, the pipeline, and the five
workflows written out step by step. Most tools read it on their own.

| Tool | Reads `AGENTS.md` automatically? | What to do |
|---|---|---|
| Codex CLI, Cursor, Windsurf, Copilot agent mode, most others | Yes | Nothing. Type a workflow name. |
| Claude Code | Through `CLAUDE.md`, a one-line file that imports `AGENTS.md` | Nothing. Type a workflow name; `/onboard` style also works. |
| Gemini CLI | No (it looks for `GEMINI.md`) | Either start the session with "Read `AGENTS.md` and follow it", or set `context.fileName` to `AGENTS.md` in `.gemini/settings.json`. |
| Anything else | No | Start the session with: "Read `AGENTS.md` and follow it. When I type a workflow name, run that workflow." |
| Ollama (free, local) | Depends on the agent | See "Free option: Ollama" below. |

The assistant must be able to read files and run shell commands in the repo folder; a plain chat window
cannot drive the engine. Wherever a workflow says to ask a multiple-choice question, tools without a
question feature list the options as text and wait. The commit-and-push steps inside `ingest` and `apply`
skip themselves when your candidate folder is gitignored, which is the default here; they only run if you
keep your data in a private fork.

## Free option: Ollama

Nothing in the engine calls a paid API. Scraping and filtering are plain Python, and the judging is done
by whichever coding agent sits in the repo folder. So a fully free setup is: a local model served by
[Ollama](https://ollama.com), driven by an open-source agent that can read files and run commands. Expect
weaker judgement than a frontier model; the steps below are tuned to make that gap as small as possible.

### 1. Hardware reality check

| Machine | Model to pull | Batch setting |
|---|---|---|
| 16 GB RAM, no GPU, or an 8 GB GPU | `qwen3:8b` or `qwen2.5-coder:7b` | EFFICIENT mode, `EFFICIENT_TOP_N = 8` |
| 16 GB+ GPU or 32 GB unified memory (Apple Silicon) | `gpt-oss:20b` or `qwen3:14b` | EFFICIENT mode, `EFFICIENT_TOP_N = 15` (default) |
| 24 GB+ GPU or 64 GB unified memory | `qwen3:32b` or `qwen2.5-coder:32b` | EFFICIENT mode, or SUPER_SAIYAN for small ingests |

Pick a model that is tuned for tool calling. The workflows need the model to run `run.py` commands and
write files, not just chat. The models above all support tools in Ollama.

### 2. Install Ollama and pull a model

Windows and macOS: download the installer from https://ollama.com/download. Linux:

```
curl -fsSL https://ollama.com/install.sh | sh
```

Then pull the model for your machine, for example:

```
ollama pull gpt-oss:20b
```

### 3. Raise the context window

Ollama's default context is small (4K tokens). One job posting is 500 to 1,500 tokens and the evaluate
workflow hands the agent a batch of them plus `profile.md`, so the model needs at least 32K. Set it
once as an environment variable before the Ollama server starts:

Windows (PowerShell, then restart Ollama from the tray icon):
```
[System.Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH", "32768", "User")
```
macOS / Linux (add to your shell profile, then restart the server):
```
export OLLAMA_CONTEXT_LENGTH=32768
```

Verify with `ollama run gpt-oss:20b` and type `/show parameters`; you should see the new context length.
Larger contexts use more memory, so drop back to 16384 if the model fails to load.

### 4. Switch the engine to EFFICIENT mode

Open `engine/config.py` and change:

```
MODE = EFFICIENT_MODE
EFFICIENT_TOP_N = 15      # lower it for smaller models, see the table above
```

EFFICIENT mode ranks every survivor locally with a small SentenceTransformer and only sends the top N to
the model. It needs `torch` and `sentence-transformers` from `requirements.txt`; if they are missing it
falls back to TF-IDF ranking, which still works but is cruder.

### 5. Install an agent that talks to Ollama

**Option A: Codex CLI (simplest).** OpenAI's open-source coding agent has a built-in Ollama mode and reads
`AGENTS.md` automatically.

```
npm install -g @openai/codex
cd JobSearchEngine
codex --oss -m gpt-oss:20b
```

`--oss` points Codex at your local Ollama server instead of OpenAI; `-m` picks the model you pulled.
Inside Codex, type `onboard`, then later `ingest`, `evaluate`, `apply <ID>` exactly as the workflow
table above describes.

**Option B: OpenCode.** Also open source, also reads `AGENTS.md`, and lets you name any Ollama model.
Install it from https://opencode.ai, then create `opencode.json` in the repo folder:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": { "baseURL": "http://localhost:11434/v1" },
      "models": { "gpt-oss:20b": { "name": "gpt-oss 20b" } }
    }
  },
  "model": "ollama/gpt-oss:20b"
}
```

Run `opencode` in the repo folder and type the workflow names. Other agents with Ollama support (Aider,
Cline, Continue, Goose) work the same way once they can read files and run shell commands; if one does
not pick up `AGENTS.md` by itself, start the session with "Read `AGENTS.md` and follow it."

### 6. Run it

```
onboard          # once: builds candidates/<name>/ from your answers
ingest           # daily: several minutes of scraping, no model involved
calibrate        # once, after the first ingest
evaluate         # daily: the local model judges the top N
apply <ID>       # per job you choose
```

### What to watch with a local model

- **Read every letter before sending it.** Small models are more likely to invent a certificate or name
  something from the never-name list. The rules in `AGENTS.md` forbid both, but enforcement is only as
  good as the model.
- **If evaluate stalls or truncates,** lower `EFFICIENT_TOP_N` or raise `OLLAMA_CONTEXT_LENGTH`.
- **If the agent refuses to run commands,** the model probably lacks tool support. Switch to one of the
  models in the table.
- **Speed.** A 20B model on a mid-range GPU evaluates 15 jobs in a few minutes; on CPU alone, expect
  much longer. Ingest speed is unaffected because it never touches the model.

## Privacy

- `candidates/*` is gitignored except `_template/`. Check `git status` before your first push to a public
  remote.
- Cover letters name real companies and contain your contact details. Keep them in a private remote.
- The engine never submits applications. It writes letters; you send them.

## Adding a second person

Copy `candidates/_template/` again under a new name and fill it in. The two candidates share nothing:
separate database, reports, taste model and hull knobs. Switch with `run.py candidate set <name>`.
