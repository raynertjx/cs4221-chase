import pytest
from chase.models import Schema, DependencySet, FD, MVD
from chase.entailment import ChaseEntailment
from chase.minimal_cover import MinimalCoverComputer

def test_chase_cycle_dependency():
    """Test if the Chase handles cycles like A->B, B->C, C->A."""
    schema = Schema(["A", "B", "C"])
    deps = DependencySet.from_strings(["A -> B", "B -> C", "C -> A"])
    # Manual instantiation: FD(lhs_list, rhs_list)
    target = FD(["A"], ["C"])
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed

def test_minimal_cover_cycle_preservation():
    """Ensure minimal cover doesn't accidentally delete an entire cycle."""
    deps = DependencySet.from_strings(["A -> B", "B -> A"])
    result = MinimalCoverComputer(deps).compute()
    assert len(result.result.fds) == 2

def test_chase_no_relevant_dependencies():
    """Test entailment when the dependency set is totally unrelated."""
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B"])
    target = FD(["C"], ["D"])
    result = ChaseEntailment(schema, deps, target).run()
    assert not result.entailed

def test_mvd_complementation_rule():
    """
    In a schema {A, B, C}, A ->> B logically implies A ->> C.
    """
    schema = Schema(["A", "B", "C"])
    deps = DependencySet.from_strings(["A ->> B"])
    target = MVD(["A"], ["C"])
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed