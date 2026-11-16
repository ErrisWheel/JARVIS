"""Optional local Ollama embedding index with a BM25-safe fallback.

No model is downloaded here. Set JARVIS_EMBEDDING_MODEL to an already-installed
local embedding model to enable cosine similarity retrieval.
"""
from __future__ import annotations

import math
import os
from typing import Any
import httpx

from .config import OLLAMA_BASE_URL
from .database import list_memories
from .platform_store import memory_vector_upsert, get_memory_vectors, replace_memory_links

EMBEDDING_MODEL = os.environ.get("JARVIS_EMBEDDING_MODEL", "").strip()[:120]


async def _embed(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    if not EMBEDDING_MODEL:
        raise RuntimeError("No local embedding model is configured. Set JARVIS_EMBEDDING_MODEL to an installed Ollama embedding model.")
    response = await client.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": EMBEDDING_MODEL, "input": texts, "truncate": True},
    )
    response.raise_for_status()
    data = response.json()
    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        # Compatibility with older Ollama embedding payloads.
        if len(texts) == 1 and isinstance(data.get("embedding"), list):
            embeddings = [data["embedding"]]
        else:
            raise RuntimeError("Ollama returned an unexpected embedding response.")
    output: list[list[float]] = []
    for vector in embeddings:
        if not isinstance(vector, list) or not vector or len(vector) > 20000:
            raise RuntimeError("Ollama returned an invalid embedding vector.")
        converted = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in converted):
            raise RuntimeError("Embedding vector contains a non-finite value.")
        output.append(converted)
    return output


async def index_memories(batch_size: int = 24) -> dict[str, Any]:
    memories = list_memories(limit=5000)
    indexed = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=4)) as client:
        for start in range(0, len(memories), max(1, min(batch_size, 48))):
            batch = memories[start:start + max(1, min(batch_size, 48))]
            inputs = [f"{m.get('category','general')}: {m.get('content','')}\nTags: {m.get('tags','')}"[:4000] for m in batch]
            vectors = await _embed(client, inputs)
            for memory, vector in zip(batch, vectors):
                memory_vector_upsert(int(memory["id"]), EMBEDDING_MODEL, vector)
                indexed += 1
    # Build a bounded semantic knowledge graph from the newest 240 memories.
    # This is derived only from real local embeddings; no random/fabricated links.
    rows = sorted(get_memory_vectors(EMBEDDING_MODEL), key=lambda item: item.get("updated_at", ""), reverse=True)[:240]
    normalized: list[tuple[dict, list[float], float]] = []
    for row in rows:
        vector = [float(value) for value in row.get("vector", [])]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0 and math.isfinite(norm):
            normalized.append((row, vector, norm))
    edges: dict[tuple[int, int], float] = {}
    for index, (left, vector_left, norm_left) in enumerate(normalized):
        ranked: list[tuple[float, int]] = []
        for other_index, (right, vector_right, norm_right) in enumerate(normalized):
            if index == other_index or len(vector_left) != len(vector_right):
                continue
            if left.get("workspace_id", "default") != right.get("workspace_id", "default"):
                continue
            score = sum(a * b for a, b in zip(vector_left, vector_right)) / (norm_left * norm_right)
            if math.isfinite(score) and score >= 0.62:
                ranked.append((score, other_index))
        for score, other_index in sorted(ranked, reverse=True)[:4]:
            source_id = int(left["memory_id"])
            target_id = int(normalized[other_index][0]["memory_id"])
            edges[(source_id, target_id)] = score
    link_count = replace_memory_links(EMBEDDING_MODEL, [(a, b, score) for (a, b), score in edges.items()])
    return {"indexed": indexed, "model": EMBEDDING_MODEL, "graph_nodes": len(normalized), "graph_links": link_count}


async def semantic_search(query: str, limit: int = 8, workspace_id: str | None = None) -> list[dict]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=4)) as client:
        query_vectors = await _embed(client, [query[:4000]])
    query_vector = query_vectors[0]
    qnorm = math.sqrt(sum(x * x for x in query_vector)) or 1.0
    scored = []
    for row in get_memory_vectors(EMBEDDING_MODEL, workspace_id):
        vector = row.get("vector", [])
        if len(vector) != len(query_vector):
            continue
        norm = math.sqrt(sum(float(x) * float(x) for x in vector)) or 1.0
        score = sum(float(a) * float(b) for a, b in zip(query_vector, vector)) / (qnorm * norm)
        if math.isfinite(score):
            row["similarity"] = round(score, 5)
            scored.append(row)
    scored.sort(key=lambda item: (item["similarity"], item.get("updated_at", "")), reverse=True)
    return scored[:max(1, min(limit, 30))]
