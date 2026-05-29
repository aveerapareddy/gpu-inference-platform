# Control Plane

Status: Not implemented (Architecture Phase)

Owns the model registry, routing policy, worker pool membership, and runtime
configuration. Answers which model and which worker pool serve a request. Sole
writer of configuration and registry state.

See `docs/architecture/system-overview.md` and
`docs/architecture/storage-design.md`. No runtime code exists yet.
