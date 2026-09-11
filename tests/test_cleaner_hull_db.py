from algorithms import hull
from engine import cleaner, db


# ----------------------------------------------------------------- cleaner
def test_normalise_strips_noise_and_suffix():
    j = cleaner.normalise_job({"title": "URGENT Hiring: Senior React Developer", "company": "Acme Tech LLC",
                               "description": "<p>Build <b>things</b></p>"})
    assert j["title"] == "Senior React Developer"
    assert j["company"] == "Acme Tech"
    assert j["description"] == "Build things"
    assert j["id"] == db.job_id("Acme Tech", "Senior React Developer")


def test_dedupe_collapses_fuzzy_duplicates():
    jobs = [
        {"title": "Senior Software Engineer", "company": "Careem", "description": "x"},
        {"title": "Sr. Software Engineer", "company": "Careem LLC", "description": "y"},
        {"title": "QA Engineer", "company": "Careem", "description": "z"},
    ]
    unique, reposts, dropped = cleaner.dedupe(jobs)
    assert len(unique) == 2 and dropped == 1 and reposts == set()


def test_dedupe_flags_reposts_against_existing():
    existing = [("abc", "Careem", "Software Engineer")]
    unique, reposts, _ = cleaner.dedupe([{"title": "Software Engineer", "company": "Careem"}], existing)
    assert unique[0]["id"] in reposts


def test_dedupe_drops_empty():
    unique, _, dropped = cleaner.dedupe([{"title": "", "company": "X"}, {"title": "Dev", "company": ""}])
    assert unique == [] and dropped == 2


# -------------------------------------------------------------------- hull
def test_hull_keeps_uae_mid_fullstack():
    d = hull.decide({"title": "Full Stack Developer", "location": "Dubai, UAE", "description": "React + Node"})
    assert d.inside and "fullstack" in d.tracks


def test_hull_rejects_outside_uae():
    assert not hull.decide({"title": "Software Engineer", "location": "Riyadh, Saudi Arabia"}).inside


def test_hull_rejects_principal():
    assert not hull.decide({"title": "Principal Engineer", "location": "Dubai"}).inside


def test_hull_keeps_senior_but_drops_lead_and_head():
    assert hull.decide({"title": "Senior Backend Engineer", "location": "Dubai"}).inside
    assert hull.decide({"title": "Backend Engineer", "location": "Dubai"}).inside
    assert not hull.decide({"title": "Head of Engineering", "location": "Dubai"}).inside
    assert not hull.decide({"title": "Engineering Manager", "location": "Dubai"}).inside


def test_hull_fails_open_on_unknown_location_and_seniority():
    d = hull.decide({"title": "Machine Learning Engineer", "location": "", "description": ""})
    assert d.inside and d.seniority is None and "ai" in d.tracks


def test_hull_rejects_non_tech():
    assert not hull.decide({"title": "Sales Executive", "location": "Dubai", "description": "sell software"}).inside
    assert not hull.decide({"title": "Accountant", "location": "Dubai", "description": ""}).inside


# ---------------------------------------------------------------------- db
def test_db_roundtrip(tmp_path):
    path = tmp_path / "t.db"
    db.init_db(path)
    jobs = [
        {"title": "Dev", "company": "A", "source": "test", "description": "d", "is_ghost": False},
        {"title": "Dev", "company": "B", "source": "test", "description": "d", "is_ghost": True, "risk_score": 70},
    ]
    assert db.upsert_jobs(jobs, path) == (2, 0)
    assert db.upsert_jobs(jobs[:1], path) == (0, 1)
    pending = db.pending_jobs(path)
    assert [p["company"] for p in pending] == ["A"]
    jid = pending[0]["id"]
    assert db.get_job(jid[:6], path)["id"] == jid  # prefix lookup
    assert db.set_status(jid, db.STATUS_SHORTLISTED, path)
    assert db.pending_jobs(path) == []
    s = db.stats(path)
    assert s == {"total": 2, "quarantined": 1, "pending_evaluation": 0,
                 "by_status": {"ingested": 1, "shortlisted": 1}}


def test_db_init_is_idempotent(tmp_path):
    path = tmp_path / "t.db"
    db.init_db(path)
    db.init_db(path)
    assert db.stats(path)["total"] == 0


def test_hull_rejects_ops_role_with_passing_qa_mention():
    d = hull.decide({"title": "HOP Team Leader", "location": "Dubai",
                     "description": "supervise picking and quality assurance of each order"})
    assert not d.inside


def test_hull_accepts_generic_title_with_strong_tech_description():
    d = hull.decide({"title": "Engineer II", "location": "Dubai",
                     "description": "You will build React and TypeScript frontends and Python backend services."})
    assert d.inside and "fullstack" in d.tracks


def test_hull_accepts_it_ops_roles():
    for title in ("IT Support Engineer", "System Administrator", "IT Operations Specialist",
                  "Helpdesk Technician", "IT Engineer"):
        d = hull.decide({"title": title, "location": "Sharjah", "description": ""})
        assert d.inside and "it_ops" in d.tracks, title


def test_hull_accepts_microsoft_stack_description():
    d = hull.decide({"title": "Technical Officer", "location": "Dubai",
                     "description": "Manage Active Directory, Microsoft 365 tenants and Windows Server patching."})
    assert d.inside and "it_ops" in d.tracks
