# tests/test_models.py
from chase.models import Attribute, Schema, FD, MVD, DependencySet, TableInstance

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

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])