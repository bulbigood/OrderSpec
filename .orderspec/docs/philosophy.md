# Philosophy

## Why OrderSpec exists

Most spec-driven tooling assumes a strong model that can hold a whole feature in its head, reason about contracts, and write correct code in one pass.

In practice, many teams run cheaper or smaller models — and those models drift, hallucinate scope, skip acceptance criteria, confuse instructions with data, and silently desync documents from code.

OrderSpec is designed for exactly that environment.

Every design choice answers the same question:

> **How does this behave when the model is not very smart?**

The answer is consistent:

> **Mechanical work goes to deterministic scripts. Judgment is narrow and routed. Gates detect and delegate — they never improvise.**

## Design principles

- **Weak-model-first.** The workflow is tuned to run reliably on modest models, not only frontier models.
- **Deterministic scripts own mechanical work.** Resolution, validation, bootstrap generation, agent sync, and state management should not depend on model memory. AI agent = semantic glue between deterministic logic parts.
- **Gates detect and route; owners fix.** A gate is an inspector, not an author.
- **Quality first.** Generated documents and code are the product. Everything else bends to keep them correct.
- **Token-efficient, but correctness wins.** Lean prompts are valuable, but not at the cost of ambiguity or broken contracts.
- **Engineer-facing.** Documents assume technical literacy and use precise terminology.
- **Readable to humans and models alike.** Stable IDs, tables, explicit sections, and narrow responsibilities.
- **Phase-separated.** Work is split across bootstrap, spec, plan, tasks, and code so no single step is overloaded.
- **Project- and stack-agnostic.** The framework is not tied to a language, runtime, or package manager.
- **Agent-agnostic core.** Framework core is independent of any specific AI agent; agent-specific logic lives in adapters.
- **Default-deny capabilities.** Commands and gates only do what project governance permits.
- **Framework internals stay internal.** Runtime agents use resolver output, not internal manifests, to decide what to read.
- **One source of truth for prompts.** Prompts live in `.orderspec/framework/prompts/` and are delivered to agents by adapters.

## Comparison with spec-kit and OpenSpec

See the [README](../README.md#comparison-with-spec-kit-and-openspec) for the side-by-side comparison.

The core difference in one line:

> **spec-kit and OpenSpec assume the model is smart; OrderSpec assumes it is not, and pushes every judgment call to either a script or a human-owned command.**

## Multi-framework coexistence

OrderSpec keeps all of its generated content (project contracts, feature artifacts, state, reports) under `.orderspec/`, so it does not clutter the repository root or collide with other frameworks' files.

The intended model is:

- if a project contract is missing, `/order.bootstrap` creates it under `.orderspec/contracts/`;
- if a contract already exists and is OrderSpec-owned, `/order.bootstrap` amends it;
- OrderSpec does not write outside `.orderspec/`, so similarly named non-OrderSpec files at the repository root are left untouched;
- future versions may support configurable contract paths.
