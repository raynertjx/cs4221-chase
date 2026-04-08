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
from typing import Dict, List, Optional 

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
        Number of unique dependency sets generated per measurement for stable statistical averaging.
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
    ) -> None:
        self.attr_names = attr_names
        self.schema = Schema(attr_names)
        self.fd_sizes = fd_sizes or [4, 8, 12, 16, 20, 24]
        self.iterations = iterations
        self.seed = seed
        self.gen = FDGenerator(attr_names, seed=seed)
        self.rng = random.Random(seed)

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

    def run_all(self) -> BenchmarkResult:
        """Run Chase-only benchmarks across dependency-set sizes."""
        result = BenchmarkResult()
        n_attrs = len(self.attr_names)
        num_samples = self.iterations

        for n_fds in self.fd_sizes:
            label = f"|Σ|={n_fds} / |U|={n_attrs}"
            target = FD(list(self.schema)[:2], [list(self.schema)[-1]])
            
            # --- Entailment Benchmark ---
            total_entailment_time = 0.0
            
            for _ in range(num_samples):
                deps = self.gen.generate_fds(n_fds)
                ce = ChaseEntailment(self.schema, deps, target)
                
                start = time.perf_counter()
                ce.run()
                total_entailment_time += (time.perf_counter() - start) * 1000
                
            avg_entailment_time = total_entailment_time / num_samples
            result.add(TimingEntry(label, n_fds, n_attrs, "entailment", avg_entailment_time, num_samples))

            # --- Lossless Benchmark ---
            half = n_attrs // 2
            decomp = [Schema(self.attr_names[:half + 1]), Schema(self.attr_names[half:])]
            
            total_lossless_time = 0.0
            total_steps = 0
            total_rows = 0
            lossless_samples = max(5, num_samples // 2)

            for _ in range(lossless_samples):
                deps = self.gen.generate_fds(n_fds)
                cl = ChaseLossless(self.schema, deps, decomp)
                
                start = time.perf_counter()
                res = cl.run()
                total_lossless_time += (time.perf_counter() - start) * 1000
                
                total_steps += len(res.steps)
                total_rows += len(res.steps[-1][1]) if res.steps else 0

            avg_lossless_time = total_lossless_time / lossless_samples
            result.add(TimingEntry(
                label, n_fds, n_attrs, "lossless", avg_lossless_time, lossless_samples,
                stats={
                    "avg_steps": total_steps / lossless_samples, 
                    "avg_final_rows": total_rows / lossless_samples
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
        num_samples = self.iterations

        for num_attrs in attr_sizes:
            if num_attrs < 2:
                continue
            attrs = self._attr_names_for(num_attrs)
            schema = Schema(attrs)
            gen = FDGenerator(attrs, seed=self.seed)
            fd_count = max(4, num_attrs * 2)
            label = f"|U|={num_attrs} / |Σ|={fd_count}"

            target = FD(list(schema)[: min(2, num_attrs)], [list(schema)[-1]])
            
            # --- Entailment Benchmark ---
            total_entailment_time = 0.0
            for _ in range(num_samples):
                deps = gen.generate_fds(fd_count, max_lhs=min(3, num_attrs - 1))
                ce = ChaseEntailment(schema, deps, target)
                
                start = time.perf_counter()
                ce.run()
                total_entailment_time += (time.perf_counter() - start) * 1000
                
            avg_entailment_time = total_entailment_time / num_samples
            result.add(TimingEntry(label, fd_count, num_attrs, "entailment_attr", avg_entailment_time, num_samples))

            # --- Lossless Benchmark ---
            half = num_attrs // 2
            decomp = [Schema(attrs[:half + 1]), Schema(attrs[half:])]
            
            total_lossless_time = 0.0
            total_steps = 0
            total_rows = 0
            lossless_samples = max(5, num_samples // 2)

            for _ in range(lossless_samples):
                deps = gen.generate_fds(fd_count, max_lhs=min(3, num_attrs - 1))
                cl = ChaseLossless(schema, deps, decomp)
                
                start = time.perf_counter()
                res = cl.run()
                total_lossless_time += (time.perf_counter() - start) * 1000
                
                total_steps += len(res.steps)
                total_rows += len(res.steps[-1][1]) if res.steps else 0

            avg_lossless_time = total_lossless_time / lossless_samples
            result.add(TimingEntry(
                label, fd_count, num_attrs, "lossless_attr", avg_lossless_time, lossless_samples,
                stats={
                    "avg_steps": total_steps / lossless_samples, 
                    "avg_final_rows": total_rows / lossless_samples
                },
            ))

        return result

    def run_ablation(self, with_mvd: bool = True) -> BenchmarkResult:
        """
        Ablation study: compare lossless-join Chase with vs without MVD support.
        """
        result = BenchmarkResult()
        n_attrs = len(self.attr_names)
        half = n_attrs // 2
        decomp = [Schema(self.attr_names[:half + 1]), Schema(self.attr_names[half:])]
        ablation_samples = max(5, self.iterations // 10)

        for n_fds in self.fd_sizes:
            total_time_fd = 0.0
            total_steps_fd = 0
            total_rows_fd = 0
            
            total_time_comb = 0.0
            total_steps_comb = 0
            total_rows_comb = 0
            total_mvds = 0

            for _ in range(ablation_samples):
                fds = self.gen.generate_fds(n_fds)
                
                # FD-only chase run
                cl_fd = ChaseLossless(self.schema, fds, decomp)
                start = time.perf_counter()
                res_fd = cl_fd.run()
                total_time_fd += (time.perf_counter() - start) * 1000
                total_steps_fd += len(res_fd.steps)
                total_rows_fd += len(res_fd.steps[-1][1]) if res_fd.steps else 0

                if with_mvd:
                    mvds = self.gen.generate_mvds(max(1, n_fds // 3))
                    total_mvds += len(mvds)
                    
                    combined = fds.copy()
                    for m in mvds:
                        combined.add(m)
                        
                    # FD + MVD chase run
                    cl_comb = ChaseLossless(self.schema, combined, decomp)
                    start = time.perf_counter()
                    res_comb = cl_comb.run()
                    total_time_comb += (time.perf_counter() - start) * 1000
                    total_steps_comb += len(res_comb.steps)
                    total_rows_comb += len(res_comb.steps[-1][1]) if res_comb.steps else 0

            result.add(TimingEntry(
                f"|Σ|={n_fds} (FD-only)", n_fds, n_attrs,
                "lossless_fd_only", total_time_fd / ablation_samples, ablation_samples,
                stats={
                    "avg_steps": total_steps_fd / ablation_samples, 
                    "avg_final_rows": total_rows_fd / ablation_samples
                },
            ))

            if with_mvd:
                result.add(TimingEntry(
                    f"|Σ|={n_fds} (FD+MVD)", n_fds, n_attrs,
                    "lossless_fd+mvd", total_time_comb / ablation_samples, ablation_samples,
                    stats={
                        "avg_steps": total_steps_comb / ablation_samples,
                        "avg_final_rows": total_rows_comb / ablation_samples,
                        "num_mvds": total_mvds / ablation_samples,
                    },
                ))

        return result