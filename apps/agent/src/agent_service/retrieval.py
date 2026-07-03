"""BM25 retrieval over the markdown knowledge base.

v1 is deliberately BM25 (rank-bm25): deterministic (stable evals), dependency-light, and
fully offline. The planned upgrade path is a vector index behind the same search() signature,
validated by the eval suite.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-_.]*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class Chunk:
    doc: str          # source filename, e.g. video-playback-troubleshooting.md
    heading: str      # section heading within the doc
    text: str

    def render(self) -> str:
        return f"[{self.doc} — {self.heading}]\n{self.text.strip()}"


def _split_doc(name: str, raw: str) -> list[Chunk]:
    """Split a markdown doc into chunks by ## headings; the preamble becomes its own chunk."""
    title = name
    m = re.match(r"^#\s+(.+)$", raw.strip().splitlines()[0]) if raw.strip() else None
    if m:
        title = m.group(1).strip()
    parts = re.split(r"^##\s+", raw, flags=re.MULTILINE)
    chunks = []
    preamble = parts[0]
    body = re.sub(r"^#\s+.+$", "", preamble, flags=re.MULTILINE).strip()
    if body:
        chunks.append(Chunk(doc=name, heading=title, text=body))
    for part in parts[1:]:
        lines = part.splitlines()
        heading = lines[0].strip()
        text = "\n".join(lines[1:]).strip()
        if text:
            chunks.append(Chunk(doc=name, heading=heading, text=text))
    return chunks


class KBIndex:
    def __init__(self, kb_dir: Path):
        self.chunks: list[Chunk] = []
        for path in sorted(kb_dir.glob("*.md")):
            self.chunks.extend(_split_doc(path.name, path.read_text(encoding="utf-8")))
        if not self.chunks:
            raise ValueError(f"no KB documents found in {kb_dir}")
        # Headings and doc names carry a lot of signal — include them in the indexed text.
        corpus = [_tokenize(f"{c.doc} {c.heading} {c.text}") for c in self.chunks]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(zip(self.chunks, scores), key=lambda pair: pair[1], reverse=True)
        return [(chunk, float(score)) for chunk, score in ranked[:top_k] if score > 0]


_index: KBIndex | None = None


def get_index(kb_dir: Path) -> KBIndex:
    global _index
    if _index is None:  # single-process cache; tests construct KBIndex directly
        _index = KBIndex(kb_dir)
    return _index
