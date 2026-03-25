# tests/test_closure.py
from chase.models import Schema, DependencySet
from chase.closure import ClosureComputer

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

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])