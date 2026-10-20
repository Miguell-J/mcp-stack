# ADR 0009: Cordis metadata in the existing local monitor

Status: accepted. Date: 2026-10-18.

## Context

Operators need to inspect orchestration runs alongside gateway observations.
Cordis must remain independent of MCP Stack, and the local dashboard must remain
read-only and outside the MCP execution and approval paths. Cordis run-store
inspection can rebuild projections; sharing its raw run directory would grant
the dashboard more access than needed.

## Decision

Cordis explicitly exports one bounded, sanitized, versioned `snapshot.json` with
atomic replacement. Stack optionally mounts only the configured export directory
read-only, validates a bundled copy of the producer's JSON Schema and caches
observations through its existing Starlette lifecycle. It never imports Cordis,
loads the run store, runs a subprocess or accepts browser-supplied source paths.
The existing vanilla JavaScript/CSS interface shows run/task dependencies,
attempts, failure routing, gates, history, observed usage/tool metadata and
immutable evidence registration links. Evidence routes return cached metadata.

## Consequences

No new application framework, runtime dependency, frontend build system or
service is introduced. Gateway/catalog operation does not require Cordis.
Export age and failure are visible, previous valid data remains marked stale,
and unknown measurements remain null. Counts disclose bounded truncation.
LocalOnly checks, CSP, GET-only routes, safe text rendering, regular-file/no-follow
checks, size/schema limits and stable errors apply to the new surface.
The operator owns source selection, export permissions and refresh scheduling.
Artifact contents, prompts, raw outputs, arbitrary event details and commands
remain outside this interface. Registration metadata does not prove artifact
bytes were independently validated. The loopback endpoint still exposes
operational metadata to local users, with no multi-user authentication model.
