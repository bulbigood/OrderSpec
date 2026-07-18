#!/usr/bin/env python3
"""Static regression checks for /order.code orchestration wiring."""

import json
from pathlib import Path


FRAMEWORK = Path(__file__).resolve().parents[2]
ORDERSPEC = FRAMEWORK.parent


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


manifest = json.loads((FRAMEWORK / "command-context.json").read_text(encoding="utf-8"))
resources = manifest["resources"]
code_required = manifest["commands"]["order.code"]["required"]

expect("protocol.sub_agent_execution" in resources, "sub-agent protocol is a manifest resource")
expect("protocol.worker_execution" in resources, "canonical worker protocol is a manifest resource")
expect("schema.worker_envelope" in resources, "worker envelope schema is a manifest resource")
expect(
    any(item.get("ref") == "protocol.sub_agent_execution" for item in code_required),
    "order.code requires sub-agent protocol",
)
expect(
    not any(item.get("ref") == "schema.task_context" for item in code_required),
    "order.code leaves task-context validation to the deterministic workflow",
)
expect(
    manifest["commands"]["order.code"]["feature_context"] == {
        "mode": "if_active",
        "artifacts": ["tasks", "plan"],
    },
    "order.code preloads active tasks before plan without hiding lifecycle errors",
)
expect(
    resources["protocol.sub_agent_execution"]["usage"] == "apply"
    and resources["protocol.sub_agent_execution"]["authority"] == "framework",
    "sub-agent protocol has framework apply authority",
)

code_prompt = (FRAMEWORK / "prompts" / "order.code.md").read_text(encoding="utf-8")
normalized_code_prompt = " ".join(code_prompt.split())
expect("LOCAL_PHASE" in code_prompt and "LOCAL_ALL" in code_prompt, "order.code documents local fallback modes")
expect(
    "`--local` / `--no-subagents`" in code_prompt
    and "User prohibition of delegation" in code_prompt,
    "order.code gives explicit user local execution priority over dispatch capability",
)
expect(
    "natural-language single-agent constraint" in normalized_code_prompt
    and "do not inspect, configure, dispatch, or wait for a worker" in normalized_code_prompt,
    "order.code maps a single-agent-session constraint to local execution",
)
expect("task_progress.py mark" in code_prompt, "order.code delegates marker writes to deterministic script")
expect(
    "task_progress.py reconcile" in code_prompt and "ALREADY_COMPLETE" in code_prompt,
    "order.code reconciles previously completed unchecked work from evidence",
)
expect(
    "RESET_PREVIEW" in code_prompt and "### Reset" in code_prompt,
    "order.code reset uses a bounded work-order baseline",
)
expect(
    "workflow_feedback.py create" in code_prompt and "Before every upstream route" in code_prompt,
    "order.code persists every upstream route",
)
expect(
    code_prompt.index("attempt-finish") < code_prompt.index("Before every upstream route")
    and "Never create feedback input or report files\nduring the attempt snapshot" in code_prompt,
    "order.code closes task attempts before writing feedback state",
)
expect(
    "code_workflow.py finish" in normalized_code_prompt
    and "return to Step 4" in normalized_code_prompt,
    "order.code deterministically rejects voluntary partial completion",
)
expect(
    "Task count, elapsed work, context size, token/tool budget" in normalized_code_prompt,
    "order.code forbids workload-based LOCAL_ALL chunking",
)
expect(
    "PHASE_COMPLETE" in code_prompt and "HALTED" in code_prompt,
    "order.code distinguishes phase completion from evidenced halt",
)
expect(
    "rejected result is terminal" in code_prompt
    and "Never alter `changed_files`" in code_prompt,
    "order.code forbids marker-result laundering and retries",
)
expect(
    "plan Evidence Sequencing" in code_prompt
    and "never manufacture a red state" in code_prompt,
    "order.code enforces the plan-selected evidence result",
)
expect("`VERIFY:` and `GATE:`" in code_prompt, "order.code defines read-only command gates")
expect("Phase verification must pass" in code_prompt, "order.code enforces phase verification")
expect("contract_context" in code_prompt, "order.code consumes resolved task contract context")
expect(
    "Do not open full `spec.md`" in normalized_code_prompt,
    "order.code forbids bypassing resolved spec excerpts",
)
expect(
    "Applied `[NEW]` and `[DEL]` transitions" in code_prompt
    and "Never run plan-authoring current-state checks" in code_prompt,
    "order.code preserves plan baseline during resume",
)
expect(
    "task envelope omits it: `/order.tasks`" in code_prompt
    and "physical mapping is absent or wrong: `/order.plan`" in code_prompt,
    "order.code routes task and plan defects separately",
)
expect("code_workflow.py preflight" in code_prompt, "order.code delegates mechanical preflight")
expect(
    "attempt-begin" in code_prompt and "attempt-finish" in code_prompt
    and "worker_envelopes" in code_prompt and "verbatim" in code_prompt,
    "order.code dispatches a snapshotted self-contained envelope verbatim",
)
expect("tooling-protocol.md" not in code_prompt, "order.code contains no dead tooling branch")
expect("Mark Gate Report Consumed" not in code_prompt, "order.code does not consume tasks gate reports")

tasks_prompt = (FRAMEWORK / "prompts" / "order.tasks.md").read_text(encoding="utf-8")
tasks_template = (FRAMEWORK / "templates" / "tasks-template.md").read_text(encoding="utf-8")
task_context_schema = json.loads(
    (FRAMEWORK / "schemas" / "task-context.schema.json").read_text(encoding="utf-8")
)
expect(
    "task_refine.py begin" in tasks_prompt
    and "task_refine.py validate" in tasks_prompt
    and "Refine only" in tasks_prompt,
    "order.tasks Refine protects existing progress without template regeneration",
)
expect(
    "work_order.py capture" in tasks_prompt,
    "order.tasks captures a reset baseline for each new work order",
)
expect(
    "mandatory for behavior-bearing support tasks" in tasks_prompt,
    "order.tasks supplies exact contract context to support paths",
)
expect(
    "Test-writing tasks state the expected" in tasks_prompt
    and "expected red/baseline/post-implementation result" in tasks_template,
    "order.tasks makes plan-selected evidence expectation task-local",
)
expect(
    "command-only lint/typecheck" in tasks_prompt
    and "begins with `VERIFY:`" in tasks_prompt
    and "forbid autofix/writes" in tasks_template,
    "order.tasks makes final command verification explicitly read-only",
)
expect(
    "exactly four fields" in tasks_prompt
    and "never omitted as a field" in tasks_prompt,
    "order.tasks defines one unambiguous four-field task format",
)
expect(
    "every `[NEW]`, `[MOD]`, and `[DEL]` path" in tasks_prompt
    and "Planned {tag} path" in (FRAMEWORK / "scripts" / "trace_validate.py").read_text(encoding="utf-8"),
    "order.tasks and mechanical validation require pathmanifest completeness",
)
expect(
    "never modify\nplan-owned state from `/order.tasks`" in tasks_prompt,
    "order.tasks routes mechanisms and mapping defects to the plan owner",
)
expect(
    "Commit after each task" not in tasks_template,
    "tasks template contains no implicit version-control side effect",
)
expect(
    "then `render`" not in tasks_prompt
    and "`render` produces" not in tasks_prompt,
    "order.tasks does not invoke removed traceability render command",
)
expect(
    "contract_refs"
    in task_context_schema["properties"]["tasks"]["additionalProperties"]["properties"],
    "task context schema permits support-path contract refs",
)

protocol = (FRAMEWORK / "protocols" / "sub-agent-execution.md").read_text(encoding="utf-8")
expect("task_context" in protocol and "to_read" in protocol, "protocol consumes resolver task context")
expect("MUST be copied verbatim" in protocol, "protocol forbids coordinator whitelist edits")
expect("contract_context" in protocol and "task_contract_context.py" in protocol, "protocol carries exact contract context")
expect("NEEDS_CONTEXT" in protocol and "changed_files" in protocol, "protocol defines bounded worker result")
expect(
    "worker-execution.json" in protocol and "MUST NOT restate or translate" in protocol,
    "protocol delegates worker-only rules to the canonical envelope",
)

worker_protocol = json.loads(
    (FRAMEWORK / "protocols" / "worker-execution.json").read_text(encoding="utf-8")
)
worker_schema = json.loads(
    (FRAMEWORK / "schemas" / "worker-envelope.schema.json").read_text(encoding="utf-8")
)
expect(worker_protocol["protocol_version"] == 1, "worker protocol is explicitly versioned")
expect(
    worker_schema["properties"]["protocol_version"]["const"] == 1,
    "worker envelope schema pins the protocol version",
)
expect(
    all(value is False for value in worker_protocol["capabilities"].values()),
    "worker envelope capabilities are default-deny",
)

codex_adapter = (FRAMEWORK / "adapters" / "codex.py").read_text(encoding="utf-8")
expect(
    "ORDERSPEC:ADAPTER_SUBAGENT_RULES" in code_prompt
    and "orderspec.worker.weak" in codex_adapter
    and "built-in `worker`" in codex_adapter
    and "configuration_ready" in codex_adapter,
    "order.code receives exact Codex weak-worker selection from its adapter",
)

print("All order-code contract tests passed")
