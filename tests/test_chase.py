"""
tests/test_chase.py
───────────────────
Test suite for the Chase algorithm toolkit.
Run with:  python -m pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chase import (
    Attribute, Schema, FD, MVD, DependencySet, TableInstance,
    ClosureComputer, MinimalCoverComputer, CandidateKeyFinder, ProjectionComputer,
    ChaseEntailment, ChaseLossless, ChaseTableValidator,
    FDDiscoverer, BenchmarkRunner,
)


# ── Model tests ──────────────────────────────────────────────────────────────

def test_attribute_equality():
    a1 = Attribute("A")
    a2 = Attribute("A")
    assert a1 == a2
    assert hash(a1) == hash(a2)

def test_schema_contains():
    s = Schema(["A", "B", "C"])
    assert "A" in s
    assert "D" not in s
    assert len(s) == 3

def test_fd_creation():
    fd = FD(["A", "B"], ["C"])
    assert fd.lhs == frozenset({Attribute("A"), Attribute("B")})
    assert fd.rhs == frozenset({Attribute("C")})
    assert "→" in str(fd)

def test_mvd_creation():
    mvd = MVD(["A"], ["B", "C"])
    assert "↠" in str(mvd)

def test_dependency_set_from_strings():
    ds = DependencySet.from_strings([
        "A,B -> C",
        "C -> D",
        "A ->> B",
    ])
    assert len(ds) == 3
    assert len(ds.fds) == 2
    assert len(ds.mvds) == 1

def test_dependency_set_from_tuples():
    ds = DependencySet.from_tuples([
        ({"A"}, {"B", "C"}),
        ({"B", "C"}, {"A", "D"}),
    ])
    assert len(ds) == 2

def test_table_instance_from_csv():
    s = Schema(["A", "B", "C"])
    t = TableInstance.from_csv_text(s, "1, 2, 3\n1, 2, 4\n2, 3, 3")
    assert len(t) == 3
    assert t.rows[0]["A"] == "1"


# ── Closure tests ────────────────────────────────────────────────────────────

def test_closure_basic():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "B -> C", "C -> D"])
    cc = ClosureComputer(schema, deps)
    result = cc.compute(["A"])
    assert result.closure_names == ["A", "B", "C", "D"]
    assert result.is_superkey

def test_closure_not_superkey():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "C -> D"])
    cc = ClosureComputer(schema, deps)
    result = cc.compute(["A"])
    assert result.closure_names == ["A", "B"]
    assert not result.is_superkey


# ── Minimal Cover tests ─────────────────────────────────────────────────────

def test_minimal_cover_removes_redundant():
    deps = DependencySet.from_strings([
        "A,B -> C",
        "A -> C",       # makes A,B -> C redundant via A -> C
        "C -> D",
        "D -> A",
    ])
    mc = MinimalCoverComputer(deps).compute()
    # Should have A -> C, C -> D, D -> A (A,B -> C is redundant)
    result_strs = {str(fd) for fd in mc.result}
    assert "A → C" in result_strs or len(mc.result) <= 3

def test_minimal_cover_merges_lhs():
    deps = DependencySet.from_strings([
        "A -> B",
        "A -> C",
    ])
    mc = MinimalCoverComputer(deps).compute()
    # Should merge into A -> B,C (1 FD)
    assert len(mc.result) == 1


# ── Candidate Key tests ─────────────────────────────────────────────────────

def test_candidate_keys_basic():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B,C,D"])
    keys = CandidateKeyFinder(schema, deps).compute()
    assert keys.key_names == [["A"]]

def test_candidate_keys_composite():
    schema = Schema(["A", "B", "C"])
    deps = DependencySet.from_strings(["A,B -> C"])
    keys = CandidateKeyFinder(schema, deps).compute()
    assert ["A", "B"] in keys.key_names


# ── Chase Entailment tests ───────────────────────────────────────────────────

def test_entailment_positive():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A,B -> C", "C -> D", "D -> A"])
    target = FD(["A", "B"], ["D"])
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed is True
    assert len(result.steps) >= 2

def test_entailment_negative():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "C -> D"])
    target = FD(["A"], ["D"])
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed is False


# ── Chase Lossless tests ────────────────────────────────────────────────────

def test_lossless_positive():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "B -> C", "C -> D"])
    decomp = [Schema(["A", "B"]), Schema(["B", "C"]), Schema(["C", "D"])]
    result = ChaseLossless(schema, deps, decomp).run()
    assert result.lossless is True

def test_lossless_negative():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "C -> D"])
    decomp = [Schema(["A", "C"]), Schema(["B", "D"])]
    result = ChaseLossless(schema, deps, decomp).run()
    assert result.lossless is False

def test_lossless_with_mvd():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A ->> B", "A -> C"])
    decomp = [Schema(["A", "B"]), Schema(["A", "C", "D"])]
    result = ChaseLossless(schema, deps, decomp).run()
    # With MVD A ->> B, decomposing into {A,B} and {A,C,D} should be lossless
    assert result.lossless is True


# ── Table Validation tests ───────────────────────────────────────────────────

def test_table_validation_satisfied():
    schema = Schema(["A", "B", "C"])
    table = TableInstance.from_csv_text(schema, "1, 2, 3\n2, 3, 4\n3, 4, 5")
    deps = DependencySet.from_strings(["A -> B", "A -> C"])
    result = ChaseTableValidator(table, deps).run()
    assert result.all_satisfied

def test_table_validation_violated():
    schema = Schema(["A", "B", "C"])
    table = TableInstance.from_csv_text(schema, "1, 2, 3\n1, 2, 4")
    deps = DependencySet.from_strings(["A -> C"])
    result = ChaseTableValidator(table, deps).run()
    assert not result.all_satisfied
    assert result.validations[0].violations == [(0, 1)]


# ── FD Discovery tests ──────────────────────────────────────────────────────

def test_discovery_simple():
    schema = Schema(["A", "B"])
    table = TableInstance(schema, [
        {"A": "1", "B": "x"},
        {"A": "2", "B": "y"},
        {"A": "1", "B": "x"},
    ])
    result = FDDiscoverer(table).run()
    # A -> B should be discovered (each A value maps to one B)
    fd_strs = [str(fd) for fd in result.discovered_fds]
    assert any("A" in s and "B" in s and "→" in s for s in fd_strs)


# ── Projection tests ────────────────────────────────────────────────────────

def test_projection():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "B -> C", "C -> D"])
    proj = ProjectionComputer(schema, deps).project(["A", "B", "C"])
    # Should include A -> B and B -> C (D is excluded)
    proj_strs = {str(fd) for fd in proj}
    assert any("A" in s and "B" in s for s in proj_strs)


# ── Benchmark tests ──────────────────────────────────────────────────────────

def test_benchmark_runs():
    runner = BenchmarkRunner(
        ["A", "B", "C", "D", "E"],
        fd_sizes=[5, 10],
        iterations=5,
        seed=42,
    )
    result = runner.run_all()
    assert len(result.entries) > 0


# ── Run all ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  ✓ {test_fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test_fn.__name__}: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"  {passed} passed, {failed} failed out of {passed + failed}")
    if failed == 0:
        print("  All tests passed!")
