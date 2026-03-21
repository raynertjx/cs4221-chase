"""
chase – The Chase Algorithm Toolkit
====================================
CS4221 Database Tuning · NUS

A comprehensive OOP implementation of the Chase algorithm
for functional dependencies, multivalued dependencies,
entailment testing, lossless decomposition, minimal cover,
candidate keys, and FD discovery from table instances.

Quick Start
-----------
    from chase import Schema, FD, MVD, DependencySet
    from chase import ChaseEntailment, ChaseLossless, ChaseTableValidator
    from chase import ClosureComputer, MinimalCoverComputer, CandidateKeyFinder
    from chase import FDDiscoverer, BenchmarkRunner

Example
-------
    schema = Schema(['A', 'B', 'C', 'D'])
    deps = DependencySet.from_strings(['A,B -> C', 'C -> D', 'D -> A'])
    
    # Entailment
    target = FD(['A', 'B'], ['D'])
    result = ChaseEntailment(schema, deps, target).run()
    print(result)   # A,B → D IS entailed
    
    # Minimal cover
    mc = MinimalCoverComputer(deps).compute()
    print(mc)
    
    # Candidate keys
    keys = CandidateKeyFinder(schema, deps).compute()
    print(keys)
"""

__version__ = "2.0.0"

# Models
from .models import (
    Attribute,
    Schema,
    FD,
    MVD,
    Dependency,
    DependencySet,
    TableInstance,
    TableauCell,
    TableauRow,
    Tableau,
)

# Core algorithms
from .algorithms import (
    ClosureComputer,
    ClosureResult,
    MinimalCoverComputer,
    MinimalCoverResult,
    CandidateKeyFinder,
    CandidateKeyResult,
    ProjectionComputer,
)

# Chase implementations
from .chase import (
    ChaseEntailment,
    ChaseEntailmentResult,
    ChaseLossless,
    ChaseLosslessResult,
    ChaseTableValidator,
    TableValidationResult,
    FDValidation,
)

# Discovery
from .discovery import (
    FDDiscoverer,
    DiscoveryResult,
)

# Benchmarking
from .benchmark import (
    BenchmarkRunner,
    BenchmarkResult,
    FDGenerator,
    TimingEntry,
)

__all__ = [
    # Models
    "Attribute", "Schema", "FD", "MVD", "Dependency", "DependencySet",
    "TableInstance", "TableauCell", "TableauRow", "Tableau",
    # Algorithms
    "ClosureComputer", "ClosureResult",
    "MinimalCoverComputer", "MinimalCoverResult",
    "CandidateKeyFinder", "CandidateKeyResult",
    "ProjectionComputer",
    # Chase
    "ChaseEntailment", "ChaseEntailmentResult",
    "ChaseLossless", "ChaseLosslessResult",
    "ChaseTableValidator", "TableValidationResult", "FDValidation",
    # Discovery
    "FDDiscoverer", "DiscoveryResult",
    # Benchmark
    "BenchmarkRunner", "BenchmarkResult", "FDGenerator", "TimingEntry",
]
