"""
Policy Semantics Registry

Holds externally-defined policy rules that cannot be inferred from data alone.
Two kinds of policy:

  Grounded  — a concrete definition exists (e.g. BSA $10k threshold, NY crash
              reporting criteria). Planner injects the exact SQL condition.

  Gap       — concept is real but has no authoritative definition in this
              schema (e.g. "VIP client", "preventable crash"). Planner
              acknowledges the gap and suggests the best available proxy.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PolicyDefinition:
    concept: str
    domain: str
    description: str
    keywords: list[str]
    is_gap: bool = False

    # Grounded policy fields
    sql_condition: Optional[str] = None
    column_mappings: dict = field(default_factory=dict)  # {col: [values]} or {col: ">= N"}
    threshold: Optional[float] = None
    time_window_days: Optional[int] = None
    source: Optional[str] = None

    # Gap policy fields
    gap_message: Optional[str] = None
    gap_alternatives: list[str] = field(default_factory=list)


def _policy_text(p: PolicyDefinition) -> str:
    kw = ", ".join(p.keywords) if p.keywords else ""
    return f"{p.concept}: {p.description}. Keywords: {kw}"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


class PolicyRegistry:
    """
    Loads and indexes policy definitions from a policy_definitions.json file
    placed alongside the VSL directory.

    Usage (keyword):
        registry = PolicyRegistry.from_vsl_dir("demos/bird_finance_vsl")
        policy = registry.match("Find reportable large cash withdrawals")

    Usage (embedding):
        registry = PolicyRegistry.from_vsl_dir("demos/bird_finance_vsl")
        registry.build_embedding_index()   # one-time; call after loading
        policy = registry.match_embedding(query_embedding)
    """

    def __init__(self) -> None:
        self._policies: list[PolicyDefinition] = []
        self._policy_embeddings: Optional[list[list[float]]] = None
        self._pre_matched: Optional[PolicyDefinition] = None

    @classmethod
    def from_vsl_dir(cls, vsl_dir: str | Path) -> "PolicyRegistry":
        registry = cls()
        path = Path(vsl_dir) / "policy_definitions.json"
        if path.exists():
            registry._load(path)
        return registry

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyRegistry":
        registry = cls()
        registry._load(Path(path))
        return registry

    def _load(self, path: Path) -> None:
        with open(path) as f:
            data = json.load(f)
        for p in data.get("policies", []):
            self._policies.append(PolicyDefinition(
                concept=p["concept"],
                domain=p.get("domain", ""),
                description=p["description"],
                keywords=p.get("keywords", []),
                is_gap=p.get("is_gap", False),
                sql_condition=p.get("sql_condition"),
                column_mappings=p.get("column_mappings", {}),
                threshold=p.get("threshold"),
                time_window_days=p.get("time_window_days"),
                source=p.get("source"),
                gap_message=p.get("gap_message"),
                gap_alternatives=p.get("gap_alternatives", []),
            ))

    def policy_texts(self) -> list[str]:
        return [_policy_text(p) for p in self._policies]

    def build_embedding_index(self, embeddings: list[list[float]]) -> None:
        """Store pre-computed policy embeddings for use with match_embedding()."""
        assert len(embeddings) == len(self._policies)
        self._policy_embeddings = embeddings

    def set_pre_match(self, policy: Optional[PolicyDefinition]) -> None:
        """Pin the result returned by match(); used when the caller pre-computes retrieval."""
        self._pre_matched = policy

    def match(self, question: str) -> Optional[PolicyDefinition]:
        """Return pre-matched policy if set; otherwise keyword regex search."""
        if self._pre_matched is not None:
            return self._pre_matched
        q = question.lower()
        for policy in self._policies:
            for kw in policy.keywords:
                if re.search(re.escape(kw.lower()), q):
                    return policy
        return None

    def match_embedding(self, query_embedding: list[float]) -> Optional[PolicyDefinition]:
        """Embedding-based match: returns the policy with highest cosine similarity."""
        if not self._policies or self._policy_embeddings is None:
            return None
        scores = [_cosine(query_embedding, pe) for pe in self._policy_embeddings]
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        return self._policies[best_idx]

    def all_policies(self) -> list[PolicyDefinition]:
        return list(self._policies)

    def __len__(self) -> int:
        return len(self._policies)

    def __repr__(self) -> str:
        return f"PolicyRegistry({len(self._policies)} policies)"
