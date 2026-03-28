# The Chase — CS4221 Database Tuning

Interactive Chase Algorithm Toolkit with **web UI** and Python library.
Covers FDs, MVDs, entailment, lossless decomposition, minimal cover,
candidate keys, FD discovery from tables, and benchmarking.

## Quick Start (Web App)

```bash
# 1. Clone
git clone https://github.com/<your-team>/chase-algorithm.git
cd chase-algorithm

# 2. Install dependencies 
pip install -r requirements.txt

# 3. Run
python web/app.py

# 4. Run tests
python3 -m pytest -v
python3 -m pytest tests/test_entailment.py -v
pytest tests/

# 5. Spin up docker
docker rm -f $(docker ps -aq)
docker build -t my-app .
docker run -d --name chase-v2 -p 8080:8080 my-app
# view at:
http://localhost:8080
# check for errors:
docker logs chase-v2

# 6. Using makefile
make test — Validates your logic.
make web — Starts the UI for development.
make docker — Handles the full build/run cycle.
make clean — Wipes the junk 

```



Then open **http://localhost:5000** in your browser.

That's it — the full interactive tool runs locally with a VisualGo-style
step-by-step tableau viewer, all 8 features, and dark theme UI.

## All Ways to Run

| What | Command | Where |
|------|---------|-------|
| **Web app** | `python web/app.py` | http://localhost:5000 |
| **CLI demo** | `python examples/demo.py` | Terminal |
| **Tests** | `python tests/test_chase.py` | Terminal |
| **Benchmarks** | `python examples/benchmark_runner.py` | Terminal |
| **Docker** | `docker build -t chase . && docker run -p 5000:5000 chase` | http://localhost:5000 |
| **Makefile** | `make web` / `make test` / `make demo` / `make bench` | Terminal |

## Repo Structure

```
cs4221-chase/
├── chase/                     # Core Python library
│   ├── __init__.py            # Public API (Barrel exports)
│   ├── models.py              # Schema, FD, MVD, DependencySet, TableInstance
│   ├── closure.py             # Attribute Closure algorithm
│   ├── minimal_cover.py       # Minimal Cover (3-step algorithm)
│   ├── keys.py                # Candidate Key finding & Prime attributes
│   ├── entailment.py          # Generalized Chase Engine (FD + MVD Support)
│   ├── decomposition.py       # Lossless Join test & Projection
│   ├── discovery.py           # FD Discoverer (Partition Refinement)
│   ├── chase.py               # Legacy support & Table Validation
│   └── benchmark.py           # Performance & Ablation runners
├── web/                       # Flask web application
│   ├── app.py                 # API routes (MVD-aware parsing)
│   ├── templates/index.html   # VisualGo-style dark theme UI
│   └── static/                # CSS/JS assets
├── tests/                     # Comprehensive Unit Test Suite
│   ├── test_models.py         # Model integrity
│   ├── test_closure.py        # Closure & superkey logic
│   ├── test_minimal_cover.py  # Redundancy removal
│   ├── test_keys.py           # Candidate key finding
│   ├── test_entailment.py     # MVD transitivity/replication
│   ├── test_decomposition.py  # Lossless join (FD + MVD)
│   ├── test_discovery.py      # FD discovery logic
│   └── test_edge_cases.py     # Cycles & empty inputs
├── examples/
│   └── demo.py                # Full walkthrough of library features
├── Dockerfile                 # Multi-stage production build
├── requirements.txt           # flask>=3.0, pytest
└── README.md
```

## Web UI Features

The web interface at `http://localhost:5000` provides 8 tabs:

- **Table Check** — input a table instance + FDs, see which are satisfied/violated
- **Entailment** — step-by-step Chase tableau to test if Σ ⊨ X→Y
- **Lossless Join** — Chase test for decomposition (FD + MVD support)
- **Min Cover** — step-by-step minimal cover computation
- **Closure** — compute X⁺, check superkey status
- **Keys** — find all candidate keys and prime attributes
- **Discover** — discover minimal FDs from a table instance
- **Benchmark** — time all operations + ablation (FD-only vs FD+MVD)

Pre-loaded examples include standard textbook cases and a University schema.

## Using as a Python Library

```python
from chase import (
    Schema, FD, MVD, DependencySet,
    ChaseEntailment, ChaseLossless, ClosureComputer,
    MinimalCoverComputer, CandidateKeyFinder,
)

schema = Schema(['A', 'B', 'C', 'D'])
deps = DependencySet.from_strings(['A,B -> C', 'C -> D', 'D -> A'])

# Entailment
result = ChaseEntailment(schema, deps, FD(['A','B'], ['D'])).run()
print(result.entailed)  # True

# Closure
print(ClosureComputer(schema, deps).compute(['A', 'B']))
# {A, B}⁺ = {A, B, C, D} [superkey]

# Minimal cover
print(MinimalCoverComputer(deps).compute())

# Candidate keys
print(CandidateKeyFinder(schema, deps).compute())
```

### pratik2358/fucntional_dep compatibility

```python
# Their format works directly:
deps = DependencySet.from_tuples([
    ({'A'}, {'B', 'C'}),
    ({'B', 'C'}, {'A', 'D'}),
])
```

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
```

### Cloud VM (e.g. AWS EC2, GCP, NUS SoC servers)
```bash
# On the VM:
git clone <repo-url> && cd chase-algorithm
pip install -r requirements.txt
PORT=80 python web/app.py      # or use gunicorn for production
```

### Gunicorn (production)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web.app:app
```

## Requirements

- Python 3.10+
- Flask (for web app only — core library has zero dependencies)

## License

MIT
