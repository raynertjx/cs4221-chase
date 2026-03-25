# chase/decomposition.py
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, FrozenSet, List, Tuple

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
class ChaseLosslessResult:
    decomposition: List[Schema]
    lossless: bool
    steps: List[Tuple[str, List[Dict[str, str]]]]

    @property
    def success(self) -> bool:
        return self.lossless

    def __str__(self) -> str:
        tag = "IS" if self.lossless else "is NOT"
        dec = ", ".join(str(s) for s in self.decomposition)
        return f"Decomposition [{dec}] {tag} lossless ({len(self.steps)} steps)"


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

        # We need MinimalCoverComputer to minimise this, but to avoid circular imports 
        # for your teammates right now, we will just return the raw projected set.
        # Branch 4 can hook up the minimal cover logic later!
        ds = DependencySet(projected)
        return ds


# ── ChaseLossless ────────────────────────────────────────────────────────────

class ChaseLossless:
    """Chase test for lossless-join decomposition."""

    def __init__(
        self,
        schema: Schema,
        deps: DependencySet,
        decomposition: List[Schema],
    ) -> None:
        self.schema = schema
        self.deps = deps
        self.decomposition = decomposition

    def run(self) -> ChaseLosslessResult:
        names = self.schema.names

        # Build initial tableau
        rows: List[TableauRow] = []
        for i, rel in enumerate(self.decomposition):
            rel_names = set(rel.names)
            row = TableauRow({})
            for a in names:
                if a in rel_names:
                    row[a] = TableauCell(f"a_{a}", distinguished=True)
                else:
                    row[a] = TableauCell(f"b_{i}{a}", distinguished=False)
            rows.append(row)

        steps: List[Tuple[str, List[Dict[str, str]]]] = []
        dec_str = ", ".join(str(s) for s in self.decomposition)
        steps.append((f"Initialize for [{dec_str}]", _tableau_to_dicts(rows, names)))

        changed = True
        iterations = 0
        while changed and iterations < 200:
            changed = False
            iterations += 1

            # ── FD equating rules ──
            for fd in self.deps.fds:
                fd_lhs = [a.name for a in fd.lhs]
                fd_rhs = [a.name for a in fd.rhs]

                groups: Dict[Tuple[str, ...], List[int]] = {}
                for idx, r in enumerate(rows):
                    key = tuple(r[a].symbol for a in fd_lhs)
                    groups.setdefault(key, []).append(idx)

                fd_changed = False
                for key, idxs in groups.items():
                    if len(idxs) < 2:
                        continue
                    for a in fd_rhs:
                        vals = [rows[i][a] for i in idxs]
                        best = next((v for v in vals if v.distinguished), vals[0])
                        for i in idxs:
                            if rows[i][a].symbol != best.symbol:
                                rows[i][a] = TableauCell(best.symbol, best.distinguished)
                                changed = True
                                fd_changed = True

                if fd_changed:
                    steps.append((f"Apply {fd}", _tableau_to_dicts(rows, names)))

            # ── MVD row-generation rules ──
            for mvd in self.deps.mvds:
                mvd_lhs = [a.name for a in mvd.lhs]
                mvd_rhs = [a.name for a in mvd.rhs]
                rest = [a for a in names if a not in mvd_lhs and a not in mvd_rhs]

                groups: Dict[Tuple[str, ...], List[int]] = {}
                for idx, r in enumerate(rows):
                    key = tuple(r[a].symbol for a in mvd_lhs)
                    groups.setdefault(key, []).append(idx)

                new_rows: List[TableauRow] = []
                for key, idxs in groups.items():
                    if len(idxs) < 2:
                        continue
                    for x in range(len(idxs)):
                        for y in range(x + 1, len(idxs)):
                            for src_rhs, src_rest in [(x, y), (y, x)]:
                                nr = TableauRow({})
                                for a in mvd_lhs:
                                    nr[a] = TableauCell(
                                        rows[idxs[src_rhs]][a].symbol,
                                        rows[idxs[src_rhs]][a].distinguished,
                                    )
                                for a in mvd_rhs:
                                    nr[a] = TableauCell(
                                        rows[idxs[src_rhs]][a].symbol,
                                        rows[idxs[src_rhs]][a].distinguished,
                                    )
                                for a in rest:
                                    nr[a] = TableauCell(
                                        rows[idxs[src_rest]][a].symbol,
                                        rows[idxs[src_rest]][a].distinguished,
                                    )
                                # Check duplicate
                                sig = tuple(nr[a].symbol for a in names)
                                if not any(
                                    tuple(r[a].symbol for a in names) == sig
                                    for r in rows + new_rows
                                ):
                                    new_rows.append(nr)

                if new_rows:
                    rows.extend(new_rows)
                    changed = True
                    steps.append((
                        f"Apply {mvd} (+{len(new_rows)} rows)",
                        _tableau_to_dicts(rows, names),
                    ))

            # Early exit
            if any(all(r[a].distinguished for a in names) for r in rows):
                break

        lossless = any(all(r[a].distinguished for a in names) for r in rows)
        tag = "✓ Lossless" if lossless else "✗ Not lossless"
        steps.append((tag, _tableau_to_dicts(rows, names)))

        return ChaseLosslessResult(
            decomposition=self.decomposition,
            lossless=lossless,
            steps=steps,
        )