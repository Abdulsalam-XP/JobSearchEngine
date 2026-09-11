from datetime import date

from engine import config, uae_detector as det


def _job(**kw):
    base = {"title": "Software Engineer", "company": "Acme Tech", "description": "", "location": "Dubai, UAE"}
    base.update(kw)
    return base


def test_clean_job_scores_zero():
    r = det.assess(_job(description="We build React and Python apps. Visa provided."))
    assert r.score == 0 and not r.quarantined


def test_visa_charge_is_trap():
    r = det.assess(_job(description="Candidate must pay visa charges before joining."))
    assert r.score == config.PENALTY_VISA_TRAP and r.quarantined


def test_golden_visa_not_penalised():
    r = det.assess(_job(description="Golden Visa holders preferred. NOC required. Spouse visa OK."))
    assert r.score == 0


def test_commission_only_is_trap():
    r = det.assess(_job(description="This is a commission only role in direct sales."))
    assert r.score >= config.PENALTY_WAGE_TRAP and r.quarantined


def test_salary_below_floor_dubai():
    r = det.assess(_job(salary_text="AED 4,000 per month", location="Dubai, UAE"))
    assert r.quarantined and "below floor" in r.reasons[0]


def test_salary_above_floor_ok():
    r = det.assess(_job(salary_text="AED 9,000 - 12,000 per month", location="Abu Dhabi"))
    assert r.score == 0


def test_annual_salary_normalised():
    r = det.assess(_job(salary_text="AED 120,000 per annum", location="Abu Dhabi"))
    assert r.score == 0  # 10k/month >= 8k floor


def test_no_salary_fails_open():
    assert det.extract_monthly_salary_aed(None) is None
    assert det.assess(_job(salary_text=None)).score == 0


def test_remote_has_no_floor():
    r = det.assess(_job(salary_text="AED 3,000 per month", location="Remote"))
    assert r.score == 0


def test_stale_posting_is_ghost():
    r = det.assess(_job(date_posted="2026-01-01"), today=date(2026, 9, 7))
    assert r.score == config.PENALTY_GHOST and not r.quarantined  # 40 < 50 alone


def test_repost_penalty():
    r = det.assess(_job(), is_repost=True)
    assert r.score == config.PENALTY_GHOST


def test_ghost_plus_agency_quarantines():
    r = det.assess(_job(company="Confidential", date_posted="2026-01-01"), today=date(2026, 9, 7))
    assert r.score == config.PENALTY_GHOST + config.PENALTY_AGENCY and r.quarantined


def test_agency_in_description():
    r = det.assess(_job(description="Hiring on behalf of our client, a leading bank."))
    assert r.score == config.PENALTY_AGENCY


def test_apply_safety_net_splits():
    jobs = [_job(id="a"), _job(id="b", description="commission only")]
    clean, quarantined = det.apply_safety_net(jobs)
    assert [j["id"] for j in clean] == ["a"]
    assert quarantined[0]["is_ghost"] is True and quarantined[0]["risk_score"] >= 50
