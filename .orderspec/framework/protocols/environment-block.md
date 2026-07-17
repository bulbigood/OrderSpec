---
orderspec:
  artifact: protocol
  authority: framework
---

# Environment Block Protocol

## Purpose

This protocol handles a task that cannot run because a runtime prerequisite is
unavailable: a database, service, port, credential, emulator, queue, or other
external capability.

The coordinator owns environment recovery. A worker MUST NOT start, stop,
restart, install, reset, migrate, or otherwise mutate an environment. It MUST
return `BLOCKED` with the observed command, error, and missing prerequisite.

## Planning requirement

`/order.plan` MUST identify every material runtime prerequisite in the
`Environment Readiness` section of `plan.md`. Each row MUST contain:

- prerequisite and operational scope;
- an exact read-only check and its expected result;
- repository evidence or an explicit unresolved marker;
- one or more recovery options, including risk and required side effect;
- the safe fallback if recovery is refused or unavailable.

If a prerequisite cannot be verified or no safe fallback exists, `/order.plan`
MUST stop with `PLAN_BLOCKED: runtime prerequisite unverified` rather than
deferring the discovery to implementation.

`/order.tasks` MUST preserve the plan's readiness checks and recovery boundary.
It may add a task for a repository change such as a compose file, test fixture,
or configuration, but it MUST NOT turn an operator action into an implicit
implementation task. Readiness-only checks belong in phase verification or the
implementation preflight.

## Implementation behavior

Before dispatching a task that depends on a declared prerequisite, `/order.code`
MUST use the plan's readiness check when project governance permits it. If the
check fails, the coordinator MUST:

1. stop the current task before writing code or marking it complete;
2. report the shortest decisive error and the affected prerequisite;
3. propose a bounded solution from the plan, repository evidence, or a clearly
   labeled low-risk inference;
4. state the exact command or action, side effect, scope, and fallback;
5. ask the user for approval before any mutating recovery action;
6. execute only the action the user approved, then rerun the readiness check;
7. resume the same task only after the check passes.

The coordinator MUST NOT silently start or stop services, install packages,
change credentials, reset data, run migrations, use network access, or alter
production/shared environments. User approval is required for each exact
mutating action. Approval for one action does not authorize a different action.

If the user refuses, requests the default continuation, or no approved action
is available, use the plan's safe fallback. If the fallback cannot satisfy the
task, leave it unchecked and stop with `CODE_BLOCKED: environment prerequisite`.
Do not invent a code workaround that changes the contract or plan.

If the required recovery changes architecture, deployment topology, data
semantics, security, or the feature contract, stop and route the decision to
`/order.spec`, `/order.plan`, or `/order.bootstrap` as appropriate. User
approval permits an operation; it does not silently amend an artifact.

## Permission boundary

Read-only diagnosis is not permission to mutate the environment. Constitution
capabilities, the plan's declared commands, and current-chat approval all must
permit a mutating action. Capability silence remains denial.

