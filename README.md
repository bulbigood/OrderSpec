# OrderSpec

**Spec-driven development for relatively weak LLMs — built for engineers, hardened for teams.**

> ⚠️ **Adaptation status:** OrderSpec is currently adapted for **[Kilo Code](https://kilocode.ai/)** only. There is **no installer yet** — setup is manual (drop the prompts and scripts into your project). Support for other agents and a proper installer are future work.

OrderSpec is a spec-driven workflow that turns a feature idea into a verifiable implementation through four explicit phases — **specify → plan → tasks → implement** — each guarded by an optional verification gate. It is a re-architecture of the [spec-kit](https://github.com/github/spec-kit) pipeline, redesigned around one core constraint: **it must run reliably on relatively weak LLM models.**

---

## Why OrderSpec exists

Most spec-driven tooling assumes a strong model that can hold a whole feature in its head, reason about contracts, and write correct code in one pass. In practice, many teams run cheaper or smaller models — and those models drift, hallucinate scope, skip acceptance criteria, and silently desync documents from code.

OrderSpec is designed for exactly that environment. Every design choice answers the same question: *"How does this behave when the model is not very smart?"*

The answer, throughout, is one pattern:

> **Mechanical work goes to scripts. Judgment is narrow and routed. Gates detect and delegate — they never improvise.**

---

## The three-document model

OrderSpec splits a feature into three documents with **distinct roles and distinct lifecycles**. This separation is the heart of the framework: the cognitive load is spread across phases so no single step is overloaded, and each document stays readable to both humans and models.

| Document | Role | Stability |
|----------|------|-----------|
| `spec.md` | **WHAT** + logical architecture — the contract | **Stable. The source of truth.** |
| `plan.md` | **WHERE / HOW** — mapping onto physical code, stack, gates | **Regenerated** to match the current repository state |
| `tasks.md` | **ORDER** — the E-M-C execution sequence | **Disposable.** A one-shot work order |

The key insight: **`plan.md` depends on the state of the repository; `spec.md` does not.** A spec is a contract about behavior — it survives refactors, renames, and merges. A plan is a snapshot of *how* to realize that contract against the code as it exists *right now*, so it is regenerated whenever the codebase moves underneath it. Tasks are pure throwaway: generate, execute, discard.

---

## The pipeline

```
/order.spec  →  /order.plan  →  /order.tasks  →  /order.code
   WHAT           WHERE/HOW        ORDER            IMPLEMENT
```

Each phase has an **optional verification gate** that checks the *previous* phase's artifact before you proceed:

| Phase | Author command | Gate (optional) | The gate verifies |
|-------|----------------|-----------------|-------------------|
| Specify | `/order.spec` | `/order.spec-check` | spec is a valid, self-consistent, testable WHAT-contract |
| Plan | `/order.plan` | `/order.plan-check` | plan is correctly derived from spec + repo |
| Tasks | `/order.tasks` | `/order.tasks-check` | tasks are correctly derived from plan |
| Implement | `/order.code` | `/order.code-check` | the **code** faithfully implements the contract |

Plus one **event-triggered** gate that stands outside the linear flow:

| Gate | When you run it | What it does |
|------|-----------------|--------------|
| `/order.sync-check` | after a **merge / rebase / long branch / hand-edit** | detects drift, cross-version ID collisions, and repo-staleness **between artifacts**, then routes reconciliation to the owning command |

`sync-check` checks **artifact ↔ artifact** consistency. `code-check` checks **code ↔ contract**. Together they cover the two axes along which a merge can break a feature.

---

## How gates behave (the governance model)

Every gate in OrderSpec is a **pure inspector**. This single rule explains the whole system:

- **Gates detect and route. Owners fix.** A gate never rewrites a spec to resolve an ambiguity, never picks a winner in a merge conflict, and — for `code-check` — never edits a line of code. It emits a **Routing block** naming the command that *should* make the change.
- **The only writes a gate makes are mechanical and reversible** — normalizing a term to the glossary, fixing an unambiguous stale ID reference. Anything that touches *meaning* or *scope* is routed, not applied.
- **`code-check` writes nothing at all.** Code edits are never unambiguously reversible, so the terminal gate is pure-route: it reads, optionally runs the tests, and reports.

This is what makes OrderSpec safe under a weak model: the model is never trusted to silently "improve" your contract. The worst a confused gate can do is route a bad suggestion to a human-driven command.

---

## Customization

OrderSpec is meant to bend to your project, not the reverse.

- **Optional gates.** Every `*-check` is optional. On a small single-session MVP you can skip them; on a large or team project you run them as hard gates.
- **Hooks.** Every gate exposes `before_*` and `after_*` extension points via `.specify/extensions.yml`. Wire in your own steps — e.g., run a **linter as an `after_code_check` hook** (linting is deliberately *outside* the contract scope of the gates).
- **Constitution-gated capabilities.** A project `constitution.md` governs not just *what* is allowed but *how* gates may gather evidence. `code-check` runs your test suite or compiler **only when the constitution explicitly permits it** — otherwise it degrades to static inspection. Silence means deny.

---

## Environment requirements

OrderSpec is intentionally lightweight and **environment-independent**:

- **Prompts + shell scripts** (`sh` / `bat`), with **optional** Python.
- **No package manager, no `uv`, no Python toolchain to install.** If you can run the prompts in Kilo Code and execute a shell script, you can run OrderSpec.

This is a deliberate departure from spec-kit's installer-and-Python-CLI model.

---

## Philosophy: OrderSpec vs spec-kit vs OpenSpec

The three frameworks share a pipeline shape but believe different things about the world.

> **spec-kit** believes the spec is **scaffolding for a capable model**.
> The document exists to get the model productive; the model is trusted to fill the gaps and write the code. Optimized for generation speed with a strong agent.

> **OpenSpec** believes the spec is a **proposal to be reviewed**.
> The center of gravity is the change proposal and its review loop — alignment between humans on *what* to build before building it.

> **OrderSpec** believes the spec is a **contract that a weak model must not be allowed to break**.
> The document is the source of truth; the model is a fallible executor. Every phase is guarded, every judgment is narrow and cited, and every fix is routed to a named owner instead of being silently improvised. The system is built to stay correct *despite* the model, not *because of* it.

In one line: **spec-kit and OpenSpec assume the model is smart; OrderSpec assumes it isn't, and pushes every judgment call to either a script or a human-owned command.**

### Side by side

| | **spec-kit** | **OpenSpec** | **OrderSpec** |
|---|---|---|---|
| Core belief | spec = scaffolding for a smart model | spec = a proposal to review | **spec = a contract a weak model must not break** |
| Primary audience | general | general | **software engineers** (assumes technical fluency) |
| Optimized for | capable models | human alignment | **relatively weak models** |
| Document roles | spec / plan / tasks | proposal / spec / tasks | **spec (contract) / plan (repo-mapped) / tasks (disposable)** — distinct lifecycles |
| Load distribution | — | — | **split across phases**; no single phase overloaded |
| Gate behavior | generation-centric | review-centric | **pure inspectors: detect + route, owners fix** |
| Merge / team safety | — | — | **dedicated `sync-check`** for artifact desync across merges/branches |
| Code verification | — | — | **terminal `code-check`** (code ↔ contract, tests as oracle) |
| Mechanical work | in-model | in-model | **offloaded to scripts** (traceability, prerequisites) |
| Environment | Python CLI + installer | Node | **prompts + sh/bat, optional Python; no installer** |
| Customization | templates | — | **hooks + optional gates + constitution-gated capabilities** |

---

## Design philosophy

The principles that shaped every prompt:

- **Weak-model-first.** Tuned to run reliably on modest models (DeepSeek V4 Flash and MiMo V2.5 are the baseline), not just frontier ones.
- **Gates detect and route; owners fix.** The defining trait of OrderSpec — the model is a fallible executor, never trusted to silently rewrite a contract. Every fix is routed to a named, human-owned command.
- **Quality first.** The generated documents and code are the product. Everything else bends to keep them correct.
- **Token-efficient, but quality wins.** Lean by design; where leanness and correctness conflict, correctness always wins.
- **Engineer-facing.** Documents target a technically literate reader — precise terminology, contract-grade criteria, no hand-holding.
- **Readable to humans and models alike.** Stable IDs, anchored sections, tables over prose.
- **Scales both ways.** Reliable from a one-file MVP to a large multi-team codebase, and from solo work to a full team — without changing tools.
- **Balanced load.** Work is split across phases so no single step is overloaded.
- **Project- and stack-agnostic.** Nothing is tied to a language, framework, or runtime.
- **Customizable.** Optional gates and hooks let teams turn strictness up or down.
- **Environment-independent.** Prompts plus `sh`/`bat` scripts (optional Python). No installer, no package manager.

---

## Quick start

> Manual setup (no installer yet). Targets Kilo Code.

1. Copy the OrderSpec prompts and the `.specify/` directory (scripts, templates, optional `constitution.md`) into your project.
2. In Kilo Code, run the pipeline:

   ```
   /order.spec    "describe the feature you want"
   /order.plan
   /order.tasks
   /order.code
   ```

3. Run any gate when you want verification:

   ```
   /order.spec-check        # before planning
   /order.plan-check        # before tasking
   /order.tasks-check       # before implementing
   /order.code-check        # before merging
   /order.sync-check        # after a merge / rebase / long branch
   ```

---

## Status & roadmap

- ✅ All five gates and three author commands implemented (`/order.*`).
- ✅ Constitution-gated execution, hooks, optional gates.
- 🔜 Installer.
- 🔜 Adapters for agents beyond Kilo Code.
- 🔜 `.sh` / `.bat` parity verification across all scripts.

---
