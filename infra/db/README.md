# infra/db

Status: Not implemented (Architecture Phase)

Holds the database setup for control-plane configuration and registry state
(schema, migrations, local setup). The concrete store is selected at the start of
the Serving Phase, favoring a simple, well-understood database.

See `docs/architecture/storage-design.md`. No setup exists yet.
