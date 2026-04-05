# The Chase — CS4221 Database Tuning

An interactive Chase Algorithm Toolkit with a **web UI** and Python library.
Covers FDs, MVDs, entailment, lossless decomposition, minimal cover, closure, candidate keys, BCNF & 3NF decomposition, FD discovery from tables, and benchmarking.

---

## Features

| #   | Feature            | Description                                                       |
| --- | ------------------ | ----------------------------------------------------------------- |
| 1   | **Table Check**    | Input a table instance + FDs → see which are satisfied / violated |
| 2   | **Entailment**     | Step-by-step Chase tableau to test if Σ ⊨ X → Y or Σ ⊨ X ↠ Y      |
| 3   | **Lossless Join**  | Chase test for decomposition (FD + MVD support)                   |
| 4   | **Minimal Cover**  | Step-by-step minimal cover computation                            |
| 5   | **Closure**        | Compute X⁺, check superkey status                                 |
| 6   | **Candidate Keys** | Find all candidate keys and prime attributes                      |
| 7   | **Decomposition**  | BCNF and 3NF decomposition with dependency preservation check     |
| 8   | **FD Discovery**   | Discover minimal FDs from a table instance (partition refinement) |
| 9   | **Benchmark**      | Time all operations + ablation (FD-only vs FD+MVD)                |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/raynertjx/cs4221-chase.git
cd cs4221-chase

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the web app
python web/app.py
# Open http://localhost:5000 in your browser

# 4. Run tests
python3 -m pytest -v
```

---

## All Ways to Run

| What           | Command                                                    | Where                 |
| -------------- | ---------------------------------------------------------- | --------------------- |
| **Web app**    | `python web/app.py`                                        | http://localhost:5000 |
| **CLI demo**   | `python examples/demo.py`                                  | Terminal              |
| **Tests**      | `python3 -m pytest -v`                                     | Terminal              |
| **Benchmarks** | `python examples/benchmark_runner.py`                      | Terminal              |
| **Docker**     | `docker build -t chase . && docker run -p 5000:5000 chase` | http://localhost:5000 |
| **Makefile**   | `make web` / `make test` / `make demo` / `make bench`      | Terminal              |

---

## Repo Structure

```
cs4221-chase/
├── chase/                     # Core Python library
│   ├── __init__.py            # Public API (barrel exports)
│   ├── models.py              # Schema, FD, MVD, DependencySet, TableInstance
│   ├── closure.py             # Attribute closure (fixpoint algorithm)
│   ├── minimal_cover.py       # Minimal cover (4-step algorithm)
│   ├── entailment.py          # Generalized Chase engine (FD + MVD entailment)
│   ├── chase.py               # Lossless join test & table validation
│   ├── decomposition.py       # Candidate keys, projection, BCNF & 3NF decomposition
│   ├── discovery.py           # FD discovery (partition refinement)
│   └── benchmark.py           # Performance & ablation runners
├── web/                       # Flask web application
│   ├── app.py                 # API routes (MVD-aware parsing)
│   ├── templates/index.html   # Interactive dark-theme UI
│   └── static/                # CSS / JS assets
├── tests/                     # Comprehensive test suite
│   ├── test_models.py         # Model integrity
│   ├── test_closure.py        # Closure & superkey logic
│   ├── test_minimal_cover.py  # Redundancy removal
│   ├── test_keys.py           # Candidate key finding
│   ├── test_entailment.py     # MVD transitivity / replication
│   ├── test_decomposition.py  # Lossless join (FD + MVD)
│   ├── test_discovery.py      # FD discovery logic
│   └── test_edge_cases.py     # Cycles & empty inputs
├── examples/
│   ├── demo.py                # Full walkthrough of library features
│   └── benchmark_runner.py    # Benchmark script
├── Dockerfile                 # Multi-stage production build
├── docker-compose.yml         # Docker Compose config
├── Makefile                   # Convenience targets
├── requirements.txt           # flask>=3.0, pytest
└── README.md
```

---

## Using as a Python Library

The core library has **zero dependencies** and can be used independently of the web app.

```python
from chase import (
    Schema, FD, MVD, DependencySet,
    ChaseEntailment, ChaseLossless, ClosureComputer,
    MinimalCoverComputer, CandidateKeyFinder,
)

schema = Schema(['A', 'B', 'C', 'D'])
deps = DependencySet.from_strings(['A,B -> C', 'C -> D', 'D -> A'])

# Entailment: does Σ ⊨ A,B → D?
result = ChaseEntailment(schema, deps, FD(['A','B'], ['D'])).run()
print(result.entailed)  # True

# Attribute closure
print(ClosureComputer(schema, deps).compute(['A', 'B']))
# {A, B}⁺ = {A, B, C, D} [superkey]

# Minimal cover
print(MinimalCoverComputer(deps).compute())

# Candidate keys
print(CandidateKeyFinder(schema, deps).compute())
```

---

### Alternative input format

```python
# Tuple-based construction
deps = DependencySet.from_tuples([
    ({'A'}, {'B', 'C'}),
    ({'B', 'C'}, {'A', 'D'}),
])
```

---

## Web UI

The web interface at `http://localhost:5000` provides **9 tabs** — one for each feature listed above. The UI includes:

- **Step-by-step tableau playback** for Chase entailment and lossless join tests, allowing users to observe how symbols are equated or rows are generated at each step.
- **Pre-loaded examples** from standard textbook cases and a University schema for quick exploration.
- **Interactive dark or light-themed interface** designed for exploring database dependency concepts.

---

## Deployment

### Local

```bash
python web/app.py              # runs on port 5000
PORT=8080 python web/app.py    # custom port
```

### Docker

```bash
docker build -t chase-algorithm .
docker run -p 5000:5000 chase-algorithm

# Or with Docker Compose
docker-compose up

# Or with Makefile
make docker
```

### Production (Gunicorn)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web.app:app
```

### Cloud VM (e.g. AWS EC2, GCP, NUS SoC servers)

```bash
git clone https://github.com/raynertjx/cs4221-chase.git && cd cs4221-chase
pip install -r requirements.txt
PORT=80 python web/app.py
```

---

## Testing

```bash
# Run all tests
python3 -m pytest -v

# Run a specific test module
python3 -m pytest tests/test_entailment.py -v

# Using Makefile
make test
```

---

## Requirements

- Python 3.10+
- Flask (for the web app only — the core library has zero dependencies)

---

## License

MIT
