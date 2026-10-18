"""Tiny, dependency-free BM25 retriever over the repo's Markdown runbooks.

Runbooks are split into sections on `## ` headings so the copilot cites the exact
procedure an on-call engineer should follow, not a whole document.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = frozenset(
    "a an and are as at be by for from has in is it of on or that the this to was were will with "
    "when what how if you your".split()
)


def _stem(token: str) -> str:
    """Very light suffix stripping so 'aborts'/'aborted'/'abort' and 'releases'/'release' match."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass(frozen=True)
class Chunk:
    source: str
    heading: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def load_chunks(directory: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(directory).glob("*.md")):
        title = path.stem
        current_heading, buf = "Overview", []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                continue
            if line.startswith("## "):
                if "".join(buf).strip():
                    chunks.append(Chunk(path.name, f"{title} › {current_heading}", "\n".join(buf).strip()))
                current_heading, buf = line[3:].strip(), []
            else:
                buf.append(line)
        if "".join(buf).strip():
            chunks.append(Chunk(path.name, f"{title} › {current_heading}", "\n".join(buf).strip()))
    return chunks


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        # Section headings name the procedure, so their terms count 3x.
        self._docs = [Counter(tokenize(f"{c.heading} {c.heading} {c.heading} {c.text}")) for c in chunks]
        self._lens = [sum(d.values()) for d in self._docs]
        self._avg = (sum(self._lens) / len(self._lens)) if self._lens else 0.0
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(d.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> list[Hit]:
        terms = tokenize(query)
        scored: list[Hit] = []
        for chunk, doc, length in zip(self.chunks, self._docs, self._lens, strict=True):
            score = 0.0
            for t in terms:
                tf = doc.get(t, 0)
                if not tf:
                    continue
                norm = tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / (self._avg or 1)))
                score += self._idf.get(t, 0.0) * norm
            # "Overview" sections only restate alert metadata; procedures are what responders need
            if score > 0 and not chunk.heading.endswith("› Overview"):
                scored.append(Hit(chunk, round(score, 4)))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]
