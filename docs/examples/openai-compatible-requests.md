# OpenAI-Compatible Requests

Status: Architecture Phase
Implementation: Not Started

This document records the request and response shapes the platform intends to
support. The endpoints do not exist yet. The examples define the contract the
implementation will be held to.

## Endpoint

`POST /v1/chat/completions`

Authentication uses a bearer token in the `Authorization` header, following the
OpenAI convention.

## Non-streaming request

```http
POST /v1/chat/completions
Authorization: Bearer <api-key>
Content-Type: application/json
```

```json
{
  "model": "example-model",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Summarize what an inference scheduler does." }
  ],
  "stream": false,
  "max_tokens": 256
}
```

## Streaming request

Set `stream` to `true`. The response is a sequence of server-sent events, each
carrying an incremental chunk, terminated by a `[DONE]` sentinel.

```json
{
  "model": "example-model",
  "messages": [
    { "role": "user", "content": "Explain admission control in one paragraph." }
  ],
  "stream": true,
  "max_tokens": 256
}
```

## Rejection response (admission limit)

When admission control rejects a request, the platform returns a typed error and
an appropriate HTTP status. The exact body is defined in
`packages/common-schemas` once implemented. Shape intent:

```json
{
  "error": {
    "type": "queue_full",
    "message": "Request rejected: admission queue is full.",
    "retry_after_ms": 250
  }
}
```

## Notes

- Field names follow the OpenAI chat completion convention so existing clients
  work without modification.
- These examples are contracts for the implementation. They are not backed by a
  running endpoint during the Architecture Phase.
