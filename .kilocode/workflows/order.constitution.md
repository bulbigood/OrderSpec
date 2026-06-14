---
description: Author or amend the project constitution — the supreme governance document that gates execute literally (principles + machine-readable capability grants).
handoffs:
  - label: Write a specification
    agent: order.spec
    prompt: With the constitution in place, specify the feature. I want to build...
---

## Role of this document

The constitution at `.orderspec/memory/constitution.md` is the **supreme law of the project**. It does two distinct jobs — keep them distinct:

1. **Principles** — declarative, testable rules the project must uphold (human-facing governance).
2. **Capability grants** — machine-readable permissions that **gates execute literally**. The most important: whether `code-check` (and other gates) may run the test suite, invoke a compiler/linter, or touch the network as evidence.

> **Default-deny is law.** If the constitution does not explicitly grant a capability, every gate MUST treat it as **denied** and degrade to static inspection. Silence is never "allowed". You are authoring the thing that other commands obey without re-interpretation — be unambiguous.

This command **authors and validates** the constitution. It does **not** rewrite specs, plans, tasks, or templates to match it: when an amendment conflicts with existing artifacts, you **detect and route** (name the owning command), you do not fix them here.

## User Input

```text
$ARGUMENTS
```

Consider the user input before proceeding (if non-empty).

## Pre-Execution Checks

Run the **`before_constitution`** phase per `.orderspec/memory/hooks-protocol.md`.

## Execution

### 1. Load

- Read `.orderspec/memory/constitution.md`. If missing, copy `.orderspec/templates/constitution-template.md` first, then read it.
- Identify every placeholder token `[ALL_CAPS_IDENTIFIER]`.
- The template's principle count is a default, not a quota. If the user asks for more/fewer principles, honor that.

### 2. Resolve values

For each placeholder and each requested change, in priority order:

1. **User input** (this conversation) — use it.
2. **Repo evidence** — infer from `README`, existing docs, or the prior constitution.
3. **Unresolved** — if a value genuinely cannot be determined, write the literal marker `[UNRESOLVED: <field> — <why>]` and list it in the Sync Impact Report. Do **not** invent governance.

Dates: `RATIFICATION_DATE` = original adoption (ask or mark `[UNRESOLVED]` if unknown). `LAST_AMENDED_DATE` = today (2026-06-14) if anything changed, else unchanged. ISO format `YYYY-MM-DD`.

### 3. Author the content

**Principles** — each principle MUST be:
- declarative and **testable** (a gate or a human can objectively judge compliance);
- written with `MUST` / `SHOULD` (never bare "should" / "we try to"); each `SHOULD` carries a one-line rationale for when it may be skipped;
- accompanied by a short rationale if the rule is non-obvious.

**Capability grants** — this is the section gates read. State each capability **explicitly and in plain machine-detectable terms**. At minimum address:
- **Test execution**: may a gate run the project's tests as evidence? If yes, name the command (e.g. `run: pytest -q`). If unstated → denied.
- **Build / compile / lint as evidence**: permitted? command?
- **Network access** during a gate: permitted? scope?
- **Mechanical auto-fixes**: may gates apply reversible normalizations (glossary terms, stale-ID references) automatically, or only route them?

Write grants as flat, unambiguous statements — no prose a weak model could misread. A reviewing gate must be able to answer "am I allowed to do X?" with a literal yes/no by scanning this section.

### 4. Version

Increment `CONSTITUTION_VERSION` (semantic) by the **highest-severity** change present:

| Bump | Trigger (detect, don't deliberate) |
|------|-----------------------------------|
| **MAJOR** | a principle or capability grant was **removed**, **reversed**, or made **more restrictive** |
| **MINOR** | a principle or grant was **added** or **materially expanded** |
| **PATCH** | wording, typos, clarifications — no change to what is required or permitted |

Pick the single highest bump that applies. State the rationale in one line.

### 5. Detect conflicts and route (do NOT fix)

Without rewriting anything, check whether this amendment **invalidates** existing artifacts, and route each finding to its owner:

- A changed/removed **principle** that an existing `spec.md` relies on → route to `/order.spec`.
- A changed **capability grant** that affects how a gate gathers evidence → note which gate's behavior changes.
- A new mandatory section that templates don't yet carry → route to template maintenance.

Emit these as a **Routing block**. You produce findings, not edits. (Cross-artifact reconciliation after the fact is `sync-check`'s job — point the user there if findings are broad.)

### 6. Validate before writing

- No unexplained `[BRACKET]` tokens remain (only intentional `[UNRESOLVED: …]`, each listed in the report).
- Every principle is testable and uses MUST/SHOULD correctly.
- Every capability is either explicitly granted or knowingly omitted (= denied); no capability is left vaguely worded.
- Version line matches the bump rationale; dates are ISO.

### 7. Write & report

Overwrite `.orderspec/memory/constitution.md`. Prepend a **Sync Impact Report** as an HTML comment:

```
<!--
Sync Impact Report
Version: <old> → <new> (<MAJOR|MINOR|PATCH>: <one-line reason>)
Principles changed: <list, with renames as old → new>
Capability grants changed: <list, with old → new where relevant>
Added / Removed sections: <list>
Routing (owner must reconcile):
  - <finding> → /order.<command>
Unresolved: <[UNRESOLVED] markers, or "none">
-->
```

Then output to the user: the new version + bump reason, the Routing block (what they must reconcile and where), any `[UNRESOLVED]` items, and a suggested commit message, e.g. `docs: amend constitution to v<X.Y.Z> (<short reason>)`.

## Constraints

- Operate **only** on the existing `.orderspec/memory/constitution.md`. Never create a parallel template.
- Preserve heading hierarchy from the template; do not demote/promote levels.
- Single blank line between sections; no trailing whitespace.
- Partial updates still go through versioning + validation + routing.
- **You author governance; you do not enforce it and you do not rewrite the artifacts it governs.**

## Post-Execution Checks

Run the **`after_constitution`** phase per `.orderspec/memory/hooks-protocol.md`.
