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

from .models import Attribute, DependencySet, FD, MVD, Schema, TableInstance
from .entailment import ChaseEntailment
from .chase import ChaseLossless

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
    num_rows: Optional[int] = None
    stats: Dict[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        row_tag = f" | Rows={self.num_rows:4d}" if self.num_rows is not None else ""
        return (
            f"{self.label:20s} | {self.operation:15s} | "
            f"FDs={self.num_fds:3d} | Attrs={self.num_attrs:2d} | "
            f"{self.time_ms:8.3f} ms/op ({self.iterations} iters){row_tag}"
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
            f"{'Label':20s} | {'Operation':15s} | {'#FDs':>5s} | {'#Attrs':>6s} | {'#Rows':>6s} | {'ms/op':>10s}",
            "-" * 86,
        ]
        for e in self.entries:
            row_count = "-" if e.num_rows is None else str(e.num_rows)
            lines.append(
                f"{e.label:20s} | {e.operation:15s} | {e.num_fds:5d} | "
                f"{e.num_attrs:6d} | {row_count:>6s} | {e.time_ms:10.3f}"
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
        runner = BenchmarkRunner(['A','B','C','D','E'], [4,8,12,16,20,24])
        result = runner.run_all()
        print(result)
    """

    def __init__(
        self,
        attr_names: List[str],
        fd_sizes: Optional[List[int]] = None,
        iterations: int = 50,
        seed: Optional[int] = None,
        benchmark_seeds: Optional[List[int]] = None,
    ) -> None:
        self.attr_names = attr_names
        self.schema = Schema(attr_names)
        self.fd_sizes = fd_sizes or [4, 8, 12, 16, 20, 24]
        self.iterations = iterations
        self.seed = seed
        self.rng = random.Random(seed)
        self.benchmark_seeds = benchmark_seeds or ([seed] if seed is not None else [42])

    def _time_op(self, fn: Callable[[], Any], iters: int) -> float:
        """Return average time in ms."""
        start = time.perf_counter()
        for _ in range(iters):
            fn()
        elapsed = (time.perf_counter() - start) / iters * 1000
        return elapsed

    def _mean(self, values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _attr_names_for(self, count: int) -> List[str]:
        if count <= len(self.attr_names):
            return self.attr_names[:count]
        names = list(self.attr_names)
        i = 0
        while len(names) < count:
            names.append(f"A{i}")
            i += 1
        return names

    def _generate_table(self, attrs: List[str], num_rows: int) -> TableInstance:
        rows: List[Dict[str, str]] = []
        domain = max(3, min(8, len(attrs) + 1))
        for _ in range(num_rows):
            row = {
                a: f"v{self.rng.randint(0, domain - 1)}"
                for a in attrs
            }
            rows.append(row)
        return TableInstance(Schema(attrs), rows)

    def _measure_lossless(
        self,
        schema: Schema,
        deps: DependencySet,
        decomp: List[Schema],
        iterations: int,
    ) -> Tuple[float, float, float]:
        start = time.perf_counter()
        total_steps = 0.0
        total_rows = 0.0

        for _ in range(iterations):
            result = ChaseLossless(schema, deps, decomp).run()
            total_steps += len(result.steps)
            total_rows += len(result.steps[-1][1]) if result.steps else 0

        elapsed = (time.perf_counter() - start) / iterations * 1000
        return elapsed, total_steps / iterations, total_rows / iterations

    def run_all(self) -> BenchmarkResult:
        """Run Chase-only benchmarks across dependency-set sizes."""
        result = BenchmarkResult()
        n_attrs = len(self.attr_names)

        for n_fds in self.fd_sizes:
            label = f"|Σ|={n_fds} / |U|={n_attrs}"
            entailment_samples: List[float] = []
            lossless_samples: List[float] = []
            lossless_steps: List[float] = []
            lossless_rows: List[float] = []

            for benchmark_seed in self.benchmark_seeds:
                deps = FDGenerator(self.attr_names, seed=benchmark_seed).generate_fds(n_fds)

                target = FD(list(self.schema)[:2], [list(self.schema)[-1]])
                ce = ChaseEntailment(self.schema, deps, target)
                entailment_samples.append(self._time_op(lambda: ce.run(), self.iterations))

                half = n_attrs // 2
                d1 = Schema(self.attr_names[:half + 1])
                d2 = Schema(self.attr_names[half:])
                decomp = [d1, d2]
                lossless_iters = max(5, self.iterations // 2)
                t, avg_steps, avg_rows = self._measure_lossless(
                    self.schema, deps, decomp, lossless_iters
                )
                lossless_samples.append(t)
                lossless_steps.append(avg_steps)
                lossless_rows.append(avg_rows)

            result.add(TimingEntry(
                label,
                n_fds,
                n_attrs,
                "entailment",
                self._mean(entailment_samples),
                self.iterations,
                stats={"num_workloads": float(len(self.benchmark_seeds))},
            ))
            result.add(TimingEntry(
                label,
                n_fds,
                n_attrs,
                "lossless",
                self._mean(lossless_samples),
                lossless_iters,
                stats={
                    "avg_steps": self._mean(lossless_steps),
                    "avg_final_rows": self._mean(lossless_rows),
                    "num_workloads": float(len(self.benchmark_seeds)),
                },
            ))

        return result

    def run_attr_scaling(
        self,
        attr_sizes: Optional[List[int]] = None,
    ) -> BenchmarkResult:
        """
        Benchmark Chase-only operations as schema width grows.
        """
        result = BenchmarkResult()
        attr_sizes = attr_sizes or sorted(set([4, 6, 8, len(self.attr_names)]))

        for num_attrs in attr_sizes:
            if num_attrs < 2:
                continue
            attrs = self._attr_names_for(num_attrs)
            schema = Schema(attrs)
            fd_count = max(4, num_attrs * 2)
            label = f"|U|={num_attrs} / |Σ|={fd_count}"
            entailment_samples: List[float] = []
            lossless_samples: List[float] = []
            lossless_steps: List[float] = []
            lossless_rows: List[float] = []

            for benchmark_seed in self.benchmark_seeds:
                deps = FDGenerator(attrs, seed=benchmark_seed).generate_fds(
                    fd_count, max_lhs=min(3, num_attrs - 1)
                )

                target = FD(list(schema)[: min(2, num_attrs)], [list(schema)[-1]])
                ce = ChaseEntailment(schema, deps, target)
                entailment_samples.append(self._time_op(lambda: ce.run(), self.iterations))

                half = num_attrs // 2
                d1 = Schema(attrs[:half + 1])
                d2 = Schema(attrs[half:])
                decomp = [d1, d2]
                lossless_iters = max(5, self.iterations // 2)
                t, avg_steps, avg_rows = self._measure_lossless(
                    schema, deps, decomp, lossless_iters
                )
                lossless_samples.append(t)
                lossless_steps.append(avg_steps)
                lossless_rows.append(avg_rows)

            result.add(TimingEntry(
                label,
                fd_count,
                num_attrs,
                "entailment_attr",
                self._mean(entailment_samples),
                self.iterations,
                stats={"num_workloads": float(len(self.benchmark_seeds))},
            ))
            result.add(TimingEntry(
                label,
                fd_count,
                num_attrs,
                "lossless_attr",
                self._mean(lossless_samples),
                lossless_iters,
                stats={
                    "avg_steps": self._mean(lossless_steps),
                    "avg_final_rows": self._mean(lossless_rows),
                    "num_workloads": float(len(self.benchmark_seeds)),
                },
            ))

        return result

    def run_ablation(self, with_mvd: bool = True) -> BenchmarkResult:
        """
        Ablation study: compare lossless-join Chase with vs without MVD support.
        """
        result = BenchmarkResult()
        n_attrs = len(self.attr_names)

        for n_fds in self.fd_sizes:
            ablation_iters = max(5, self.iterations // 10)
            fd_only_samples: List[float] = []
            fd_only_steps: List[float] = []
            fd_only_rows: List[float] = []
            mixed_samples: List[float] = []
            mixed_steps: List[float] = []
            mixed_rows: List[float] = []
            mvd_counts: List[float] = []

            for benchmark_seed in self.benchmark_seeds:
                gen = FDGenerator(self.attr_names, seed=benchmark_seed)
                fds = gen.generate_fds(n_fds)
                mvds = gen.generate_mvds(max(1, n_fds // 3))

                half = n_attrs // 2
                d1 = Schema(self.attr_names[:half + 1])
                d2 = Schema(self.attr_names[half:])
                decomp = [d1, d2]

                t, avg_steps, avg_rows = self._measure_lossless(
                    self.schema, fds, decomp, ablation_iters
                )
                fd_only_samples.append(t)
                fd_only_steps.append(avg_steps)
                fd_only_rows.append(avg_rows)

                if with_mvd:
                    combined = fds.copy()
                    for m in mvds:
                        combined.add(m)
                    t, avg_steps, avg_rows = self._measure_lossless(
                        self.schema, combined, decomp, ablation_iters
                    )
                    mixed_samples.append(t)
                    mixed_steps.append(avg_steps)
                    mixed_rows.append(avg_rows)
                    mvd_counts.append(float(len(mvds)))

            result.add(TimingEntry(
                f"|Σ|={n_fds} (FD-only)", n_fds, n_attrs,
                "lossless_fd_only", self._mean(fd_only_samples), ablation_iters,
                stats={
                    "avg_steps": self._mean(fd_only_steps),
                    "avg_final_rows": self._mean(fd_only_rows),
                    "num_workloads": float(len(self.benchmark_seeds)),
                },
            ))

            if with_mvd:
                result.add(TimingEntry(
                    f"|Σ|={n_fds} (FD+MVD)", n_fds, n_attrs,
                    "lossless_fd+mvd", self._mean(mixed_samples), ablation_iters,
                    stats={
                        "avg_steps": self._mean(mixed_steps),
                        "avg_final_rows": self._mean(mixed_rows),
                        "num_mvds": self._mean(mvd_counts),
                        "num_workloads": float(len(self.benchmark_seeds)),
                    },
                ))

        return result
