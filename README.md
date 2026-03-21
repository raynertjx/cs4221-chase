# The Chase — CS4221 Database Tuning

Interactive Chase Algorithm Toolkit with **web UI** and Python library.
Covers FDs, MVDs, entailment, lossless decomposition, minimal cover,
candidate keys, FD discovery from tables, and benchmarking.

## Quick Start (Web App)

```bash
# 1. Clone
git clone https://github.com/<your-team>/chase-algorithm.git
cd chase-algorithm

# 2. Install Flask
pip install -r requirements.txt

# 3. Run
python web/app.py
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
chase-algorithm/
├── chase/                     # Core Python library
│   ├── __init__.py            # Public API
│   ├── models.py              # Schema, FD, MVD, DependencySet, TableInstance, Tableau
│   ├── algorithms.py          # ClosureComputer, MinimalCoverComputer, CandidateKeyFinder
│   ├── chase.py               # ChaseEntailment, ChaseLossless, ChaseTableValidator
│   ├── discovery.py           # FDDiscoverer (partition refinement)
│   └── benchmark.py           # BenchmarkRunner, FDGenerator
├── web/                       # Flask web application
│   ├── app.py                 # API routes + server
│   ├── templates/index.html   # Full frontend (single HTML file)
│   └── static/                # (optional assets)
├── tests/
│   └── test_chase.py          # 23 unit tests
├── examples/
│   ├── demo.py                # Full CLI walkthrough
│   └── benchmark_runner.py    # Standalone benchmark script
├── requirements.txt           # flask>=3.0
├── Dockerfile                 # For cloud/VM deployment
├── Makefile                   # make web / make test / etc.
├── pyproject.toml
├── .gitignore
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
