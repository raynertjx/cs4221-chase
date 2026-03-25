# tests/test_minimal_cover.py
from chase.models import DependencySet
from chase.minimal_cover import MinimalCoverComputer

def test_minimal_cover_removes_redundant():
    # A->B, B->C, A->C (A->C is redundant)
    deps = DependencySet.from_strings(["A -> B", "B -> C", "A -> C"])
    mc_res = MinimalCoverComputer(deps).compute()
    assert len(mc_res.result.fds) == 2

def test_minimal_cover_merges_lhs():
    # A->B, A->C should become A->B,C
    deps = DependencySet.from_strings(["A -> B", "A -> C"])
    mc_res = MinimalCoverComputer(deps).compute()
    assert len(mc_res.result.fds) == 1
    rhs_names = mc_res.result.fds[0].rhs_names
    assert "B" in rhs_names
    assert "C" in rhs_names

def test_minimal_cover_complex_extraneous():
    # In {A->B, B->C, AC->D}, A is extraneous in AC->D 
    # because A->B and BC->D (implied) makes A redundant for D.
    deps = DependencySet.from_strings(["A -> B", "B -> C", "A, C -> D"])
    result = MinimalCoverComputer(deps).compute()
    # AC -> D should have become C -> D or A -> D depending on the closure
    # Check that no FD has 2 attributes on the LHS
    for fd in result.result.fds:
        assert len(fd.lhs) == 1