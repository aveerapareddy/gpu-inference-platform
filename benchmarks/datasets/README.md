# Benchmark datasets

**Status:** Implemented (Session 22)  
**Owner:** benchmarks/datasets

Prompt fixtures for workload profiles. Profiles in `benchmarks/runner/profiles.py` reference these keys.

| Key | Approx input tokens | Use |
|-----|---------------------|-----|
| `short` | ~10 words | ShortPromptProfile |
| `medium` | ~80 words | MediumPromptProfile |
| `long` | ~400 words | LongPromptProfile |

Output sizes are set via `max_tokens` on each profile, not stored here.
