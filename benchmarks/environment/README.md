# Benchmark environment

**Status:** Implemented (Session 23)  
**Owner:** benchmarks/runner/environment.py

Every `BenchmarkRun` includes a `BenchmarkEnvironment` record captured at run start.

## Captured fields

| Field | Source |
|-------|--------|
| GPU model | `gpu_inference_observability.gpu.probes` |
| GPU memory total | NVML or fallback probe |
| GPU source | `nvml`, `fallback_unavailable`, or `simulated` |
| CPU model | `platform.processor()` |
| RAM | `psutil.virtual_memory().total` when installed |
| OS | `platform.system()` + release |
| Platform string | `platform.platform()` |
| Python version | `sys.version` |
| vLLM version | `vllm.__version__` when package installed |
| Model name | scenario/run configuration (`demo` for embedded validation) |
| Model size | `BENCHMARK_MODEL_SIZE` env var when set |
| Backend ID | runner configuration (`mock` for embedded validation) |
| Hostname | `socket.gethostname()` |

## Failure behavior

- Missing GPU: fields remain null; `gpu_source=fallback_unavailable` or `unavailable`
- Missing psutil: `ram_bytes` is null
- Missing vLLM: `vllm_version` is null
- Runs without environment metadata are invalid for baseline comparison

## Operator overrides

Set before running baseline suite:

```bash
export BENCHMARK_MODEL_SIZE="7B"
```

## Persistence

Environment is stored in:

- `BenchmarkRun.environment` (JSON field)
- Duplicated in `BenchmarkRun.hardware` and `BenchmarkRun.model` for Session 22 compatibility
