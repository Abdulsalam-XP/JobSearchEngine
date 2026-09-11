import importlib

import pytest

from algorithms import hull
from engine import config


@pytest.fixture(autouse=True)
def _reset():
    yield
    importlib.reload(config)


def _job(title, desc="", loc="Dubai, UAE"):
    return {"title": title, "description": desc, "location": loc}


def test_exclude_title_keywords_rejects_before_tracks(monkeypatch):
    monkeypatch.setattr(config, "EXCLUDE_TITLE_KEYWORDS", ["solutions architect"])
    monkeypatch.setattr(config, "SENIORITY_EXTRA_PATTERNS", {})
    monkeypatch.setattr(config, "DOMAIN_TRACKS", {"arch": ["architect"]})
    d = hull.decide(_job("Solutions Architect"))
    assert not d.inside and "excluded title keyword" in d.reason


def test_same_title_passes_when_exclusions_empty(monkeypatch):
    monkeypatch.setattr(config, "EXCLUDE_TITLE_KEYWORDS", [])
    monkeypatch.setattr(config, "SENIORITY_EXTRA_PATTERNS", {})
    monkeypatch.setattr(config, "DOMAIN_TRACKS", {"arch": ["architect"]})
    assert hull.decide(_job("Solutions Architect")).inside


def test_non_tech_pattern_comes_from_config(monkeypatch):
    monkeypatch.setattr(config, "NON_TECH_TITLE_PATTERN", r"\b(developer)\b")
    monkeypatch.setattr(config, "DOMAIN_TRACKS", {"arch": ["architect", "revit", "autocad"]})
    desc = "architect using revit and autocad"  # 3 distinct keywords = strong description evidence
    d = hull.decide(_job("Software Developer", desc=desc))
    assert not d.inside and d.reason.startswith("non-tech title")
    # a pattern without "developer" does NOT reject the same title
    monkeypatch.setattr(config, "NON_TECH_TITLE_PATTERN", r"\b(sales)\b")
    assert hull.decide(_job("Software Developer", desc=desc)).inside


def test_architect_is_lead_tier_only_when_extra_pattern_set(monkeypatch):
    monkeypatch.setattr(config, "SENIORITY_EXTRA_PATTERNS", {4: [r"\barchitect\b"]})
    assert hull.seniority_of("Junior Architect") == 4
    monkeypatch.setattr(config, "SENIORITY_EXTRA_PATTERNS", {})
    assert hull.seniority_of("Junior Architect") == 1
