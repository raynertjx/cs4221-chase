"""
chase/algorithms.py
───────────────────
Pure algorithmic classes — each encapsulates one logical operation
and exposes a clean run() → Result interface.

Classes
-------
ClosureComputer        – attribute closure  X⁺
MinimalCoverComputer   – canonical / minimal cover of a DependencySet
CandidateKeyFinder     – all candidate keys of a schema under FDs
ProjectionComputer     – project FDs onto a sub-schema
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import FrozenSet, List, Optional, Set, Tuple

from .models import Attribute, Dependency, DependencySet, FD, MVD, Schema


# ── Result containers ────────────────────────────────────────────────────────

@dataclass
class ClosureResult:
    """Result of an attribute-closure computation."""
    input_attrs: FrozenSet[Attribute]
    closure: FrozenSet[Attribute]
    is_superkey: bool

    @property
    def input_names(self) -> List[str]:
        return sorted(a.name for a in self.input_attrs)

    @property
    def closure_names(self) -> List[str]:
        return sorted(a.name for a in self.closure)

    def __str__(self) -> str:
        tag = " [superkey]" if self.is_superkey else ""
        return (
            f"{{{', '.join(self.input_names)}}}⁺ = "
            f"{{{', '.join(self.closure_names)}}}{tag}"
        )


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


@dataclass
class CandidateKeyResult:
    """Result of candidate-key computation."""
    keys: List[FrozenSet[Attribute]]
    prime_attributes: FrozenSet[Attribute]

    @property
    def key_names(self) -> List[List[str]]:
        return [sorted(a.name for a in k) for k in self.keys]

    def __str__(self) -> str:
        keys_str = ", ".join("{" + ",".join(k) + "}" for k in self.key_names)
        primes = ", ".join(sorted(a.name for a in self.prime_attributes))
        return f"Candidate keys: {keys_str}\nPrime attributes: {{{primes}}}"


# ── ClosureComputer ──────────────────────────────────────────────────────────

class ClosureComputer:
    """
    Compute the attribute closure X⁺ under a set of FDs.

    Parameters
    ----------
    schema : Schema
        The full relation schema (used to determine superkey status).
    deps   : DependencySet
        The dependencies (only FDs are used).
    """

    def __init__(self, schema: Schema, deps: DependencySet) -> None:
        self.schema = schema
        self.deps = deps

    def compute(
        self, attrs: FrozenSet[Attribute] | Set[str] | List[str]
    ) -> ClosureResult:
        """Return the closure of *attrs* under the stored FDs."""
        # Normalise input
        if isinstance(attrs, (list, set)) and attrs and isinstance(next(iter(attrs)), str):
            seed = frozenset(Attribute(a) for a in attrs)
        else:
            seed = frozenset(attrs)  # type: ignore

        closure = set(seed)
        changed = True
        while changed:
            changed = False
            for fd in self.deps.fds:
                if fd.lhs <= closure and not fd.rhs <= closure:
                    closure |= fd.rhs
                    changed = True

        frozen = frozenset(closure)
        return ClosureResult(
            input_attrs=seed,
            closure=frozen,
            is_superkey=(frozen >= self.schema.attribute_set),
        )

    @staticmethod
    def closure_of(attrs: FrozenSet[Attribute], fds: List[FD]) -> FrozenSet[Attribute]:
        """Stateless helper — no Schema needed."""
        closure = set(attrs)
        changed = True
        while changed:
            changed = False
            for fd in fds:
                if fd.lhs <= closure and not fd.rhs <= closure:
                    closure |= fd.rhs
                    changed = True
        return frozenset(closure)


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


# ── CandidateKeyFinder ───────────────────────────────────────────────────────

class CandidateKeyFinder:
    """
    Find all candidate keys using attribute closure.

    Uses bitmask optimisation similar to pratik2358/fucntional_dep.
    """

    def __init__(self, schema: Schema, deps: DependencySet) -> None:
        self.schema = schema
        self.deps = deps
        self._closure = ClosureComputer(schema, deps)

    def compute(self) -> CandidateKeyResult:
        attrs = list(self.schema)
        n = len(attrs)
        all_mask = (1 << n) - 1

        bit_of = {a: 1 << i for i, a in enumerate(attrs)}

        def to_mask(s):
            m = 0
            for a in s:
                m |= bit_of[a]
            return m

        def from_mask(m):
            return frozenset(a for a in attrs if m & bit_of[a])

        # Find superkeys
        superkeys = []
        for r in range(n + 1):
            for combo in combinations(range(n), r):
                mask = sum(1 << i for i in combo)
                attr_set = from_mask(mask)
                cl = self._closure.compute(attr_set)
                if cl.is_superkey:
                    superkeys.append(mask)

        # Sort by popcount → keep minimal
        superkeys.sort(key=lambda m: bin(m).count("1"))
        candidates = []
        for m in superkeys:
            if any((m & c) == c for c in candidates):
                continue
            candidates.append(m)

        keys = [from_mask(m) for m in candidates]
        primes = frozenset().union(*keys) if keys else frozenset()

        return CandidateKeyResult(keys=keys, prime_attributes=primes)


# ── ProjectionComputer ───────────────────────────────────────────────────────

class ProjectionComputer:
    """Project a set of FDs onto a sub-schema R'."""

    def __init__(self, schema: Schema, deps: DependencySet) -> None:
        self.schema = schema
        self.deps = deps

    def project(self, sub_attrs: List[str]) -> DependencySet:
        """Return the projected FD set over *sub_attrs*."""
        sub = frozenset(Attribute(a) for a in sub_attrs)
        fds = self.deps.fds
        projected: List[FD] = []

        for r in range(1, len(sub_attrs) + 1):
            for combo in combinations(sub, r):
                lhs = frozenset(combo)
                cl = ClosureComputer.closure_of(lhs, fds)
                head = (cl & sub) - lhs
                if head:
                    projected.append(FD(lhs, head))

        # Minimise via MinimalCoverComputer
        ds = DependencySet(projected)
        return MinimalCoverComputer(ds).compute().result
