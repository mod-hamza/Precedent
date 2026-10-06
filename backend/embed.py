"""EMBED role (PRD §5): one adapter, three backends, cosine similarity in numpy.

auto    -> voyage if VOYAGE_API_KEY is set, else sentence-transformers if installed, else hash
voyage  -> Voyage AI embeddings endpoint (VOYAGE_MODEL, default voyage-3.5-lite)
st      -> local sentence-transformers (PRECEDENT_ST_MODEL, default all-MiniLM-L6-v2)
hash    -> dependency-free hashed word + char-n-gram vectors; offline and deterministic, weaker semantics.
           Clustering thresholds must be re-tuned per backend.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3

import numpy as np

from .cache import cache_key
from .config import settings

HASH_DIM = 1024


def _hash_embed(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), HASH_DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        t = t.casefold()
        words = re.findall(r"\w+", t)
        feats = words + [a + "_" + b for a, b in zip(words, words[1:])]
        feats += [t[j:j + 4] for j in range(max(0, len(t) - 3))]
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "little")
            out[i, h % HASH_DIM] += 1.0 if (h >> 63) == 0 else -1.0
    out = np.sign(out) * np.log1p(np.abs(out))
    return out


class Embedder:
    def __init__(self, conn: sqlite3.Connection | None = None, backend: str | None = None):
        self.conn = conn
        backend = backend or settings.embed_backend
        if backend == "auto":
            if os.environ.get("VOYAGE_API_KEY"):
                backend = "voyage"
            else:
                try:
                    import sentence_transformers  # noqa: F401
                    backend = "st"
                except ImportError:
                    backend = "hash"
        self.backend = backend
        self._st = None
        if conn is not None:
            conn.execute("CREATE TABLE IF NOT EXISTS embed_cache(key TEXT PRIMARY KEY, vec BLOB)")

    @property
    def name(self) -> str:
        if self.backend == "voyage":
            return "voyage:" + os.environ.get("VOYAGE_MODEL", "voyage-3.5-lite")
        if self.backend == "st":
            return "st:" + os.environ.get("PRECEDENT_ST_MODEL", "all-MiniLM-L6-v2")
        return f"hash:{HASH_DIM}"

    def embed(self, texts: list[str]) -> np.ndarray:
        """L2-normalised float32 matrix, one row per text. Cached per (backend, text)."""
        keys = [cache_key(embed=self.name, text=t) for t in texts]
        vecs: dict[int, np.ndarray] = {}
        if self.conn is not None:
            for i, k in enumerate(keys):
                row = self.conn.execute("SELECT vec FROM embed_cache WHERE key=?", (k,)).fetchone()
                if row:
                    vecs[i] = np.frombuffer(row[0], dtype=np.float32)
        todo = [i for i in range(len(texts)) if i not in vecs]
        if todo:
            fresh = self._raw([texts[i] for i in todo])
            for i, v in zip(todo, fresh):
                vecs[i] = v.astype(np.float32)
                if self.conn is not None:
                    self.conn.execute("INSERT OR REPLACE INTO embed_cache VALUES(?,?)", (keys[i], vecs[i].tobytes()))
            if self.conn is not None:
                self.conn.commit()
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        m = np.vstack([vecs[i] for i in range(len(texts))])
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        return m / np.where(norms == 0, 1, norms)

    def _raw(self, texts: list[str]) -> np.ndarray:
        if self.backend == "hash":
            return _hash_embed(texts)
        if self.backend == "st":
            if self._st is None:
                from sentence_transformers import SentenceTransformer
                self._st = SentenceTransformer(os.environ.get("PRECEDENT_ST_MODEL", "all-MiniLM-L6-v2"))
            return np.asarray(self._st.encode(texts, batch_size=64, show_progress_bar=False))
        if self.backend == "voyage":
            import httpx
            out = []
            for i in range(0, len(texts), 128):
                r = httpx.post("https://api.voyageai.com/v1/embeddings", timeout=60,
                               headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
                               json={"input": texts[i:i + 128], "model": os.environ.get("VOYAGE_MODEL", "voyage-3.5-lite")})
                r.raise_for_status()
                out += [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
            return np.asarray(out)
        raise ValueError(f"unknown embed backend {self.backend}")


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Rows are already L2-normalised by Embedder.embed."""
    return a @ b.T
