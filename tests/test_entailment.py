# tests/test_entailment.py
from chase.models import Schema, DependencySet, FD, MVD
from chase.entailment import ChaseEntailment

def test_entailment_positive():
    schema = Schema(["A", "B", "C"])
    # A->B, B->C should entail A->C
    deps = DependencySet.from_strings(["A -> B", "B -> C"])
    target = FD(["A"], ["C"])
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed

def test_entailment_negative():
    schema = Schema(["A", "B", "C"])
    # A->B does NOT entail B->A
    deps = DependencySet.from_strings(["A -> B"])
    target = FD(["B"], ["A"])
    result = ChaseEntailment(schema, deps, target).run()
    assert not result.entailed

def test_entailment_mvd():
    schema = Schema(["A", "B", "C"])
    # A->>B entails A->>C in a 3-attribute schema
    deps = DependencySet.from_strings(["A ->> B"])
    target = MVD(["A"], ["C"])
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed

def test_entailment_mvd_transitive():
    schema = Schema(["A", "B", "C", "D"])
    # A ->> B and B ->> C
    deps = DependencySet.from_strings(["A ->> B", "B ->> C"])
    target = MVD(["A"], ["C"]) 
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed

def test_fd_implies_mvd():
    schema = Schema(["A", "B", "C"])
    deps = DependencySet.from_strings(["A -> B"])
    target = MVD(["A"], ["B"])
    result = ChaseEntailment(schema, deps, target).run()
    assert result.entailed