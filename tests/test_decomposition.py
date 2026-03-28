from unittest import result
import pytest
from chase.models import Schema, DependencySet
from chase.decomposition import CandidateKeyFinder, BCNFDecomposer, ThreeNFDecomposer
from chase.chase import ChaseLossless

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

def test_bcnf_decomposition():
    schema = Schema(["A", "B", "C", "D", "E", "F"])
    deps = DependencySet.from_strings([
        "C -> E",
        "E -> C",
        "D -> C, E",
        "B, C -> A, D",
        "B, E -> A, D"
    ])

    decomposer = BCNFDecomposer(schema, deps)
    result = decomposer.decompose()

    expected_fragment_sets = [
        {"C", "E"},
        {"C", "D"},
        {"A", "B", "D"},
        {"B", "D", "F"}
    ]
    
    actual_fragment_sets = [set(s.names) for s in result.fragments]

    for expected in expected_fragment_sets:
        assert expected in actual_fragment_sets

    assert not result.dependency_preserved

def test_3nf_decomposition():
    schema = Schema(["A", "B", "C", "D", "E", "F"])
    deps = DependencySet.from_strings([
        "C -> E",
        "E -> C",
        "D -> C, E",
        "B, C -> A, D",
        "B, E -> A, D"
    ])

    decomposer = ThreeNFDecomposer(schema, deps)
    result = decomposer.decompose()

    actual_fragments = [set(names) for names in result.fragment_names]

    assert {"C", "E"} in actual_fragments
    assert {"B", "C", "F"} in actual_fragments
    assert (
        {"A", "B", "C", "D"} in actual_fragments
        or {"A", "B", "D", "E"} in actual_fragments
    )

    assert result.key_added
    assert result.key_fragment is not None
    assert set(result.key_fragment.names) == {"B", "C", "F"}


