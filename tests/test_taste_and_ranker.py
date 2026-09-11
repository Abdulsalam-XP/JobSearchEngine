import numpy as np

from algorithms import taste_model as tm
from engine import semantic_ranker

JOBS = [
    {"id": "ml1", "title": "Machine Learning Engineer", "company": "AI Co",
     "description": "deep learning pytorch neural networks models training data"},
    {"id": "ml2", "title": "AI Engineer", "company": "Neural Ltd",
     "description": "machine learning llm transformers python research models"},
    {"id": "web1", "title": "React Developer", "company": "Web Co",
     "description": "react typescript frontend css html components ui"},
    {"id": "web2", "title": "Frontend Engineer", "company": "Sites Inc",
     "description": "javascript react next.js frontend ui css"},
    {"id": "qa1", "title": "QA Automation Engineer", "company": "Test Co",
     "description": "selenium pytest automation testing quality assurance"},
]


def test_taste_learns_preference_and_persists(tmp_path, monkeypatch):
    from engine import config
    monkeypatch.setattr(config, "TASTE_PROFILE_PATH", tmp_path / "default_taste.json")
    answers = iter(["a", "a", "a", "a", "a"])
    # Force "ML wins" regardless of which side it lands on by answering based on the prompt.
    shown = []

    def out(s):
        shown.append(s)

    def ask(_prompt):
        # find the last A/B block; prefer the ML job
        a_block = next(s for s in reversed(shown) if s.startswith("[A]"))
        return "a" if "Machine Learning" in a_block or "AI Engineer" in a_block else "b"

    path = tmp_path / "taste.json"
    model = tm.calibrate(JOBS, n_questions=4, ask=ask, out=out)
    model.save(path)
    loaded = tm.TasteModel.load(path)
    assert len(loaded.comparisons) == 4
    ranked = loaded.rank(JOBS)
    assert ranked[0]["id"] in {"ml1", "ml2"}
    assert loaded.score(JOBS[0]) > loaded.score(JOBS[2])


def test_next_pair_avoids_asked():
    model = tm.TasteModel.fit_vocabulary(JOBS)
    X = dict(zip([j["id"] for j in JOBS], model.features(JOBS)))
    asked = set()
    seen = []
    for _ in range(10):
        pair = model.next_pair(JOBS, X, asked)
        assert pair is not None
        key = frozenset((pair[0]["id"], pair[1]["id"]))
        assert key not in seen
        seen.append(key)
        asked.add(key)
    assert model.next_pair(JOBS, X, asked) is None  # C(5,2)=10 exhausted


def test_bradley_terry_probability_symmetry():
    model = tm.TasteModel.fit_vocabulary(JOBS)
    model.w = np.random.default_rng(0).normal(size=len(model.w))
    X = model.features(JOBS)
    p = model.prob(X[0], X[1])
    assert abs(p + model.prob(X[1], X[0]) - 1.0) < 1e-9


def test_tfidf_fallback_ranks_by_meaning(monkeypatch):
    monkeypatch.setattr(semantic_ranker, "_scores_transformer", lambda *a, **k: (_ for _ in ()).throw(ImportError("x")))
    profile = "Full-stack web developer: react typescript frontend javascript"
    top = semantic_ranker.rank([dict(j) for j in JOBS], top_n=2, profile_text=profile)
    assert {j["id"] for j in top} == {"web1", "web2"}
    assert all("semantic_score" in j for j in top)
