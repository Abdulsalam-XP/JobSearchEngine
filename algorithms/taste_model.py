"""Bradley-Terry pairwise preference learner with active pair selection.

    P(i beats j) = sigmoid( w^T (x_i - x_j) )

x are TF-IDF vectors of "title + company + description". The learned weight vector w
(plus the vocabulary/idf needed to rebuild the vectoriser) lives in data/taste_profile.json.

Active learning: at each step we pick the unseen pair whose predicted preference is closest
to 0.5 (maximum uncertainty). Before any answers exist every pair is 0.5, so ties break on
maximum feature distance to spread the first questions across the job space.

Usage:
    python -m algorithms.taste_model            # interactive 5-question calibration
    from algorithms.taste_model import TasteModel; TasteModel.load().score(job)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from engine import config

MAX_FEATURES = 600
L2 = 0.5
LEARNING_RATE = 0.5
EPOCHS = 300


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _job_text(job: dict) -> str:
    return f"{job.get('title', '')} {job.get('company', '')} {(job.get('description') or '')[:3000]}"


@dataclass
class TasteModel:
    vocabulary: dict[str, int]
    idf: np.ndarray
    w: np.ndarray
    comparisons: list[dict] = field(default_factory=list)  # {"winner": id, "loser": id}

    # ------------------------------------------------------------------ build
    @classmethod
    def fit_vocabulary(cls, jobs: list[dict]) -> "TasteModel":
        vec = TfidfVectorizer(stop_words="english", max_features=MAX_FEATURES, ngram_range=(1, 2), sublinear_tf=True)
        vec.fit([_job_text(j) for j in jobs])
        vocab = {k: int(v) for k, v in vec.vocabulary_.items()}
        return cls(vocabulary=vocab, idf=vec.idf_.astype(float), w=np.zeros(len(vocab)))

    def _vectoriser(self) -> TfidfVectorizer:
        vec = TfidfVectorizer(stop_words="english", vocabulary=self.vocabulary, ngram_range=(1, 2), sublinear_tf=True)
        vec.fit(["placeholder"])  # initialise internals; idf is overwritten below
        vec.idf_ = self.idf
        return vec

    def features(self, jobs: list[dict]) -> np.ndarray:
        return self._vectoriser().transform([_job_text(j) for j in jobs]).toarray()

    # ------------------------------------------------------------------ learn
    def prob(self, xi: np.ndarray, xj: np.ndarray) -> float:
        return float(_sigmoid(self.w @ (xi - xj)))

    def train(self, X: dict[str, np.ndarray]) -> None:
        """Logistic regression on pairwise differences, L2-regularised, plain gradient descent."""
        if not self.comparisons:
            return
        D = np.array([X[c["winner"]] - X[c["loser"]] for c in self.comparisons])
        # Symmetrise: (d, 1) and (-d, 0) so there is no intercept to learn.
        D = np.vstack([D, -D])
        y = np.concatenate([np.ones(len(self.comparisons)), np.zeros(len(self.comparisons))])
        w = np.zeros(D.shape[1])
        for _ in range(EPOCHS):
            p = _sigmoid(D @ w)
            grad = D.T @ (p - y) / len(y) + L2 * w / len(y)
            w -= LEARNING_RATE * grad
        self.w = w

    def score(self, job: dict) -> float:
        """w^T x - higher means closer to the user's revealed taste."""
        return float(self.features([job])[0] @ self.w)

    def rank(self, jobs: list[dict]) -> list[dict]:
        X = self.features(jobs)
        scored = sorted(zip(X @ self.w, jobs), key=lambda t: t[0], reverse=True)
        return [j for _, j in scored]

    # ---------------------------------------------------------- active learning
    def next_pair(self, jobs: list[dict], X: dict[str, np.ndarray], asked: set[frozenset]) -> tuple[dict, dict] | None:
        best, best_key = None, None
        for a, b in combinations(jobs, 2):
            key = frozenset((a["id"], b["id"]))
            if key in asked:
                continue
            uncertainty = -abs(self.prob(X[a["id"]], X[b["id"]]) - 0.5)  # 0 is maximal
            spread = float(np.linalg.norm(X[a["id"]] - X[b["id"]]))
            cand = (round(uncertainty, 4), spread)
            if best_key is None or cand > best_key:
                best, best_key = (a, b), cand
        return best

    # --------------------------------------------------------------- persist
    def save(self, path: Path | str | None = None) -> Path:
        path = Path(path or config.TASTE_PROFILE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vocabulary": self.vocabulary,
            "idf": self.idf.tolist(),
            "w": self.w.tolist(),
            "comparisons": self.comparisons,
            "top_positive_terms": self.top_terms(10),
            "top_negative_terms": self.top_terms(10, negative=True),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path | str | None = None) -> "TasteModel":
        path = Path(path or config.TASTE_PROFILE_PATH)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            vocabulary=data["vocabulary"],
            idf=np.array(data["idf"], dtype=float),
            w=np.array(data["w"], dtype=float),
            comparisons=data.get("comparisons", []),
        )

    @classmethod
    def exists(cls, path: Path | str | None = None) -> bool:
        return Path(path or config.TASTE_PROFILE_PATH).exists()

    def top_terms(self, n: int = 10, negative: bool = False) -> list[str]:
        inv = {v: k for k, v in self.vocabulary.items()}
        order = np.argsort(self.w if negative else -self.w)
        return [inv[int(i)] for i in order[:n] if (self.w[i] < 0 if negative else self.w[i] > 0)]


# ---------------------------------------------------------------------------
# Interactive calibration
# ---------------------------------------------------------------------------
def _summary(job: dict, width: int = 90) -> str:
    desc = (job.get("description") or "").replace("\n", " ")
    return (
        f"  {job.get('title')} @ {job.get('company')}  [{job.get('location') or 'n/a'}]\n"
        f"    {desc[: width * 3]}{'...' if len(desc) > width * 3 else ''}"
    )


def calibrate(jobs: list[dict], n_questions: int = 5, *, ask=input, out=print) -> TasteModel:
    """Run an interactive A/B session. `ask`/`out` are injectable for tests."""
    if len(jobs) < 2:
        raise ValueError("need at least 2 jobs to calibrate taste")
    model = TasteModel.fit_vocabulary(jobs)
    X = dict(zip([j["id"] for j in jobs], model.features(jobs)))
    asked: set[frozenset] = set()

    out(f"\nTaste calibration: {n_questions} pairwise questions. Answer A, B, or S to skip.\n")
    for q in range(1, n_questions + 1):
        pair = model.next_pair(jobs, X, asked)
        if pair is None:
            break
        a, b = pair
        asked.add(frozenset((a["id"], b["id"])))
        out(f"Q{q}/{n_questions}  Which job do you prefer?\n")
        out("[A]\n" + _summary(a))
        out("[B]\n" + _summary(b) + "\n")
        while True:
            ans = ask("A / B / S > ").strip().lower()
            if ans in ("a", "b", "s"):
                break
        if ans == "s":
            continue
        winner, loser = (a, b) if ans == "a" else (b, a)
        model.comparisons.append({"winner": winner["id"], "loser": loser["id"]})
        model.train(X)
        out("")

    path = model.save()
    out(f"Saved taste profile -> {path}")
    if model.top_terms(5):
        out(f"You lean towards: {', '.join(model.top_terms(8))}")
    if model.top_terms(5, negative=True):
        out(f"You lean away from: {', '.join(model.top_terms(8, negative=True))}")
    return model


def main(argv: list[str] | None = None) -> int:
    from engine import db

    argv = argv if argv is not None else sys.argv[1:]
    n = int(argv[0]) if argv else 5
    db.init_db()
    jobs = db.pending_jobs() or db.all_jobs()
    jobs = [j for j in jobs if not j.get("is_ghost")]
    if len(jobs) < 2:
        print("Not enough jobs in career.db to calibrate. Run /ingest first.")
        return 1
    calibrate(jobs, n_questions=n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
