# ENG-P11 — AI Agent Task Scheduling Runbook

**Status: PARTIAL / NOT APPROVED FOR AUTONOMOUS PRODUCTION EXECUTION**  
**Canonical components:** FastAPI Agent Task Schedule API, Workflow Engine, Agent Runtime, Supabase Postgres, registered Tool Registry.  
**UI source:** `urbanrealty36-ops/Allpha-Front-End-UI-New/components/AgentGoalsTasksModal.tsx`. The reference contains the Task/Goal visual form and local demo behavior; it does not implement the durable scheduler. Copy its UI hierarchy/classes only. Do not promote demo tasks, last-run times, output summaries or success states to production.

## Intended lifecycle

1. Human Owner selects an owned Agent, active Runtime session, published Skill, registered Tool, instructions/input, task type, schedule (once/daily/weekly), IANA timezone, local time/weekdays, explicit permission scopes, budget and approval requirement.
2. `POST /v1/agent-task-schedules` validates owner/session/Agent/Skill binding, published Skill, Tool registration, approved capability/policy, granted scopes, risk approval and Skill budget. It creates a version-pinned Workflow Definition containing one `agent_task` node and persists the schedule in `agent_task_schedules`.
3. The gated `allpha-agent-task-scheduler` worker claims due schedules via `rpc/claim_due_agent_task_schedules` (`FOR UPDATE SKIP LOCKED` and lease), creates a unique `agent_task_schedule_runs` occurrence, and dispatches a durable Workflow run with a stable occurrence trace/idempotency key.
4. The separately gated Workflow worker claims the `agent_task` node. It rechecks schedule ownership/status, approval, Agent/Skill version, published Skill, capability and current Agent Runtime policy, then creates/executes a durable Agent Runtime task. Runtime uses checkpoint/effect receipts and does not replay unknown side effects automatically.
5. Schedule-run status, runtime/workflow IDs, timestamps, error code and real result summary are persisted. UI reads those values from the API; no client-generated success or guessed next-run value is authoritative.

## API surface currently present

- `POST /v1/agent-task-schedules` — create durable schedule.
- `GET /v1/agent-task-schedules` — list owner schedules.
- `GET /v1/agent-task-schedules/{schedule_id}/runs` — real occurrence history.
- `POST /v1/agent-task-schedules/{schedule_id}/runs/{run_id}/approve` — Human Owner approval.
- `PATCH /v1/agent-task-schedules/{schedule_id}/status` — pause/cancel/resume schedule.
- Worker entry point: `allpha-agent-task-scheduler`, disabled unless `ALLPHA_AGENT_TASK_SCHEDULER_ENABLED=true`.
- Workflow worker entry point: `allpha-workflow-worker`, disabled unless `ALLPHA_WORKFLOW_WORKER_ENABLED=true`.
- Migration: `20261026100000_eng_p11_agent_task_schedules.sql`; source-only until the approved ENG-P37 migration gate.

## Known implementation limits that prevent a full-autonomy claim

- The current Tool Registry has only `text.normalize`; it does not yet provide real canonical domain handlers for `SCHEDULING_POST`, `BROADCAST_INFO`, `KNOWLEDGE_DISPATCH` or `ANALYTICS_REPORT`. The API deliberately rejects these task types rather than simulating a business operation.
- `SKILL_EXECUTION` only works when the selected published Skill, its declared tool, approved runtime policy, input schema and grants genuinely align. A registered deterministic tool is not equivalent to an LLM planner or an arbitrary instruction executor.
- Schedule `instructions` are persisted as schedule metadata but are not currently consumed by the Agent Runtime execution request. A canonical planner contract is still required to turn instructions into a bounded, schema-validated plan; model output must never grant permissions or bypass the approved Tool Registry.
- A scheduled occurrence currently dispatches a Workflow run, but production acceptance still requires verified worker deployment/configuration, migration acceptance, end-to-end durable result propagation and real authenticated evidence. Both worker flags remain off by default.
- The reference `AgentGoalsTasksModal` is not mounted on the active Agent route. Keep its source DOM/classes/style intact; wire it only when typed API adapters are ready. Goals remain a separate domain contract, not a schedule.

## Gate before enabling a production worker

- [ ] ENG-P37 approved isolated migration run confirms the schedule tables, constraints, RLS/revokes, indexes and claim RPC.
- [ ] API tests cover owner isolation, invalid schedule/timezone, explicit grants, risk/approval, version changes, idempotency, retries, unknown outcomes and status reconciliation.
- [ ] Approved worker environment has server-side Supabase configuration, bounded poll/batch/lease settings, alerting and a rollback/disable procedure.
- [ ] Only real registered domain tools may execute; unknown/unimplemented task types remain blocked.
- [ ] Workflow/Runtime output is durably linked to the occurrence and the UI renders the backend state without fabricated summaries.
- [ ] Authenticated visual parity evidence is captured separately from unauthenticated fallback screenshots.

Do not turn on either worker flag or apply the migration to production as part of UI-copy work. Do not claim autonomous task completion until the above gates are verified.
