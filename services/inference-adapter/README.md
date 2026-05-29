# Inference Adapter

Status: Not implemented (Architecture Phase)

Translates platform-internal requests into calls to a concrete inference backend
and normalizes responses. Defines a narrow interface: submit a batch, stream
tokens, cancel. A mock or CPU backend implements this interface for development
without a GPU.

See `docs/architecture/runtime-model.md`. No runtime code exists yet.
