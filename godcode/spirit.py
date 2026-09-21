"""SpiritEngine -- discerns the spiritual intent behind words. 🕊

Loads the God Code training dataset, builds a keyword index over each row's
primary_action + spiritual_intent + logic_flows, and classifies new text by
keyword overlap. When nothing resonates, it falls back to silent contemplation.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

_WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    """
    a an the of and to in for on with by or is are was were be been being
    this that these those it its as at from into over under between through
    during before after above below up down out off again further then once
    here there when where why how all any both each few more most other some
    such no nor not only own same so than too very can will just don should
    now your you we they them their our us my me him her his she he i
    do does did have has had shall may might must would could ought
    """.split()
)

SILENT_CONTEMPLATION = {
    "intent": "Silent contemplation",
    "confidence": 0.0,
    "spiritual_intent": "The Spirit is quiet on this matter.",
    "suggestion": "BREATHE and try again.",
    "keywords": [],
}


def _keywords(text: str) -> set[str]:
    """Lowercase word tokens with stopwords removed."""
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in STOPWORDS}


class SpiritEngine:
    """Keyword-overlap classifier over the God Code training dataset."""

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        if dataset_path is None:
            # Default: god_code_training_dataset.csv at the repo root.
            dataset_path = Path(__file__).resolve().parent.parent / "god_code_training_dataset.csv"
        self.dataset_path = Path(dataset_path)
        self.rows: list[dict] = self._load()

    def _load(self) -> list[dict]:
        try:
            with open(self.dataset_path, newline="", encoding="utf-8") as f:
                records = list(csv.reader(f))
        except OSError:
            # No dataset beside the engine (e.g. an installed copy):
            # the Spirit is quiet, and classify() falls back gracefully.
            return []
        if not records:
            return []
        header, records = records[0], records[1:]
        rows: list[dict] = []
        buf: list[str] = []
        for rec in records:
            if len(rec) == len(header):
                # A row ends here: the code field may have spanned earlier
                # physical lines (unquoted), accumulated in buf.
                code = "\n".join(buf + [rec[0]])
                row = dict(zip(header, [code] + rec[1:]))
                row["keywords"] = _keywords(
                    " ".join(row[c] for c in ("primary_action", "spiritual_intent", "logic_flows"))
                )
                rows.append(row)
                buf = []
            else:
                # Continuation line of the multi-line code field.
                buf.extend(rec)
        return rows

    def classify(self, text: str) -> dict:
        """Classify text -> {intent, confidence, spiritual_intent, suggestion, keywords}."""
        words = _keywords(text)
        best: dict | None = None
        best_overlap = 0
        for row in self.rows:
            overlap = len(words & row["keywords"])
            if overlap > best_overlap:
                best, best_overlap = row, overlap
        if best is None:
            return dict(SILENT_CONTEMPLATION)
        confidence = min(1.0, best_overlap / max(1, len(best["keywords"])))
        return {
            "intent": best["primary_action"],
            "confidence": round(confidence, 4),
            "spiritual_intent": best["spiritual_intent"],
            "suggestion": best["next_suggestions"],
            "keywords": sorted(words & best["keywords"]),
        }

    def prophesy(self, program_text: str) -> str:
        """Compose a 2-3 sentence divine forecast over a program's lines."""
        lines = [ln.strip() for ln in (program_text or "").splitlines() if ln.strip()]
        results = [self.classify(ln) for ln in lines] or [dict(SILENT_CONTEMPLATION)]
        counts = Counter(r["intent"] for r in results)
        top = max(counts.values())
        # Dominant intent = mode; ties resolve to the earliest line's intent.
        dominant = next(r for r in results if counts[r["intent"]] == top)
        avg_conf = sum(r["confidence"] for r in results) / len(results)
        pct = round(avg_conf * 100)
        return (
            f"Thus the Spirit speaks over this creation: the prevailing wind is "
            f"'{dominant['intent']}', discerned with {pct}% certainty. "
            f"{dominant['spiritual_intent']} "
            f"Therefore the counsel of heaven is this: {dominant['suggestion']}"
        )
