from chase.models import Schema, DependencySet
from chase.decomposition import ProjectionComputer


def test_projection_returns_minimal_cover():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "B -> C", "C -> D"])

    projected = ProjectionComputer(schema, deps).project(["A", "B", "C"])

    assert sorted(str(fd) for fd in projected.fds) == ["A → B", "B → C"]


def test_projection_removes_redundant_supersets():
    schema = Schema(["A", "B", "C", "D"])
    deps = DependencySet.from_strings(["A -> B", "A -> C", "B -> C", "C -> D"])

    projected = ProjectionComputer(schema, deps).project(["A", "B", "C"])

    assert sorted(str(fd) for fd in projected.fds) == ["A → B", "B → C"]
