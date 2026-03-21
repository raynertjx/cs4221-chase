"""
chase/benchmark.py
──────────────────
Benchmarking framework for comparing Chase algorithm variants.

Classes
-------
FDGenerator     – generate random FD sets of configurable size
BenchmarkRunner – run timed experiments across algorithms
BenchmarkResult – structured results with comparison stats
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import Attribute, DependencySet, FD, MVD, Schema
from .algorithms import (
    CandidateKeyFinder,
    ClosureComputer,
    MinimalCoverComputer,
)
from .chase import ChaseEntailment, ChaseLossless


# ── FDGenerator ──────────────────────────────────────────────────────────────

class FDGenerator:
    """Generate random functional dependency sets for benchmarking."""

    def __init__(self, attrs: List[str], seed: Optional[int] = None) -> None:
        self.attrs = [Attribute(a) for a in attrs]
        self.rng = random.Random(seed)

    def generate_fds(self, count: int, max_lhs: int = 3) -> DependencySet:
        """Generate *count* random FDs with LHS size up to *max_lhs*."""
        ds = DependencySet()
        for _ in range(count):
            lhs_size = self.rng.randint(1, min(max_lhs, len(self.attrs) - 1))
            lhs = frozenset(self.rng.sample(self.attrs, lhs_size))
            remaining = [a for a in self.attrs if a not in lhs]
            if not remaining:
                continue
            rhs = frozenset([self.rng.choice(remaining)])
            ds.add(FD(lhs, rhs))
        return ds

    def generate_mvds(self, count: int) -> DependencySet:
        """Generate *count* random MVDs."""
        ds = DependencySet()
        for _ in range(count):
            lhs_size = self.rng.randint(1, max(1, len(self.attrs) // 2))
            lhs_attrs = self.rng.sample(self.attrs, lhs_size)
            remaining = [a for a in self.attrs if a not in lhs_attrs]
            if not remaining:
                continue
            rhs_size = self.rng.randint(1, len(remaining))
            rhs_attrs = self.rng.sample(remaining, rhs_size)
            ds.add(MVD(lhs_attrs, rhs_attrs))
        return ds


# ── BenchmarkResult ──────────────────────────────────────────────────────────

@dataclass
class TimingEntry:
    label: str
    num_fds: int
    num_attrs: int
    operation: str
    time_ms: float
    iterations: int

    def __str__(self) -> str:
        return (
            f"{self.label:20s} | {self.operation:15s} | "
            f"FDs={self.num_fds:3d} | Attrs={self.num_attrs:2d} | "
            f"{self.time_ms:8.3f} ms/op ({self.iterations} iters)"
        )


@dataclass
class BenchmarkResult:
    """Structured benchmark output."""
    entries: List[TimingEntry] = field(default_factory=list)

    def add(self, entry: TimingEntry) -> None:
        self.entries.append(entry)

    def summary_table(self) -> str:
        """Pretty-print a comparison table."""
        if not self.entries:
            return "No benchmark entries."
        lines = [
            f"{'Label':20s} | {'Operation':15s} | {'#FDs':>5s} | {'#Attrs':>6s} | {'ms/op':>10s}",
            "-" * 75,
        ]
        for e in self.entries:
            lines.append(
                f"{e.label:20s} | {e.operation:15s} | {e.num_fds:5d} | "
                f"{e.num_attrs:6d} | {e.time_ms:10.3f}"
            )
        return "\n".join(lines)

    def group_by_operation(self) -> Dict[str, List[TimingEntry]]:
        groups: Dict[str, List[TimingEntry]] = {}
        for e in self.entries:
            groups.setdefault(e.operation, []).append(e)
        return groups

    def __str__(self) -> str:
        return self.summary_table()


# ── BenchmarkRunner ──────────────────────────────────────────────────────────

class BenchmarkRunner:
    """
    Run timed benchmarks across different FD set sizes and operations.

    Parameters
    ----------
    attr_names : list of str
        Attribute names to use.
    fd_sizes   : list of int
        Number of FDs to generate at each scale.
    iterations : int
        Repetitions per measurement for stable timing.
    seed       : int | None
        RNG seed for reproducibility.

    Usage
    -----
        runner = BenchmarkRunner(['A','B','C','D','E'], [5,10,20,40])
        result = runner.run_all()
        print(result)
    """

    def __init__(
        self,
        attr_names: List[str],
        fd_sizes: Optional[List[int]] = None,
        iterations: int = 50,
        seed: Optional[int] = None,
    ) -> None:
        self.attr_names = attr_names
        self.schema = Schema(attr_names)
        self.fd_sizes = fd_sizes or [5, 10, 20, 40, 80]
        self.iterations = iterations
        self.gen = FDGenerator(attr_names, seed=seed)

    def _time_op(self, fn: Callable[[], Any], iters: int) -> float:
        """Return average time in ms."""
        start = time.perf_counter()
        for _ in range(iters):
            fn()
        elapsed = (time.perf_counter() - start) / iters * 1000
        return elapsed

    def run_all(self) -> BenchmarkResult:
        """Run closure, minimal cover, entailment, and key-finding benchmarks."""
        result = BenchmarkResult()
        n_attrs = len(self.attr_names)

        for n_fds in self.fd_sizes:
            deps = self.gen.generate_fds(n_fds)
            label = f"{n_fds} FDs / {n_attrs} attrs"

            # Closure
            cc = ClosureComputer(self.schema, deps)
            seed_attrs = list(self.schema)[:2]
            t = self._time_op(lambda: cc.compute(frozenset(seed_attrs)), self.iterations)
            result.add(TimingEntry(label, n_fds, n_attrs, "closure", t, self.iterations))

            # Minimal cover
            mc = MinimalCoverComputer(deps)
            t = self._time_op(lambda: mc.compute(), max(10, self.iterations // 5))
            result.add(TimingEntry(label, n_fds, n_attrs, "min_cover", t, max(10, self.iterations // 5)))

            # Entailment
            target = FD(list(self.schema)[:2], [list(self.schema)[-1]])
            ce = ChaseEntailment(self.schema, deps, target)
            t = self._time_op(lambda: ce.run(), self.iterations)
            result.add(TimingEntry(label, n_fds, n_attrs, "entailment", t, self.iterations))

            # Candidate keys
            ckf = CandidateKeyFinder(self.schema, deps)
            t = self._time_op(lambda: ckf.compute(), max(5, self.iterations // 10))
            result.add(TimingEntry(label, n_fds, n_attrs, "cand_keys", t, max(5, self.iterations // 10)))

        return result

    def run_ablation(self, with_mvd: bool = True) -> BenchmarkResult:
        """
        Ablation study: compare lossless-join Chase with vs without MVD support.
        """
        result = BenchmarkResult()
        n_attrs = len(self.attr_names)

        for n_fds in self.fd_sizes[:4]:  # limit to keep runtime reasonable
            fds = self.gen.generate_fds(n_fds)
            mvds = self.gen.generate_mvds(max(1, n_fds // 3))

            # Simple 2-way decomposition
            half = n_attrs // 2
            d1 = Schema(self.attr_names[:half + 1])
            d2 = Schema(self.attr_names[half:])
            decomp = [d1, d2]

            # FD-only chase
            t = self._time_op(
                lambda: ChaseLossless(self.schema, fds, decomp).run(),
                max(5, self.iterations // 10),
            )
            result.add(TimingEntry(
                f"{n_fds} FDs (no MVD)", n_fds, n_attrs,
                "lossless_fd_only", t, max(5, self.iterations // 10),
            ))

            if with_mvd:
                # FD + MVD chase
                combined = fds.copy()
                for m in mvds:
                    combined.add(m)
                t = self._time_op(
                    lambda: ChaseLossless(self.schema, combined, decomp).run(),
                    max(5, self.iterations // 10),
                )
                result.add(TimingEntry(
                    f"{n_fds} FDs + MVDs", n_fds + len(mvds), n_attrs,
                    "lossless_fd+mvd", t, max(5, self.iterations // 10),
                ))

        return result
