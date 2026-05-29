# Tradeoffs

Status: Architecture Phase
Implementation: Not Started

This document records the deliberate tradeoffs in the design and the reasoning
behind them. It exists so that choices are not silently revisited. Decisions may
change, but a change should be a conscious amendment to this list.

## Load shedding over unbounded queueing

The system rejects requests when full rather than queueing without limit.
Rejections are explicit and observable. The cost is that clients must handle
retries. The benefit is bounded latency and a system that fails predictably under
overload.

## Disposable scheduling state

Live scheduling state is in memory and is lost on restart. The cost is that a
restart drops queued requests. The benefit is a much simpler scheduler with no
durable-queue machinery. Only configuration and registry state is persisted.

## Centralized scheduler

A single scheduler is the authority for dispatch. The cost is that the scheduler
is a coordination point and a scaling consideration. The benefit is one clear
place for admission, batching, and fairness logic, which keeps behavior
predictable and debuggable.

## Backend behind a narrow adapter

The platform defines a small inference interface instead of binding to one
engine. The cost is that advanced backend features are only available once
exposed through the adapter. The benefit is that the scheduler stays independent
of backend internals and a mock backend can be used for development.

## OpenAI-compatible API

The client surface follows the OpenAI chat completion convention. The cost is
inheriting that API's shape and constraints. The benefit is that existing clients
and tooling work without custom integration.

## Single-cluster scope

The target deployment is one machine or one Kubernetes cluster. The cost is no
multi-region story. The benefit is a focused, demonstrable system without
distributed-systems scope creep.

## Request batching before continuous batching

The first batching implementation is request-level. Continuous batching is
deferred to a later milestone because it depends on backend support. The cost is
lower initial GPU efficiency. The benefit is a working serving path sooner, with
a clear upgrade path.
