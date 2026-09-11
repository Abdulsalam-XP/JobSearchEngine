"""Command-line entry point used by the AI assistant workflows in AGENTS.md.

    python run.py ingest                 scrape -> dedupe -> hull -> safety net -> career.db
    python run.py pending                print un-evaluated survivors as Markdown (mode-aware)
    python run.py calibrate [N]          interactive Bradley-Terry taste session
    python run.py show <ID>              print one job in full (for /apply)
    python run.py shortlist <ID> [...]   mark as shortlisted (+ evaluated)
    python run.py evaluated <ID> [...]   mark as evaluated without shortlisting
    python run.py applied <ID>           mark as applied (letter written)
    python run.py sent <ID> [...]        mark as sent (letter actually submitted)
    python run.py letters                list cover letters on disk with their job status
    python run.py stats                  database counters
    python run.py wipe-shortlist         reset reports/daily_shortlist.md
    python run.py candidate              show the active candidate and the valid names
    python run.py candidate set NAME     make NAME the active candidate on this machine

Every command accepts --candidate NAME to override the active candidate for one run.
"""
from __future__ import annotations

import argparse
import re
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Windows consoles default to cp1252; job descriptions carry emoji and smart quotes.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

from engine import config, db  # noqa: E402

log = logging.getLogger("engine")


# --------------------------------------------------------------------------- ingest
def cmd_ingest(args) -> int:
    from algorithms import hull
    from engine import cleaner, uae_detector
    from scrapers import ats_direct, board_scraper

    db.init_db()
    raw: list[dict] = []
    if not args.skip_boards:
        raw += board_scraper.scrape()
    if not args.skip_ats:
        raw += ats_direct.scrape()
    print(f"Phase 1  raw scraped            : {len(raw)}")

    unique, reposts, dropped = cleaner.dedupe(raw, existing=db.known_titles())
    print(f"Phase 2a dedupe                 : {len(unique)} unique  ({dropped} in-batch dupes, {len(reposts)} reposts)")

    inside, rejected = hull.filter_hull(unique)
    print(f"Phase 2b hull filter            : {len(inside)} inside  ({len(rejected)} outside domain)")
    if args.verbose:
        for job, reason in rejected:
            print(f"    - {job['title']} @ {job['company']}: {reason}")

    clean, quarantined = uae_detector.apply_safety_net(inside, repost_ids=reposts)
    inserted, refreshed = db.upsert_jobs(clean + quarantined)
    print(f"Phase 2c safety net             : {len(clean)} clean, {len(quarantined)} quarantined")
    if args.verbose:
        for job in quarantined:
            print(f"    x {job['title']} @ {job['company']} [{job['risk_score']}]: {job['risk_reasons']}")
    print(f"DB       inserted / refreshed   : {inserted} / {refreshed}")
    s = db.stats()
    print(
        f"\nINGEST SUMMARY: {len(clean)} clean jobs ingested, {len(quarantined)} quarantined, "
        f"{s['pending_evaluation']} awaiting /evaluate."
    )
    return 0


# -------------------------------------------------------------------------- pending
def _fmt_job(job: dict, rank: int | None = None) -> str:
    head = f"### {'#' + str(rank) + ' ' if rank else ''}{job['title']} @ {job['company']}"
    meta = [
        f"**ID:** `{job['id']}`",
        f"**Source:** {job['source']}",
        f"**Location:** {job.get('location') or 'n/a'}",
    ]
    if job.get("salary_text"):
        meta.append(f"**Salary:** {job['salary_text']}")
    if job.get("date_posted"):
        meta.append(f"**Posted:** {job['date_posted']}")
    if job.get("semantic_score") is not None:
        meta.append(f"**Semantic:** {job['semantic_score']:.3f}")
    if job.get("taste_score") is not None:
        meta.append(f"**Taste:** {job['taste_score']:+.3f}")
    if job.get("risk_score"):
        meta.append(f"**Risk:** {job['risk_score']} ({job.get('risk_reasons')})")
    meta.append(f"**URL:** {job.get('url') or 'n/a'}")
    desc = (job.get("description") or "").strip()
    if len(desc) > 3500:
        desc = desc[:3500] + " ..."
    return f"{head}\n" + "  \n".join(meta) + f"\n\n{desc}\n"


def cmd_pending(args) -> int:
    db.init_db()
    jobs = db.pending_jobs()
    if not jobs:
        print("No un-evaluated jobs. Run /ingest first.")
        return 0

    mode = config.MODE
    if args.mode:
        mode = args.mode.upper()
    limit = args.limit

    if mode == config.EFFICIENT_MODE:
        from engine import semantic_ranker

        ranked = semantic_ranker.rank(jobs, top_n=limit or config.EFFICIENT_TOP_N)
        db.set_semantic_scores({j["id"]: j["semantic_score"] for j in jobs})
        selected = ranked
        note = f"EFFICIENT_MODE: {len(jobs)} survivors ranked semantically, top {len(selected)} forwarded."
    else:
        selected = jobs[:limit] if limit else jobs
        note = f"SUPER_SAIYAN_MODE: all {len(selected)} survivors forwarded."

    try:
        from algorithms.taste_model import TasteModel

        if TasteModel.exists():
            tm = TasteModel.load()
            for j in selected:
                j["taste_score"] = tm.score(j)
    except Exception as exc:  # taste model is optional
        log.warning("taste model unavailable: %s", exc)

    print(f"# Pending jobs for evaluation - {date.today().isoformat()}\n")
    print(f"_{note}_\n")
    for i, j in enumerate(selected, 1):
        print(_fmt_job(j, i))
    print("\n---\nIDs in this batch: " + ", ".join(j["id"] for j in selected))
    return 0


# ---------------------------------------------------------------------- calibrate
def cmd_calibrate(args) -> int:
    from algorithms import taste_model

    return taste_model.main([str(args.n)])


# --------------------------------------------------------------------------- show
def cmd_show(args) -> int:
    db.init_db()
    job = db.get_job(args.id)
    if not job:
        print(f"No job with id {args.id!r}")
        return 1
    print(_fmt_job(job))
    print(f"**Status:** {job['status']}  |  **Evaluated:** {bool(job['evaluated'])}")
    return 0


# --------------------------------------------------------------------- status ops
def _set_many(ids: list[str], status: str | None) -> int:
    db.init_db()
    missing = []
    for raw_id in ids:
        job = db.get_job(raw_id)
        if not job:
            missing.append(raw_id)
            continue
        if status:
            db.set_status(job["id"], status)
        else:
            db.mark_evaluated([job["id"]])
        print(f"{job['id']}  {job['title']} @ {job['company']}  -> {status or 'evaluated'}")
    for m in missing:
        print(f"!! unknown id {m}")
    return 1 if missing else 0


def cmd_shortlist(args) -> int:
    return _set_many(args.ids, db.STATUS_SHORTLISTED)


def cmd_evaluated(args) -> int:
    return _set_many(args.ids, None)


def cmd_applied(args) -> int:
    return _set_many([args.id], db.STATUS_APPLIED)


def cmd_sent(args) -> int:
    return _set_many(args.ids, db.STATUS_SENT)


LETTER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([0-9a-f]{16})-(.+)\.md$")


def local_letters() -> list[dict]:
    """Cover letters currently on disk, joined to their job row. Unknown ids get status '?'."""
    db.init_db()
    out = []
    for f in sorted(config.COVER_LETTER_DIR.glob("*.md")):
        m = LETTER_RE.match(f.name)
        if not m:
            continue
        job = db.get_job(m.group(2))
        out.append({
            "file": f, "date": m.group(1), "id": m.group(2), "slug": m.group(3),
            "status": job["status"] if job else "?",
            "title": job["title"] if job else "", "company": job["company"] if job else "",
        })
    return out


def cmd_letters(_args) -> int:
    letters = local_letters()
    if not letters:
        print("No cover letters on disk.")
        return 0
    for L in letters:
        print(f"{L['id']}  {L['status']:<11} {L['date']}  {L['title']} @ {L['company']}  [{L['file'].name}]")
    unsent = sum(1 for L in letters if L["status"] == db.STATUS_APPLIED)
    print(f"\n{len(letters)} letter(s); {unsent} written but not yet sent.")
    return 0


def cmd_stats(_args) -> int:
    db.init_db()
    s = db.stats()
    print(f"total               : {s['total']}")
    print(f"quarantined         : {s['quarantined']}")
    print(f"pending evaluation  : {s['pending_evaluation']}")
    for k, v in sorted(s["by_status"].items()):
        print(f"status={k:<12}: {v}")
    print(f"mode                : {config.MODE}")
    return 0


def cmd_wipe_shortlist(_args) -> int:
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.SHORTLIST_PATH.write_text(
        f"# Daily Shortlist - {date.today().isoformat()}\n\n_No evaluation run yet today._\n", encoding="utf-8"
    )
    print(f"reset {config.SHORTLIST_PATH}")
    return 0


# ------------------------------------------------------------------- candidate
def cmd_candidate(args) -> int:
    if args.action == "set" and not args.name:
        print("usage: run.py candidate set NAME", file=sys.stderr)
        return 2
    valid = config.list_candidates()
    if args.name:
        try:
            config.set_active_candidate(args.name)
        except config.UnknownCandidate as exc:
            print(exc, file=sys.stderr)
            return 2
        print(f"active candidate set to {args.name}")
        return 0
    try:
        current = config.resolve_candidate_name(None)
    except (config.NoActiveCandidate, config.UnknownCandidate):
        current = "none"
    print(f"active candidate: {current}")
    print(f"valid candidates: {', '.join(valid) or '(none)'}")
    return 0


# --------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--candidate", metavar="NAME", help="override the active candidate for this run")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest")
    s.add_argument("--skip-boards", action="store_true", help="skip jobspy (LinkedIn/Indeed/Bayt)")
    s.add_argument("--skip-ats", action="store_true", help="skip Greenhouse/Lever")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("pending")
    s.add_argument("--mode", choices=["super_saiyan", "efficient"], help="override engine/config.py MODE")
    s.add_argument("--limit", type=int)
    s.set_defaults(fn=cmd_pending)

    s = sub.add_parser("calibrate")
    s.add_argument("n", nargs="?", type=int, default=5)
    s.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser("show")
    s.add_argument("id")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("shortlist")
    s.add_argument("ids", nargs="+")
    s.set_defaults(fn=cmd_shortlist)

    s = sub.add_parser("evaluated")
    s.add_argument("ids", nargs="+")
    s.set_defaults(fn=cmd_evaluated)

    s = sub.add_parser("applied")
    s.add_argument("id")
    s.set_defaults(fn=cmd_applied)

    s = sub.add_parser("sent")
    s.add_argument("ids", nargs="+")
    s.set_defaults(fn=cmd_sent)

    sub.add_parser("letters").set_defaults(fn=cmd_letters)

    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    sub.add_parser("wipe-shortlist").set_defaults(fn=cmd_wipe_shortlist)

    s = sub.add_parser("candidate")
    s.add_argument("action", nargs="?", choices=["set"])
    s.add_argument("name", nargs="?")
    s.set_defaults(fn=cmd_candidate, needs_candidate=False)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")
    if getattr(args, "needs_candidate", True):
        try:
            config.load_candidate(args.candidate)
        except (config.NoActiveCandidate, config.UnknownCandidate) as exc:
            print(exc, file=sys.stderr)
            return 2
        print(f"Candidate: {config.DISPLAY_NAME}")
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
