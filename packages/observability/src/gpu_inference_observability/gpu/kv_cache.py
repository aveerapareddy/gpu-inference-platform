"""KV cache estimation. Owner: gpu_inference_observability.gpu."""

from __future__ import annotations

from dataclasses import dataclass

from gpu_inference_observability.gpu.models import KVCacheMetrics

# Default bytes per active sequence when model-specific metadata is unavailable.
# Assumption: 32-layer model, 4096 hidden, fp16 KV (2 bytes), 512 token average context.
# bytes_per_sequence = 2 * num_layers * hidden_size * avg_seq_len * 2 (K+V)
# Simplified constant for platform estimates; documented in gpu-observability.md.
DEFAULT_BYTES_PER_SEQUENCE = 64 * 1024


@dataclass(frozen=True, slots=True)
class KVCacheInputs:
    active_sequences: int
    max_concurrent_sequences: int
    bytes_per_sequence: int = DEFAULT_BYTES_PER_SEQUENCE
    cache_entries: int | None = None


def estimate_kv_cache_metrics(inputs: KVCacheInputs) -> KVCacheMetrics:
    active = max(0, inputs.active_sequences)
    max_seq = max(1, inputs.max_concurrent_sequences)
    bytes_per_seq = max(1, inputs.bytes_per_sequence)
    entries = inputs.cache_entries if inputs.cache_entries is not None else active
    occupancy = min(1.0, active / max_seq)
    estimated_bytes = active * bytes_per_seq
    return KVCacheMetrics(
        cache_entries=entries,
        active_sequences=active,
        cache_occupancy_ratio=occupancy,
        estimated_kv_bytes=estimated_bytes,
        estimation_method="active_sequences * bytes_per_sequence",
        bytes_per_sequence=bytes_per_seq,
    )
