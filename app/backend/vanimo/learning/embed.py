"""Local vector stand-in for the exemplar index (architecture §9.2; S3 Vectors + Titan/Cohere
embeddings in AWS).

A deterministic hashing-trick embedding over word unigrams and bigrams: no model, no network,
same input → same vector. Good enough to retrieve "replies to similar messages" on the sample
workspace; replaced by a Bedrock embedding model behind the same two functions once the AWS
account exists (D7). Runs on L1 text only, tokens collapsed to their kind.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import re

DIM = 256
_TOKEN = re.compile(r"⟦(ME|PERSON|EMAIL|PHONE)[^⟧]*⟧|⟦NS_[0-9a-f]{8}⟧")
_WORD = re.compile(r"[a-zऀ-ॿ0-9']+")
_STOP = frozenset("the a an to of and or in on for is it this that we i you be with at as are was by".split())


def _bucket(feature: str) -> tuple[int, float]:
    h = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    return int.from_bytes(h[:4], "little") % DIM, 1.0 if h[4] & 1 else -1.0


def embed(l1: str) -> list[float]:
    text = _TOKEN.sub(lambda m: f" tok{(m.group(1) or 'ns').lower()} ", l1.lower())
    ws = [w for w in _WORD.findall(text) if w not in _STOP]
    vec = [0.0] * DIM
    for feature in ws + [f"{a}_{b}" for a, b in itertools.pairwise(ws)]:
        i, sign = _bucket(feature)
        vec[i] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 5) for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
