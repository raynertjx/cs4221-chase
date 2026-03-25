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

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  ✓ {test_fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test_fn.__name__}: {e}")
            failed += 1
    print(f"\n  {passed} passed, {failed} failed out of {passed + failed}")