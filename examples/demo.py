"""
examples/demo.py
────────────────
Full demonstration of the Chase toolkit.
Covers every major feature 

Run:  python examples/demo.py
"""

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chase import (
    Schema, FD, MVD, DependencySet, TableInstance,
    ClosureComputer, MinimalCoverComputer, CandidateKeyFinder, ProjectionComputer,
    ChaseEntailment, ChaseLossless, ChaseTableValidator,
    FDDiscoverer, BenchmarkRunner, ThreeNFDecomposer, BCNFDecomposer,
)


def divider(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ═══════════════════════════════════════════════════════════════════════════
#  1. MODELS 
# ═══════════════════════════════════════════════════════════════════════════

divider("1. Creating dependencies (pratik2358-compatible format)")

pratik_fds = [
    ({'A'}, {'A', 'B', 'C'}),
    ({'A', 'B'}, {'A'}),
    ({'B', 'C'}, {'A', 'D'}),
    ({'B'}, {'A', 'B'}),
    ({'C'}, {'D'}),
]
deps_from_tuples = DependencySet.from_tuples(pratik_fds)
print(f"From tuples: {len(deps_from_tuples)} FDs")
for fd in deps_from_tuples:
    print(f"  {fd}")

# Text format
deps_from_text = DependencySet.from_strings([
    "A,B -> C",
    "C -> D",
    "D -> A",
    "A ->> B",   # MVD
])
print(f"\nFrom text: {len(deps_from_text)} deps ({len(deps_from_text.fds)} FDs, {len(deps_from_text.mvds)} MVDs)")
for d in deps_from_text:
    print(f"  {d}")


# ═══════════════════════════════════════════════════════════════════════════
#  2. ATTRIBUTE CLOSURE
# ═══════════════════════════════════════════════════════════════════════════

divider("2. Attribute Closure")

schema = Schema(["A", "B", "C", "D"])
deps = DependencySet.from_strings(["A,B -> C", "C -> D", "D -> A"])
cc = ClosureComputer(schema, deps)

for attrs in [["A", "B"], ["C"], ["A"], ["B", "C"]]:
    result = cc.compute(attrs)
    print(f"  {result}")


# ═══════════════════════════════════════════════════════════════════════════
#  3. MINIMAL COVER
# ═══════════════════════════════════════════════════════════════════════════

divider("3. Minimal Cover")

deps_redundant = DependencySet.from_strings([
    "A,B -> C",
    "A,B -> D",
    "A -> C",       # makes A,B -> C redundant
    "C -> D",
    "D -> A",
])
mc = MinimalCoverComputer(deps_redundant).compute()
print(mc)
print(f"\nSteps ({len(mc.steps)}):")
for step_desc, step_deps in mc.steps:
    print(f"  [{step_desc}] → {len(step_deps)} FDs")


# ═══════════════════════════════════════════════════════════════════════════
#  4. CANDIDATE KEYS
# ═══════════════════════════════════════════════════════════════════════════

divider("4. Candidate Keys")

schema5 = Schema(["S", "C", "I", "G", "R"])
deps_uni = DependencySet.from_strings([
    "S,C -> G",
    "C -> I",
    "I -> C",
    "S,C -> R",
])
keys = CandidateKeyFinder(schema5, deps_uni).compute()
print(keys)


# ═══════════════════════════════════════════════════════════════════════════
#  5. CHASE ENTAILMENT
# ═══════════════════════════════════════════════════════════════════════════

divider("5. Chase Entailment")

schema = Schema(["A", "B", "C", "D"])
deps = DependencySet.from_strings(["A,B -> C", "C -> D", "D -> A"])

# Positive case
target = FD(["A", "B"], ["D"])
result = ChaseEntailment(schema, deps, target).run()
print(f"  {result}")
print(f"  Steps:")
for desc, tableau in result.steps:
    print(f"    {desc}")

# Negative case
target2 = FD(["D"], ["B"])
result2 = ChaseEntailment(schema, deps, target2).run()
print(f"\n  {result2}")


# ═══════════════════════════════════════════════════════════════════════════
#  6. LOSSLESS-JOIN DECOMPOSITION
# ═══════════════════════════════════════════════════════════════════════════

divider("6. Lossless-Join Test")

schema = Schema(["A", "B", "C", "D", "E"])
deps = DependencySet.from_strings(["A -> B,C", "C -> D", "D -> E"])
decomp = [Schema(["A", "B", "C"]), Schema(["C", "D"]), Schema(["D", "E"])]

result = ChaseLossless(schema, deps, decomp).run()
print(f"  {result}")
for desc, _ in result.steps:
    print(f"    {desc}")

# With MVD
divider("6b. Lossless with MVD")
schema4 = Schema(["A", "B", "C", "D"])
deps_mvd = DependencySet.from_strings(["A ->> B", "A -> C"])
decomp_mvd = [Schema(["A", "B"]), Schema(["A", "C", "D"])]
result_mvd = ChaseLossless(schema4, deps_mvd, decomp_mvd).run()
print(f"  {result_mvd}")

divider("6c. BCNF Decomposition")
schema6 = Schema(["A", "B", "C", "D", "E", "F"])
deps6 = DependencySet.from_strings([
    "C -> E",
    "E -> C",
    "D -> C, E",
    "B, C -> A, D",
    "B, E -> A, D"
])
decomposer = BCNFDecomposer(schema6, deps6)
result6 = decomposer.decompose()
print(f"  Fragments:")
for frag in result6.fragments:
    print(f"    {frag}")
print(f"  Dependency preserved? {result6.dependency_preserved}")

divider("6d. 3NF Decomposition")
decomposer_3nf = ThreeNFDecomposer(schema6, deps6)
result_3nf = decomposer_3nf.decompose()
print(f"  Fragments:")
for frag in result_3nf.fragments:
    print(f"    {frag}")



# ═══════════════════════════════════════════════════════════════════════════
#  7. TABLE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

divider("7. Table → FD Validation")

schema3 = Schema(["A", "B", "C"])
table = TableInstance.from_csv_text(schema3, "1, 2, 3\n1, 2, 4\n2, 3, 3")
deps_check = DependencySet.from_strings(["A -> B", "A -> C", "B -> C"])
result = ChaseTableValidator(table, deps_check).run()
print(result)


# ═══════════════════════════════════════════════════════════════════════════
#  8. FD DISCOVERY FROM TABLE
# ═══════════════════════════════════════════════════════════════════════════

divider("8. FD Discovery from Table")

schema_disc = Schema(["Name", "Dept", "Manager"])
table_disc = TableInstance(schema_disc, [
    {"Name": "Alice",   "Dept": "CS",   "Manager": "Prof X"},
    {"Name": "Bob",     "Dept": "CS",   "Manager": "Prof X"},
    {"Name": "Charlie", "Dept": "Math", "Manager": "Prof Y"},
    {"Name": "Diana",   "Dept": "Math", "Manager": "Prof Y"},
    {"Name": "Eve",     "Dept": "EE",   "Manager": "Prof Z"},
])
discovery = FDDiscoverer(table_disc).run()
print(discovery)


# ═══════════════════════════════════════════════════════════════════════════
#  9. PROJECTION
# ═══════════════════════════════════════════════════════════════════════════

divider("9. FD Projection")

schema = Schema(["A", "B", "C", "D"])
deps = DependencySet.from_strings(["A -> B", "B -> C", "C -> D"])
proj = ProjectionComputer(schema, deps).project(["A", "B", "C"])
print(f"  Projected onto {{A, B, C}}:")
for fd in proj:
    print(f"    {fd}")


# ═══════════════════════════════════════════════════════════════════════════
#  10. BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════

divider("10. Performance Benchmark")

runner = BenchmarkRunner(
    attr_names=["A", "B", "C", "D", "E", "F"],
    fd_sizes=[5, 10, 20, 40],
    iterations=20,
    seed=42,
)
bench = runner.run_all()
print(bench)

divider("10b. Ablation: FD-only vs FD+MVD Lossless Chase")
ablation = runner.run_ablation()
print(ablation)


print(f"\n{'═'*60}")
print("  Demo complete!")
print(f"{'═'*60}")
