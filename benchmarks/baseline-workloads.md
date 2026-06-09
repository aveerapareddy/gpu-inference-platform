# Baseline reference workloads

**Status:** Implemented (Session 23)  
**Owner:** benchmarks/runner/profiles.py

These workloads are the standard reference set for baseline measurements and future comparison runs.

| Profile | Prompt key | Est. input tokens | Target output tokens | Stream | Rationale |
|---------|------------|-------------------|----------------------|--------|-----------|
| Short Prompt (`short_prompt`) | `short` | ~8 (estimated) | 32 | no | Minimal input volume; reference for platform overhead |
| Medium Prompt (`medium_prompt`) | `medium` | ~58 (estimated) | 128 | no | Typical interactive query length |
| Long Prompt (`long_prompt`) | `long` | ~98 (estimated) | 256 | no | Higher input token volume |
| Streaming Prompt (`streaming`) | `short` | ~8 (estimated) | 64 | yes | Token delivery latency baseline |

## Token estimation

Input token counts use `chars/4` (`benchmarks/runner/tokens.py`). Values are **estimated**, not tokenizer-measured.

Output token counts are **measured** when the backend reports completion or stream metrics. Mock backend sync completions report 0 tokens; mock streaming reports chunk count.

## Prompt fixtures

Text loaded from `benchmarks/datasets/prompts.json`.

## Usage

Single-request baseline scenarios:

- `baseline_single_short`
- `baseline_single_medium`
- `baseline_single_long`
- `baseline_single_streaming`

Low-concurrency scenarios (short prompt, request count equals concurrency):

- `baseline_concurrency_2`
- `baseline_concurrency_4`
- `baseline_concurrency_8`
