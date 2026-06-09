# Load tests

**Status:** Implemented (Session 22)  
**Owner:** benchmarks/load-tests

External load generators for HTTP benchmarks against a running API gateway.

| Tool | Directory | When to use |
|------|-----------|-------------|
| k6 | `k6/` | Scriptable scenarios, CI-friendly headless runs |
| Locust | `locust/` | Python-based load, local debugging |

Both tools require:

- Running gateway at `BASE_URL` (default `http://127.0.0.1:8080`)
- Valid API key if configured (`BENCHMARK_API_KEY`)

Session 22 establishes definitions only. Large-scale runs are not executed in validation.

Subdirectories:

- `k6/` — JavaScript scenario scripts and `run.sh` wrapper
- `locust/` — `locustfile.py` and `run.sh` wrapper
