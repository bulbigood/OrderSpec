# Philosophy

## Why OrderSpec exists

Many spec-driven workflows assume a model can hold an entire feature in
context, infer missing contracts, and implement correctly in one pass. Smaller
or cheaper models often drift, hallucinate scope, skip acceptance criteria,
confuse instructions with data, and silently desynchronize artifacts from code.

OrderSpec is designed around one question:

> **How does this behave when the model is not very smart?**

The answer is consistent: mechanical work goes to deterministic scripts,
semantic judgment is narrow and evidence-bound, and defects are routed to the
command that owns the affected artifact.

The model never owns lifecycle control flow. A deterministic state machine
selects the next legal transition and supplies one bounded semantic packet; the
model returns schema-validated evidence for that packet.

## Design principles

- **Specs are the source of truth.** Code, plans, tasks, and generated views
  derive from the logical contract.
- **Weak-model-first.** The workflow must remain reliable on modest models,
  not only frontier models.
- **Deterministic core.** Resolution, validation, synchronization, and state
  management do not depend on model memory.
- **One semantic question at a time.** Workflow engines enumerate work and
  evidence obligations; models judge or implement one bounded packet.
- **Gates detect and route; owners fix.** Inspection and authorship remain
  separate.
- **Default-deny capabilities.** Silence in project governance is never
  permission.
- **Stable truth, disposable derivatives.** Specifications survive repository
  movement; plans and tasks can be regenerated at their lifecycle boundaries.
- **Plans choose; work orders sequence.** Delivery strategy, transitions,
  mechanisms, evidence topology, and dependencies belong to the plan.
  `tasks.md` compiles their execution order without adding a second HOW-layer.
- **No orphans.** Requirements trace forward to implementation and tests;
  implementation paths trace back to contract elements.
- **Drift is a defect.** Consistency is checked mechanically rather than left
  to human vigilance.
- **Project- and stack-agnostic.** Logical specifications do not embed a
  language, framework, runtime, or package manager.
- **Agent-agnostic core.** Agent-specific detection and delivery live in
  adapters.
- **Readable by humans and machines.** Precise prose, stable IDs, tables, and
  structured islands serve both without a lossy second representation.
- **Framework internals stay internal.** Runtime agents use resolver output;
  internal manifests are framework input, not ambient prompt instructions.

Correctness has priority over token reduction. Documents remain narrow and
engineer-facing, but do not omit constraints merely to shorten prompts.

For weak models, repetition is not a substitute for determinism. Author
commands should receive machine-built candidate structure and answer bounded,
schema-validated semantic questions; scripts should render and validate the
result. A large prompt that asks the model to reconstruct lifecycle state is a
transitional implementation, not the target architecture.

## Comparison with spec-kit and OpenSpec

The frameworks have superficially similar pipelines but different centers of
gravity.

| | spec-kit | OpenSpec | OrderSpec |
|---|---|---|---|
| Core belief | spec is scaffolding for a capable model | spec is a proposal for review | spec is a contract a fallible model must not break |
| Optimized for | model productivity | human alignment | reliable execution by relatively weak models |
| Document roles | spec / plan / tasks | proposal / spec / tasks | stable contract / repository-mapped plan / disposable work order |
| Gate behavior | generation-centric | review-centric | pure inspection and defect routing |
| Mechanical work | often in-model | often in-model | deterministic scripts |

In one line: spec-kit emphasizes enabling the model, OpenSpec emphasizes
reviewing a proposed change, and OrderSpec emphasizes mechanically constraining
execution against a stable contract.

## Coexistence with other frameworks

OrderSpec keeps its contracts, feature artifacts, state, configuration,
reports, and framework files under `.orderspec/`. `/order.bootstrap` creates or
amends only OrderSpec-owned project contracts in `.orderspec/contracts/` and
does not adopt similarly named files at the repository root. This containment
allows another specification framework to coexist without filename collisions.
