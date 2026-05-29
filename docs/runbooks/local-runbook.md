# Local Runbook

Status: Architecture Phase
Implementation: Not Started

This runbook will describe how to bring the platform up locally, send a request,
and inspect its behavior. The procedures below are placeholders for the Serving
Phase and do not work yet, because no runtime code exists.

This document is included now to fix the shape of the operational story and to
list the questions a runbook must answer before the system is considered
operable.

## Intended scope (when implemented)

- Start the platform locally with a mock or CPU inference backend so a GPU is not
  required for development.
- Send a streaming and a non-streaming chat completion request.
- Observe queue depth, admission decisions, and latency in the metrics stack.
- Trigger and observe a rejection by exceeding the configured admission limit.
- Inspect a request end to end in the operator console.

## Procedures to be filled in

- Prerequisites: required tools and versions.
- Bring-up: commands to start each service or the full stack.
- Smoke test: a single request and its expected response.
- Load and rejection: how to drive enough load to see admission control reject.
- Teardown: how to stop the stack cleanly.
- Common failures: symptoms and first debugging steps.

## Current status

Nothing in this runbook is executable yet. It will be filled in as services are
implemented, and each procedure will be verified before it is documented as
working.
