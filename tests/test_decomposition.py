# tests/test_decomposition.py
from chase.models import Schema, DependencySet
from chase.decomposition import CandidateKeyFinder, ChaseLossless

def test_candidate_keys_basic():
    schema = Schema(["A", "B", "C"])
    deps = DependencySet.from_strings(["A -> B", "B -> C"])
    finder = CandidateKeyFinder(schema, deps)
    keys = finder.compute().keys # Should return [['A']]
    assert len(keys) == 1
    assert "A" in [a.name for a in keys[0]]

def test_lossless_positive():
    schema = Schema(["A", "B", "C"])
    deps = DependencySet.from_strings(["A -> B"])
    # Decomposing into (A,B) and (A,C) is lossless because A is a key for (A,B)
    schemas = [Schema(["A", "B"]), Schema(["A", "C"])]
    result = ChaseLossless(schema, deps, schemas).run()
    assert result.lossless

def test_lossless_negative():
    schema = Schema(["A", "B", "C"])
    deps = DependencySet.from_strings(["B -> C"])
    # (A,B) and (B,C) is lossless? Yes (B is key). 
    # Let's try (A,C) and (B,C) -> Lossy because no common attr is a key
    schemas = [Schema(["A", "C"]), Schema(["B", "C"])]
    result = ChaseLossless(schema, deps, schemas).run()
    assert not result.lossless