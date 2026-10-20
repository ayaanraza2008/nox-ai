# NOX AI — Background task resilience

## What this upgrade changes

- Every background task provider call has a hard timeout. Configure `NOX_TASK_PROCESSOR_TIMEOUT_SECONDS` from 5 to 180 seconds; default is 90 seconds. Invalid values fail fast during startup rather than silently disabling the bound.
- A timed-out provider call is retried once, then the task is marked failed with an explicit timeout message. The single worker can then continue to later queued tasks.
- Pause/resume recovery is safer around queue dispatch. A paused task remains paused across process recreation; a resumed task is enqueued even if its previous runner is exiting.
- Task API reads and actions remain scoped to the server-issued browser/account owner: `GET /api/tasks`, `GET /api/tasks/{id}`, `POST /api/tasks/{id}/pause`, `POST /api/tasks/{id}/resume`, and `POST /api/tasks/{id}/cancel`.

## Storage and runtime boundaries

- For durable task records across hosted restarts, configure a reachable PostgreSQL URL through `DATABASE_URL` or `SUPABASE_DB_URL`. SQLite at `/tmp/nox_tasks.sqlite3` is a fallback and may be ephemeral on hosting platforms.
- A provider timeout bounds the awaited processor call; it does not guarantee an upstream provider stopped processing immediately.
- Pause is cooperative. It prevents a task from advancing at pause checkpoints, but cannot undo a request already accepted by an external provider. Cancel stops local task execution and does not reverse any external side effect.
- The hosted worker performs supported research/reasoning tasks only. It cannot directly control the user's computer; device operations require the authenticated local companion and its own permission checks.
- The NOX task queue is not a general-purpose workflow scheduler. It does not run arbitrary shell commands, purchase items, submit forms, or send messages.

## Verification

The CI regression test `backend/tests/test_task_resilience.py` checks that a hung processor times out without permanently blocking the next queued task, and that paused tasks remain paused and owner-isolated after manager recreation.
