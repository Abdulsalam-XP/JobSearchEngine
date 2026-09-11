import importlib
import textwrap

import pytest

from engine import config


def _make_candidate(root, name, body):
    d = root / name
    d.mkdir(parents=True)
    (d / "candidate.py").write_text(textwrap.dedent(body), encoding="utf-8")
    (d / "profile.md").write_text("# p\n", encoding="utf-8")
    (d / "resume.md").write_text("# r\n", encoding="utf-8")
    return d


@pytest.fixture(autouse=True)
def _reset_config():
    """Reload engine.config after each test so overlays do not leak."""
    yield
    importlib.reload(config)


def test_list_candidates_ignores_template_and_files(tmp_path):
    _make_candidate(tmp_path, "alice", "DISPLAY_NAME = 'Alice'\n")
    _make_candidate(tmp_path, "_template", "DISPLAY_NAME = 'T'\n")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    assert config.list_candidates(tmp_path) == ["alice"]


def test_resolve_prefers_explicit_then_env_then_file(tmp_path, monkeypatch):
    _make_candidate(tmp_path, "alice", "DISPLAY_NAME = 'Alice'\n")
    _make_candidate(tmp_path, "bob", "DISPLAY_NAME = 'Bob'\n")
    active = tmp_path / ".active"
    active.write_text("bob\n", encoding="utf-8")
    monkeypatch.delenv("CANDIDATE", raising=False)
    assert config.resolve_candidate_name(None, candidates_dir=tmp_path, active_file=active) == "bob"
    monkeypatch.setenv("CANDIDATE", "alice")
    assert config.resolve_candidate_name(None, candidates_dir=tmp_path, active_file=active) == "alice"
    assert config.resolve_candidate_name("bob", candidates_dir=tmp_path, active_file=active) == "bob"


def test_resolve_raises_when_nothing_set(tmp_path, monkeypatch):
    _make_candidate(tmp_path, "alice", "DISPLAY_NAME = 'Alice'\n")
    monkeypatch.delenv("CANDIDATE", raising=False)
    with pytest.raises(config.NoActiveCandidate):
        config.resolve_candidate_name(None, candidates_dir=tmp_path, active_file=tmp_path / ".missing")


def test_resolve_raises_on_unknown_name(tmp_path, monkeypatch):
    _make_candidate(tmp_path, "alice", "DISPLAY_NAME = 'Alice'\n")
    monkeypatch.delenv("CANDIDATE", raising=False)
    with pytest.raises(config.UnknownCandidate) as ei:
        config.resolve_candidate_name("zed", candidates_dir=tmp_path, active_file=tmp_path / ".x")
    assert "alice" in str(ei.value)


def test_load_overlays_constants_and_paths(tmp_path, monkeypatch):
    d = _make_candidate(tmp_path, "alice", """
        DISPLAY_NAME = "Alice"
        SEARCH_TERMS = ["junior architect"]
        MAX_SENIORITY_LEVEL = 2
        EXCLUDE_TITLE_KEYWORDS = ["solutions architect"]
    """)
    monkeypatch.delenv("CANDIDATE", raising=False)
    name = config.load_candidate("alice", candidates_dir=tmp_path, active_file=tmp_path / ".x")
    assert name == "alice"
    assert config.CANDIDATE_NAME == "alice"
    assert config.DISPLAY_NAME == "Alice"
    assert config.SEARCH_TERMS == ["junior architect"]
    assert config.MAX_SENIORITY_LEVEL == 2
    assert config.EXCLUDE_TITLE_KEYWORDS == ["solutions architect"]
    # untouched constant keeps the shared default
    assert config.QUARANTINE_THRESHOLD == 50
    assert config.CANDIDATE_DIR == d
    assert config.DB_PATH == d / "data" / "career.db"
    assert config.TASTE_PROFILE_PATH == d / "data" / "taste_profile.json"
    assert config.PROFILE_PATH == d / "profile.md"
    assert config.RESUME_PATH == d / "resume.md"
    assert config.SHORTLIST_PATH == d / "reports" / "daily_shortlist.md"
    assert config.COVER_LETTER_DIR == d / "reports" / "cover_letters"
    assert (d / "data").is_dir() and (d / "reports" / "cover_letters").is_dir()


def test_load_ignores_lowercase_and_private_names(tmp_path, monkeypatch):
    _make_candidate(tmp_path, "alice", """
        DISPLAY_NAME = "Alice"
        _SECRET = 1
        helper = 2
    """)
    monkeypatch.delenv("CANDIDATE", raising=False)
    config.load_candidate("alice", candidates_dir=tmp_path, active_file=tmp_path / ".x")
    assert not hasattr(config, "_SECRET")
    assert not hasattr(config, "helper")


def test_set_active_writes_file_and_validates(tmp_path):
    _make_candidate(tmp_path, "alice", "DISPLAY_NAME = 'Alice'\n")
    active = tmp_path / ".active"
    config.set_active_candidate("alice", candidates_dir=tmp_path, active_file=active)
    assert active.read_text(encoding="utf-8").strip() == "alice"
    with pytest.raises(config.UnknownCandidate):
        config.set_active_candidate("zed", candidates_dir=tmp_path, active_file=active)
