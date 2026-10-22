"""Experimental standalone scalar-event postfilter helpers.

NOT called by mask_step. NOT a JSON Schema implementation. Container events
are markers rather than reconstructed values, so only scalar rules are safe.
Callers must check denies before observe and separately handle final checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Rule:
    path: Tuple[str | int, ...]  # container path the rule applies to
    kind: str  # "unique" | "capture" | "equals_capture" | "min_contains"
    name: str = ""  # capture slot name
    value: Optional[object] = None  # reserved for compatibility

    def __post_init__(self) -> None:
        if self.kind not in {"unique", "capture", "equals_capture"}:
            raise ValueError("supported scalar rules: unique, capture, equals_capture")


@dataclass
class SideMemory:
    """Event-driven semantic state. `observe(path, value)` after completions;
    `denies(prefix_path, candidate_value)` before a value completes."""

    rules: List[Rule] = field(default_factory=list)
    seen: Dict[tuple, list] = field(default_factory=dict)  # unique: items per concrete array
    captures: Dict[str, object] = field(default_factory=dict)
    counts: Dict[tuple, int] = field(default_factory=dict)  # min_contains tallies

    # ---------------------------------------------------------- event feed
    def observe(self, path: tuple, value: object) -> None:
        for r in self.rules:
            if r.kind == "unique" and path == r.path + (len(self.seen.get(r.path, [])),):
                self.seen.setdefault(r.path, []).append(value)
            if r.kind == "capture" and path == r.path:
                self.captures[r.name] = value

    # ------------------------------------------------------------ queries
    def denies(self, path: tuple, candidate: object) -> bool:
        """Would completing `candidate` at `path` violate any semantic rule?"""
        for r in self.rules:
            if r.kind == "unique" and path == r.path + (len(self.seen.get(r.path, [])),):
                if candidate in self.seen.get(r.path, []):
                    return True
            if r.kind == "equals_capture" and path == r.path:
                bound = self.captures.get(r.name)
                if r.name in self.captures and candidate != bound:
                    return True
        return False

    def finalize_ok(self) -> bool:
        """No end-of-document rules are implemented; always True."""
        return True


def guide_allows(mem: SideMemory, path: tuple, candidate: object) -> bool:
    return not mem.denies(path, candidate)
