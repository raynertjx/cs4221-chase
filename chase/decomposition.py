# chase/decomposition.py
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from .minimal_cover import MinimalCoverComputer
from .models import Attribute, DependencySet, FD, Schema, TableauCell, TableauRow
from .closure import ClosureComputer


# ── Result Containers ────────────────────────────────────────────────────────

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
    
@dataclass
class BCNFDecompositionResult:
    """Result of BCNF decomposition."""
    fragments: List[Schema]
    steps: List[Tuple[Schema, FD, Schema]]
    dependency_preserved: bool

    @property
    def fragment_names(self) -> List[List[str]]:
        return [s.names for s in self.fragments]
    
    def __str__(self) -> str:
        fragments_str = ", ".join(str(s) for s in self.fragment_names)
        dp = "True" if self.dependency_preserved else "False"
        return f"BCNF fragments: {fragments_str}\nDependency preserved: {dp}"

@dataclass
class ThreeNFDecompositionResult:
    """Result of 3NF decomposition."""
    fragments: List[Schema]
    steps: List[Tuple[Schema, FD, Schema]]
    canonical_cover: DependencySet
    key_added: bool
    key_fragment: Optional[Schema]

    @property
    def fragment_names(self) -> List[List[str]]:
        return [s.names for s in self.fragments]
    
    def __str__(self) -> str:
        fragments_str = ", ".join(str(s) for s in self.fragment_names)
        key_str = f" (key fragment: {self.key_fragment} added)" if self.key_added else ""
        canonical_cover_str = ", ".join(f"{fd.lhs} -> {fd.rhs}" for fd in self.canonical_cover.fds)
        return f"#NF decomposition: [{fragments_str}]{key_str}\nCanonical cover: {canonical_cover_str}"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tableau_to_dicts(rows: List[TableauRow], attrs: List[str]) -> List[Dict[str, str]]:
    """Serialise a list of TableauRow into plain dicts for snapshots."""
    return [{a: r.cells[a].symbol for a in attrs} for r in rows]


# ── CandidateKeyFinder ───────────────────────────────────────────────────────

class CandidateKeyFinder:
    """Find all candidate keys using attribute closure."""

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

        ds = DependencySet(projected)
        return MinimalCoverComputer(ds).compute().result


# ── BCNFDecomposer ────────────────────────────────────────────────────────────
class BCNFDecomposer:
    """Decompose a schema into BCNF."""

    def __init__(self, schema: Schema, deps: DependencySet) -> None:
        self.schema = schema
        self.deps = deps

    def _find_violation(self, schema: Schema, deps: DependencySet) -> Optional[Tuple[FrozenSet[Attribute], FrozenSet[Attribute]]]:
        """Find a BCNF violation, if any."""
        closure_compute = ClosureComputer(schema, deps)
        for fd in deps.fds:
            lhs, rhs = fd.lhs & schema.attribute_set, fd.rhs & schema.attribute_set
            if not rhs:
                continue
            cl = closure_compute.compute(lhs)
            if not cl.is_superkey:
                return (lhs, rhs)
        return None
    
    def _is_dependency_preserved(self, schemas: List[Schema]) -> bool:
        """Check if the original dependencies are preserved in the decomposition."""
        dependency_set = DependencySet()
        for fragment in schemas:
            projection = ProjectionComputer(self.schema, self.deps)
            projected_deps = projection.project(fragment.names)
            for fd in projected_deps.fds:
                dependency_set.add(fd)

        for fd in self.deps.fds:
            closure_computer = ClosureComputer(self.schema, dependency_set)
            closure = closure_computer.closure_of(fd.lhs, dependency_set.fds)
            if not fd.rhs.issubset(closure):
                return False
        return True

    def decompose(self) -> BCNFDecompositionResult:
        """Return the BCNF decomposition result."""
        steps: List[Tuple[str, List[Schema]]] = []
        done: List[Schema] = []
        current_work: List[Tuple[Schema, DependencySet]] = [(self.schema, self.deps)]

        steps.append(("Initial steps", [self.schema]))

        while current_work:
            current_schema, current_deps = current_work.pop()
            violation = self._find_violation(current_schema, current_deps)
            if not violation:
                done.append(current_schema)
                continue

            lhs, rhs = violation

            sub_closure_compute = ClosureComputer(current_schema, current_deps)
            closure_attributes = sub_closure_compute.compute(lhs).closure & current_schema.attribute_set

            r1_names = sorted(a.name for a in closure_attributes)
            r2_names = sorted(a.name for a in current_schema.attribute_set if a not in closure_attributes or a in lhs)

            r1 = Schema(r1_names)
            r2 = Schema(r2_names)

            projection = ProjectionComputer(current_schema, current_deps)
            d1 = projection.project(r1_names)
            d2 = projection.project(r2_names)

            lhs_str = "{" + ",".join(sorted(a.name for a in lhs)) + "}"
            rhs_str = "{" + ",".join(sorted(a.name for a in rhs)) + "}"
            steps.append((
                f"Violation {lhs_str} → {rhs_str} on {current_schema} → split into {r1}, {r2}",
                done + [r1, r2] + [s for s, _ in current_work],
            ))

            current_work.append((r1, d1))
            current_work.append((r2, d2))

        seen: List[FrozenSet[Attribute]] = []
        unique: List[Schema] = []

        for s in done:
            if s.attribute_set not in seen:
                unique.append(s)
                seen.append(s.attribute_set)

        steps.append(("End result", unique))
        dp = self._is_dependency_preserved(unique)

        return BCNFDecompositionResult(
            fragments=unique,
            steps=steps,
            dependency_preserved=dp,
        )
        
# ── ThreeNFDecomposer ─────────────────────────────────────────────────────────
class ThreeNFDecomposer:
    """Decompose a schema into 3NF."""

    def __init__(self, schema: Schema, deps: DependencySet) -> None:
        self.schema = schema
        self.deps = deps

    def decompose(self) -> ThreeNFDecompositionResult:
        """Return the 3NF decomposition result."""
        steps: List[Tuple[str, List[Schema]]] = []
        minimal_cover = MinimalCoverComputer(self.deps).compute().result
        steps.append(("Compute minimal cover", minimal_cover.fds))

        fragments: List[Set[Attribute]] = []
        for fd in minimal_cover.fds:
            fragment_attributes = sorted(a.name for a in fd.lhs | fd.rhs)
            new_fragment = Schema(fragment_attributes)
            new_set = new_fragment.attribute_set

            already_subsumed = any(new_set.issubset(f.attribute_set) for f in fragments)
            if already_subsumed:
                steps.append((f"Skipping {new_fragment} as it is subsumed by existing fragments", fragments))
                continue

            fragments = [f for f in fragments if not f.attribute_set.issubset(new_set)]
            fragments.append(new_fragment)
            steps.append((f"Add fragment {new_fragment} for FD {fd}", fragments))

        candidate_key_finder = CandidateKeyFinder(self.schema, self.deps)
        candidate_key_result = candidate_key_finder.compute()
        key_added = False
        key_fragment: Optional[Schema] = None

        if candidate_key_result.keys:
            contains_key = any(
                any(key <= frag.attribute_set for key in candidate_key_result.keys)
                for frag in fragments
            )
            if not contains_key:
                smallest_key = min(candidate_key_result.keys, key=len)
                key_fragment = Schema(sorted(a.name for a in smallest_key))
                fragments.append(key_fragment)
                key_added = True
                steps.append((
                    f"Add key fragment {key_fragment} — no fragment contained a candidate key",
                    list(fragments),
                ))
 
        steps.append(("Result", list(fragments)))
 
        return ThreeNFDecompositionResult(
            fragments=fragments,
            canonical_cover=minimal_cover,
            steps=steps,
            key_added=key_added,
            key_fragment=key_fragment,
        )

