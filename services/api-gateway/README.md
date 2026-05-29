# API Gateway

Status: Not implemented (Architecture Phase)

OpenAI-compatible HTTP surface. Validates client requests against shared schemas,
authenticates API keys, handles streaming and cancellation, and forwards work to
the scheduler. Holds no scheduling logic and never calls workers directly.

See `docs/architecture/system-overview.md` and
`docs/workflows/request-serving-workflow.md`. No runtime code exists yet.
