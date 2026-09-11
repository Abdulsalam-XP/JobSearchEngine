"""EFFICIENT_MODE local semantic ranker.

Embeds profile.md and every pending job description with a small SentenceTransformer
(all-MiniLM-L6-v2, ~80MB, CPU-only) and ranks by cosine similarity. Understands that
"Machine Learning" ~ "Deep Learning" without keyword overlap.

Falls back to TF-IDF cosine similarity when sentence-transformers / torch are not installed,
so the pipeline never hard-fails on a missing heavy dependency.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from engine import config

log = logging.getLogger(__name__)

_MODEL = None


def _load_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer  # heavy import, deferred

        _MODEL = SentenceTransformer(config.EMBEDDING_MODEL, device="cpu")
    return _MODEL


def _job_text(job: dict, max_chars: int = 2000) -> str:
    return f"{job.get('title', '')}. {job.get('company', '')}. {(job.get('description') or '')[:max_chars]}"


def _cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return a @ b


def _scores_transformer(profile: str, texts: list[str]) -> np.ndarray:
    model = _load_model()
    job_vecs = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
    prof_vec = model.encode([profile], convert_to_numpy=True)[0]
    return _cosine(job_vecs, prof_vec)


def _scores_tfidf(profile: str, texts: list[str]) -> np.ndarray:
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    m = vec.fit_transform([profile] + texts)
    prof = m[0].toarray()[0]
    jobs = m[1:].toarray()
    return _cosine(jobs, prof)


def score_jobs(jobs: list[dict], profile_text: str | None = None) -> dict[str, float]:
    """Return {job_id: cosine_similarity} for every job."""
    if not jobs:
        return {}
    profile_text = profile_text or Path(config.PROFILE_PATH).read_text(encoding="utf-8")
    texts = [_job_text(j) for j in jobs]
    try:
        scores = _scores_transformer(profile_text, texts)
        backend = config.EMBEDDING_MODEL
    except Exception as exc:  # ImportError, OSError (no model download), etc.
        log.warning("SentenceTransformer unavailable (%s); falling back to TF-IDF", exc)
        scores = _scores_tfidf(profile_text, texts)
        backend = "tfidf"
    log.info("semantic ranking via %s over %d jobs", backend, len(jobs))
    return {j["id"]: float(s) for j, s in zip(jobs, scores)}


def rank(jobs: list[dict], top_n: int | None = None, profile_text: str | None = None) -> list[dict]:
    """Sort jobs by semantic similarity (desc), attach `semantic_score`, return top_n."""
    scores = score_jobs(jobs, profile_text)
    for j in jobs:
        j["semantic_score"] = scores.get(j["id"], 0.0)
    ranked = sorted(jobs, key=lambda j: j["semantic_score"], reverse=True)
    return ranked[: top_n or config.EFFICIENT_TOP_N]
