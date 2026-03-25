# chase/minimal_cover.py
from dataclasses import dataclass
from typing import FrozenSet, List, Tuple

from .models import Attribute, DependencySet, FD
from .closure import ClosureComputer


# ── Result Container ─────────────────────────────────────────────────────────

@dataclass
class MinimalCoverResult:
    """Result of a minimal-cover computation with step trace."""
    original: DependencySet
    result: DependencySet
    steps: List[Tuple[str, DependencySet]]

    def __str__(self) -> str:
        lines = [f"Minimal Cover ({len(self.result)} FDs):"]
        for d in self.result:
            lines.append(f"  {d}")
        return "\n".join(lines)


# ── MinimalCoverComputer ─────────────────────────────────────────────────────

class MinimalCoverComputer:
    """
    Compute the minimal (canonical) cover of a set of FDs.

    Algorithm
    ---------
    1. Decompose RHS to singletons
    2. Remove extraneous LHS attributes
    3. Remove redundant FDs
    4. Merge FDs with same LHS
    """

    def __init__(self, deps: DependencySet) -> None:
        self.deps = deps

    def compute(self) -> MinimalCoverResult:
        steps: List[Tuple[str, DependencySet]] = []

        # Work with list of (frozenset, frozenset) pairs for easy mutation
        fds = [(fd.lhs, fd.rhs) for fd in self.deps.fds]
        steps.append(("Original FDs", self._to_depset(fds)))

        # Step 1 — singleton RHS
        fds = [(lhs, frozenset({a})) for lhs, rhs in fds for a in rhs]
        steps.append(("Decompose RHS to singletons", self._to_depset(fds)))

        # Step 2 — remove extraneous LHS attributes
        new_fds = []
        for lhs, rhs in fds:
            minimal = set(lhs)
            for a in sorted(lhs, key=lambda x: x.name):
                if len(minimal) <= 1:
                    break
                candidate = frozenset(minimal - {a})
                test_fds = [(candidate if l == frozenset(minimal) else l, r) for l, r in fds]
                cl = ClosureComputer.closure_of(candidate, [FD(l, r) for l, r in fds])
                if rhs <= cl:
                    minimal.discard(a)
            new_fds.append((frozenset(minimal), rhs))
        fds = new_fds
        steps.append(("Remove extraneous LHS attributes", self._to_depset(fds)))

        # Step 3 — remove redundant FDs
        i = len(fds) - 1
        while i >= 0:
            remaining = fds[:i] + fds[i + 1:]
            cl = ClosureComputer.closure_of(
                fds[i][0], [FD(l, r) for l, r in remaining]
            )
            if fds[i][1] <= cl:
                fds = remaining
            i -= 1
        steps.append(("Remove redundant FDs", self._to_depset(fds)))

        # Step 4 — merge same LHS
        merged: dict[FrozenSet[Attribute], set[Attribute]] = {}
        for lhs, rhs in fds:
            merged.setdefault(lhs, set()).update(rhs)
        fds = [(lhs, frozenset(rhs)) for lhs, rhs in merged.items()]
        steps.append(("Merge FDs with same LHS", self._to_depset(fds)))

        result = self._to_depset(fds)
        return MinimalCoverResult(original=self.deps, result=result, steps=steps)

    @staticmethod
    def _to_depset(pairs) -> DependencySet:
        ds = DependencySet()
        for lhs, rhs in pairs:
            ds.add(FD(lhs, rhs))
        return ds