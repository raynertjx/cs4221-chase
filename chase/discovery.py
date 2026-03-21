"""
chase/discovery.py
──────────────────
Discover functional dependencies from a table instance using
chase-style partition refinement.

Inspired by pratik2358/fucntional_dep's discover_fds_with_chase(),
refactored into an OOP interface.

Classes
-------
FDDiscoverer – discover minimal FDs from a TableInstance or DataFrame
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .models import Attribute, DependencySet, FD, Schema, TableInstance


# ── Result ───────────────────────────────────────────────────────────────────

@dataclass
class DiscoveryResult:
    """Result of FD discovery."""
    discovered_fds: DependencySet
    num_rows: int
    num_attrs: int

    def __str__(self) -> str:
        lines = [f"Discovered {len(self.discovered_fds)} FDs from {self.num_rows} rows, {self.num_attrs} attributes:"]
        for fd in self.discovered_fds:
            lines.append(f"  {fd}")
        return "\n".join(lines)


# ── Partition helpers ────────────────────────────────────────────────────────

class _PartitionCache:
    """
    Cache of column-set partitions keyed by bitmask.
    A partition is a list of frozensets of row indices.
    """

    def __init__(self, rows: List[Dict[str, str]], attrs: List[str]) -> None:
        self._rows = rows
        self._attrs = attrs
        self._nrows = len(rows)
        self._attr_to_bit = {a: i for i, a in enumerate(attrs)}
        self._bit_to_attr = {i: a for a, i in self._attr_to_bit.items()}
        self._cache: Dict[int, List[FrozenSet[int]]] = {}

        # Single-attribute partitions
        for a in attrs:
            b = 1 << self._attr_to_bit[a]
            self._cache[b] = self._partition_cols([a])

        # Empty-set partition
        self._cache[0] = [frozenset(range(self._nrows))]

    def _partition_cols(self, cols: List[str]) -> List[FrozenSet[int]]:
        groups: Dict[tuple, List[int]] = defaultdict(list)
        for i, row in enumerate(self._rows):
            key = tuple(row.get(c, "") for c in cols)
            groups[key].append(i)
        return [frozenset(g) for g in groups.values()]

    def get(self, bitmask: int) -> List[FrozenSet[int]]:
        if bitmask in self._cache:
            return self._cache[bitmask]
        # Split: use least significant bit
        lsb = bitmask & -bitmask
        rest = bitmask ^ lsb
        p_rest = self.get(rest)
        p_lsb = self.get(lsb)
        refined = self._refine(p_rest, p_lsb)
        self._cache[bitmask] = refined
        return refined

    def _refine(
        self, part_a: List[FrozenSet[int]], part_b: List[FrozenSet[int]]
    ) -> List[FrozenSet[int]]:
        pos_a = [0] * self._nrows
        pos_b = [0] * self._nrows
        for bid, block in enumerate(part_a):
            for r in block:
                pos_a[r] = bid
        for bid, block in enumerate(part_b):
            for r in block:
                pos_b[r] = bid
        inter: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for r in range(self._nrows):
            inter[(pos_a[r], pos_b[r])].append(r)
        return [frozenset(v) for v in inter.values()]

    def attr_to_bit(self, a: str) -> int:
        return self._attr_to_bit[a]

    def bits_to_attrs(self, bitmask: int) -> List[str]:
        return [self._bit_to_attr[i] for i in range(len(self._attrs)) if bitmask & (1 << i)]


# ── FDDiscoverer ─────────────────────────────────────────────────────────────

class FDDiscoverer:
    """
    Discover a minimal cover of FDs from a table instance using
    chase-style partition refinement.

    Parameters
    ----------
    table    : TableInstance
    max_lhs  : int | None
        Cap on LHS size to control runtime on wide tables.

    Usage
    -----
        result = FDDiscoverer(table).run()
        print(result.discovered_fds)
    """

    def __init__(self, table: TableInstance, max_lhs: Optional[int] = None) -> None:
        self.table = table
        self.max_lhs = max_lhs

    def run(self) -> DiscoveryResult:
        attrs = self.table.schema.names
        rows = self.table.rows
        n = len(attrs)

        if n == 0 or len(rows) == 0:
            return DiscoveryResult(DependencySet(), len(rows), n)

        cache = _PartitionCache(rows, attrs)
        raw_fds: List[Tuple[Tuple[str, ...], str]] = []

        for rhs in attrs:
            rhs_bit = cache.attr_to_bit(rhs)
            lhs_pool = [a for a in attrs if a != rhs]
            minimal_lhss: List[int] = []
            max_k = self.max_lhs if self.max_lhs is not None else len(lhs_pool)

            for k in range(0, max_k + 1):
                candidates = []
                for combo in combinations(lhs_pool, k):
                    bm = 0
                    for a in combo:
                        bm |= 1 << cache.attr_to_bit(a)
                    # Prune supersets of known minimals
                    if any((bm & m) == m for m in minimal_lhss):
                        continue
                    candidates.append(bm)

                for bm in candidates:
                    p_x = cache.get(bm)
                    p_xa = cache.get(bm | (1 << rhs_bit))
                    if len(p_x) == len(p_xa):
                        # Found X → rhs; try to reduce LHS
                        x = bm
                        for a in cache.bits_to_attrs(bm):
                            abit = 1 << cache.attr_to_bit(a)
                            if x & abit:
                                x2 = x ^ abit
                                if len(cache.get(x2)) == len(cache.get(x2 | (1 << rhs_bit))):
                                    x = x2
                        minimal_lhss.append(x)
                        lhs_names = tuple(sorted(cache.bits_to_attrs(x)))
                        raw_fds.append((lhs_names, rhs))

                if any(m == 0 for m in minimal_lhss):
                    break

        # Deduplicate and minimise
        per_rhs: Dict[str, List[int]] = defaultdict(list)
        for lhs_names, rhs in raw_fds:
            bm = 0
            for a in lhs_names:
                bm |= 1 << cache.attr_to_bit(a)
            per_rhs[rhs].append(bm)

        ds = DependencySet()
        for rhs, bm_list in per_rhs.items():
            bm_list = sorted(set(bm_list), key=lambda x: (bin(x).count("1"), x))
            keep = []
            for i, x in enumerate(bm_list):
                if any((y & x) == y for j, y in enumerate(bm_list) if j != i):
                    continue
                keep.append(x)
            for bm in keep:
                lhs = cache.bits_to_attrs(bm)
                ds.add(FD(lhs, [rhs]))

        return DiscoveryResult(
            discovered_fds=ds,
            num_rows=len(rows),
            num_attrs=n,
        )

    @classmethod
    def from_dataframe(cls, df, max_lhs: Optional[int] = None) -> FDDiscoverer:
        """Factory from a pandas DataFrame."""
        table = TableInstance.from_dataframe(df)
        return cls(table, max_lhs=max_lhs)
