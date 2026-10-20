"""Synthetic sanitized metadata shared by observer and isolated browser checks."""

from datetime import UTC, datetime


def snapshot():
    at = datetime.now(UTC).isoformat()
    ref = "artifacts/registered-reference"
    run = {
        "run_id": "example-run",
        "state": "execution",
        "status": "active",
        "plan_revision": 2,
        "work_revision": 3,
        "profile": "software",
        "available": True,
        "error": None,
        "failures": [
            {
                "id": "failure-1",
                "task_id": "implement",
                "code": "TEST_FAILED",
                "category": "local_implementation",
                "route": "execution",
                "retry_authorized": False,
            }
        ],
        "tasks": [
            {
                "id": "implement",
                "owner_role": "worker",
                "dependencies": [],
                "status": "completed",
                "write_scope": ["src/example.py"],
            },
            {
                "id": "validate",
                "owner_role": "tester",
                "dependencies": ["implement"],
                "status": "pending",
                "write_scope": [],
            },
        ],
        "attempts": [
            {
                "id": "attempt-1",
                "task_id": "implement",
                "provider": "codex",
                "status": "succeeded",
                "plan_revision": 2,
                "work_revision": 3,
                "started_at": at,
                "ended_at": at,
                "duration_ms": 125.5,
            }
        ],
        "gates": [
            {
                "name": "plan_audit",
                "status": "passed",
                "current": True,
                "actor_id": "independent-reviewer",
                "actor_role": "auditor",
                "plan_revision": 2,
                "work_revision": None,
                "evidence": [ref],
            }
        ],
        "history": [
            {
                "sequence": 1,
                "at": at,
                "type": "transition",
                "actor_id": "operator",
                "actor_role": "orchestrator",
                "evidence": [ref],
            }
        ],
        "tool_calls": [
            {
                "attempt_id": "attempt-1",
                "task_id": "implement",
                "capability": "catalog.read",
                "outcome": "success",
                "duration_ms": 12,
                "plan_revision": 2,
                "work_revision": 3,
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 25, "cost_usd": None, "duration_ms": 125.5},
        "evidence": [
            {
                "key": "a" * 64,
                "ref": ref,
                "kind": "validation",
                "sha256": "b" * 64,
                "bytes": 42,
                "available": False,
                "verification": "registration_only",
            }
        ],
        "truncated": False,
        "truncated_counts": dict.fromkeys(
            ["tasks", "attempts", "gates", "history", "evidence", "tool_calls", "failures"], 0
        ),
    }
    return {
        "schema_version": "1",
        "generated_at": at,
        "total_runs": 1,
        "exported_runs": 1,
        "truncated": False,
        "runs": [run],
    }
