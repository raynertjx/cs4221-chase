"""
chase – The Chase Algorithm Toolkit
====================================
CS4221 Database Tuning · NUS

A comprehensive OOP implementation of the Chase algorithm
for functional dependencies, multivalued dependencies,
entailment testing, lossless decomposition, minimal cover,
candidate keys, and FD discovery from table instances.
"""

__version__ = "2.0.0"

# 1. Models (Branch 1)
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

# 2. Core Engine (Branch 1)
from .closure import (
    ClosureComputer,
    ClosureResult,
)

# 3. Entailment (Branch 2)
from .entailment import (
    ChaseEntailment,
    ChaseEntailmentResult,
)

# 4. Decomposition (Branch 3)
from .decomposition import (
    CandidateKeyFinder,
    CandidateKeyResult,
    ProjectionComputer,
    BCNFDecomposer,
    BCNFDecompositionResult,
    ThreeNFDecomposer,
    ThreeNFDecompositionResult,
)

# 5. Minimal Cover (Branch 4)
from .minimal_cover import (
    MinimalCoverComputer,
    MinimalCoverResult,
)

# 6. Discovery & Validation
from .chase import (
    ChaseTableValidator,
)

from .discovery import (
    FDDiscoverer,
    DiscoveryResult,
)

from .benchmark import (
    BenchmarkRunner,
    BenchmarkResult,
    FDGenerator,
    TimingEntry,
)

# Note: If you moved ChaseTableValidator out of the old chase.py, 
# make sure to import it from wherever you placed it (e.g., from .validation import ChaseTableValidator)
# For now, I've left it out of the __all__ list to prevent import crashes.

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
    "BCNFDecomposer", "BCNFDecompositionResult",
    "ThreeNFDecomposer", "ThreeNFDecompositionResult",
    
    # Discovery
    "FDDiscoverer", "DiscoveryResult",
    "ChaseTableValidator",
    
    # Benchmark
    "BenchmarkRunner", "BenchmarkResult", "FDGenerator", "TimingEntry",
]
