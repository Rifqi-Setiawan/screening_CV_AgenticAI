"""Ontology models and relation definitions (v2.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RelationType(str, Enum):
    IMPLIES = "IMPLIES"
    PART_OF = "PART_OF"
    SUBSUMES = "SUBSUMES"
    PARTIAL_OF = "PARTIAL_OF"


@dataclass
class OntologyVersion:
    version: str
    sha256: str
    loaded_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sha256": self.sha256,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
        }


@dataclass
class Concept:
    version: str
    id: str
    label: str
    kind: str
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "aliases": self.aliases,
        }


@dataclass
class ConceptEdge:
    version: str
    src: str
    dst: str
    relation: RelationType | str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        rel = self.relation.value if isinstance(self.relation, RelationType) else str(self.relation)
        return {
            "version": self.version,
            "src": self.src,
            "dst": self.dst,
            "relation": rel,
            "weight": self.weight,
        }


@dataclass
class TraversalPath:
    target: str
    relation: str
    depth: int
    weight: float
    path: list[str] = field(default_factory=list)
