import importlib
import textwrap

import pytest

import run
from engine import config


def _make_candidate(root, name):
    d = root / name
    d.mkdir(parents=True)
    (d / "candidate.py").write_text(textwrap.dedent(f"DISPLAY_NAME = '{name.title()}'\n"), encoding="utf-8")
    (d / "profile.md").write_text("# p\n", encoding="utf-8")
    (d / "resume.md").write_text("# r\n", encoding="utf-8")
    return d


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(config, "ACTIVE_FILE", tmp_path / ".active_candidate")
    monkeypatch.delenv("CANDIDATE", raising=False)
    _make_candidate(tmp_path / "candidates", "alice")
    _make_candidate(tmp_path / "candidates", "bob")
    yield tmp_path
    importlib.reload(config)


def test_candidate_show_reports_none(workspace, capsys):
    assert run.main(["candidate"]) == 0
    out = capsys.readouterr().out
    assert "none" in out and "alice" in out and "bob" in out


def test_candidate_set_then_show(workspace, capsys):
    assert run.main(["candidate", "set", "bob"]) == 0
    assert (workspace / ".active_candidate").read_text(encoding="utf-8").strip() == "bob"
    run.main(["candidate"])
    assert "bob" in capsys.readouterr().out


def test_candidate_set_unknown_fails(workspace, capsys):
    assert run.main(["candidate", "set", "zed"]) == 2
    assert "unknown candidate" in capsys.readouterr().err


def test_subcommand_without_candidate_fails_cleanly(workspace, capsys):
    assert run.main(["stats"]) == 2
    assert "no active candidate" in capsys.readouterr().err


def test_subcommand_prints_header_with_flag(workspace, capsys):
    assert run.main(["--candidate", "alice", "stats"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "Candidate: Alice"


def test_sent_status_and_letters_listing(workspace, capsys, monkeypatch):
    from engine import db
    run.main(["candidate", "set", "alice"])
    config.load_candidate("alice")
    db.init_db()
    db.upsert_jobs([{"id": "abcdefabcdefabcd", "title": "Dev", "company": "Acme", "description": "x",
                     "location": "Dubai", "source": "t", "url": "u"}])
    assert db.set_status("abcdefabcdefabcd", db.STATUS_APPLIED)
    config.COVER_LETTER_DIR.mkdir(parents=True, exist_ok=True)
    (config.COVER_LETTER_DIR / "2026-09-11-abcdefabcdefabcd-acme.md").write_text("# letter\n", encoding="utf-8")
    (config.COVER_LETTER_DIR / "notes.md").write_text("ignored\n", encoding="utf-8")
    assert run.main(["letters"]) == 0
    out = capsys.readouterr().out
    assert "abcdefabcdefabcd" in out and "applied" in out and "1 written but not yet sent" in out
    assert run.main(["sent", "abcdefabcdefabcd"]) == 0
    assert db.get_job("abcdefabcdefabcd")["status"] == db.STATUS_SENT
    run.main(["letters"])
    assert "0 written but not yet sent" in capsys.readouterr().out
    assert run.main(["sent", "0000000000000000"]) == 1
