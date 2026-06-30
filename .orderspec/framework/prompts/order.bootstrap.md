---
orderspec:
  artifact: command_prompt
  command: order.bootstrap
  prompt_version: "0.2.0"
  phase: bootstrap
description: Create or amend four project-level contract documents — stack.md, architecture.md, conventions.md, and constitution.md. Infers stack and architecture from the repository on first run.
handoffs:
  - label: Write a specification
    agent: order.spec
    prompt: With project contracts in place, specify the feature. I want to build...
---

## Role

`/order.bootstrap` creates and maintains four **project-level contract documents** that feature specs and plans reference instead of duplicating:

| Document | Location | ID prefix | Content |
|---|---|---|---|
| `stack.md` | project root | `STACK-NNN` | Technologies, versions, purpose |
| `architecture.md` | project root | `ARCH-NNN` | Layers, dependency rules |
| `conventions.md` | project root | `CONV-NNN` | Error handling, serialization, validation patterns |
| `constitution.md` | project root | named headings | Governance principles + capability grants for gates |

These are **stable, shared, project-wide**. They are NOT feature specs. They survive refactors. `spec.md` and `plan.md` cite them by ID.

This command **authors** project contracts. It does **not** rewrite feature specs, plans, or tasks that reference them — on conflict, it **routes** to the owning command.

## User Input

```text
$ARGUMENTS
```

Consider the user input before proceeding (if non-empty).

## Command Context Bootstrap

Before starting command-specific logic:

1. Resolve command context:

   ```bash
   python3 .orderspec/scripts/command_context.py resolve order.bootstrap --json
   ```

2. If `ok` is `false` or `missing_required` is non-empty, STOP and report the missing required context.
3. Read every file returned in `to_read`, in returned order.
4. Interpret each file according to its `usage` field:
   - `apply`: apply as procedural command rules.
   - `constrain`: enforce as project constraints.
   - `parse`: parse as structured config or runtime state.
   - `inspect`: inspect as command input/output artifact.
   - `reference`: use only as reference or evidence.
5. Do not manually load additional framework rules, protocols, configuration files, project contracts, or runtime state before the main command logic unless they are returned by `command_context.py`.

Project contracts returned with `usage: "constrain"` constrain this command, but do not override framework rules.

## Pre-Execution Checks

No operator-defined pre-execution extension phases are supported in the current OrderSpec core.

Complete Command Context Bootstrap before mode detection.

## Mode Detection

Determine mode **before writing any managed file**. Read-only checks for the bootstrap script, existing project contracts, manifests, and repository structure are allowed:

1. **Init** — one or more of the four documents are missing. Goal: create missing project contracts and ensure all four are present.
2. **Amend** — all four exist, user requests a change to one or more.
3. **Targeted amend** — `$ARGUMENTS` names a specific document and change (e.g., "add Redis to stack"). This mode is how `order.spec` calls bootstrap as a subagent.

State the detected mode in one line before proceeding.

**No-overwrite rule**: In Init Mode, create only missing project contract documents. If a managed document already exists, preserve it exactly unless the user explicitly requested an amend for that document. Existing documents may be read and validated, but must not be replaced.

## Deterministic Bootstrap Script

For weak-model reliability, Init Mode MUST delegate mechanical creation and validation to:

```bash
.orderspec/scripts/bootstrap_contracts.py
```

The model MUST NOT hand-write `stack.md`, `architecture.md`, `conventions.md`, or `constitution.md` during Init Mode.

### Script missing

Before Init Mode file creation, verify:

```bash
test -f .orderspec/scripts/bootstrap_contracts.py || echo "MISSING: bootstrap_contracts.py"
```

If missing → STOP and report:

> Bootstrap script not found. Restore `.orderspec/scripts/bootstrap_contracts.py` from the OrderSpec distribution.

Do not manually create project contracts unless the user explicitly requests emergency manual fallback.

### Required Init Mode flow

Execute Init Mode in this exact order:

1. Run:

   ```bash
   python3 .orderspec/scripts/bootstrap_contracts.py inspect --json
   ```

2. Parse the JSON output.
3. State the detected mode from `mode`.
4. If `requires_gate_question` is `true`, ask the gate capabilities question from this prompt.
5. Convert the user's answer to `--gate-profile A|B|C`.
   - For `A`, no test/lint commands are required.
   - For `B` or `C`, collect `--test-command` and `--lint-command` if provided; if omitted, the script will write `[UNRESOLVED: TEST_COMMAND]` / `[UNRESOLVED: LINT_COMMAND]`.
6. Run:

   ```bash
   python3 .orderspec/scripts/bootstrap_contracts.py init      --gate-profile <A|B|C>      --json
   ```

   Include `--test-command "<command>"` and `--lint-command "<command>"` when applicable.

7. Run:

   ```bash
   python3 .orderspec/scripts/bootstrap_contracts.py validate --json
   ```

8. If `init` or `validate` exits non-zero, STOP and report the script JSON. Do not repair generated files manually.
9. Report the script summary to chat.

### Init Mode ownership

In Init Mode, `bootstrap_contracts.py` owns creation/update of:

- `stack.md`
- `architecture.md`
- `conventions.md`
- `constitution.md`
- `.orderspec/config/tooling.json` (with empty defaults; operators add bindings later via amend)

The script generates these files directly from inferred repository data. It does not read or depend on template files.

## Gate Capabilities Question

When `requires_gate_question` is `true` in Init Mode, ask the user this question:

```markdown
## Question 1: Gate capabilities

**Context**: The constitution controls what gates may do when verifying specs and code.
**What we need to decide**: What commands may gates run as evidence?

**My recommendation**: Start restrictive — deny tests and builds initially; allow only static inspection. You can loosen later via amend.

| Option | Test execution | Build/lint | Network |
|--------|---------------|------------|---------|
| A (restrictive) | DENIED | DENIED | DENIED |
| B (moderate) | ALLOWED: `<your test command>` | ALLOWED: `<your lint command>` | DENIED |
| C (permissive) | ALLOWED: `<test>` | ALLOWED: `<lint>` | ALLOWED for: package registries |

**Reply** with a choice, or write `A` to accept the restrictive default.
```


## Agents Discovery & Sync Phase

After gate capabilities are determined and before tooling discovery, OrderSpec detects installed AI agents, asks the operator which to enable, and synchronizes prompts and skills directory configuration.

This phase runs in **both Init and Amend modes**. On Amend, it re-syncs all enabled agents and detects newly installed agents.

### Step 1 — Detect installed agents

```bash
python3 .orderspec/scripts/agents_sync.py detect --json
```

Parse the JSON output. Filter to agents where `detected` is `true`.

### Step 2 — Read current agent state

```bash
cat .orderspec/state/agents.json 2>/dev/null || echo '{"enabled_agents": []}'
```

Extract `enabled_agents` array. If the file does not exist, treat as empty list (first run).

### Step 3 — Ask user which agents to enable

**Bypass rule**: If only ONE agent is detected, AND it is already listed in `enabled_agents` in `agents.json`, you MAY skip this question and proceed directly to Step 5 (Sync).

Present detected agents and current configuration. Ask ONE blocking question:

```markdown
## Question: AI Agent Support

**Context**: OrderSpec can deliver prompts and register skills directories for multiple AI agents simultaneously. All enabled agents receive the same prompts from `.orderspec/framework/prompts/` and are configured to scan `.orderspec/skills/` for skill definitions.

**Detected agents**:
- Kilo Code (kilocode): Found .kilo/ directory (new format)
- [other agents if detected...]

**Currently enabled**: [list from agents.json, or "none — first run"]

**What this does**:
1. Registers `.orderspec/skills/` in each agent's config so skills are visible
2. Copies OrderSpec prompts to each agent's commands directory
3. Enables future prompt updates to propagate to all agents via re-running bootstrap

| Option | Answer |
|--------|--------|
| A | Enable all detected agents |
| B | Keep current selection |
| C | Custom selection — specify agent IDs (comma-separated) |

**Reply** with `A`, `B`, `C`, or a list of agent IDs like `kilocode,opencode`.
```

### Step 4 — Determine enabled agents list

Based on user's answer:
- **A**: all detected agent IDs
- **B**: current `enabled_agents` from agents.json (skip sync if unchanged and prompts are up-to-date)
- **C**: parse comma-separated agent IDs from user response
- **Explicit list**: use provided agent IDs

Validate that each requested agent ID was detected. If user requests an agent that was not detected, warn and ask for confirmation.

### Step 5 — Sync agents

Run the synchronization script with the determined agent list:

```bash
python3 .orderspec/scripts/agents_sync.py sync --agents <agent_id1> <agent_id2> ... --json
```

Parse the JSON output. Check for:
- `errors` array — if non-empty, report each error but continue
- `warnings` array — report each warning to the user
- `sync_results` — extract per-agent status

**Stale files handling**: If any agent has `missing_in_source` files (files in agent's prompts dir that don't exist in framework source), report them:

```markdown
### ⚠️ Stale Prompt Files

The following files exist in agent prompt directories but not in the framework source. They may be leftovers from renamed or removed prompts:

- `.kilo/commands/old-prompt-name.md`
- ...

These files are NOT deleted automatically. Remove them manually if no longer needed.
```

### Step 6 — Report

Add to the completion report:

```markdown
### Agents Sync
- Detected: N agents
- Enabled: M agents (list IDs)
- Skills dir registered: yes/no for each agent
- Prompts copied: N files (list if <10)
- Prompts up-to-date: M files
- Warnings: [list, or "none"]
```

## Tooling Discovery Phase

After the deterministic script creates all artifacts including `.orderspec/config/tooling.json`, the agent runs an interactive discovery phase. This phase is **optional** — if no MCP tools are available, the baseline `tooling.json` with defaults is valid and the project works.

### Step 1 — Check tooling availability

Determine what tools are available:

**CLI tools** (MUST run this command and use its exact output):
```bash
command -v npx >/dev/null 2>&1 && npx skills --help >/dev/null 2>&1 && echo "npx_skills=AVAILABLE" || echo "npx_skills=UNAVAILABLE"
```
Do not guess. If you do not run this command, you cannot proceed to discovery.

**MCP tools** (check your tool list):
- Is `context7` (or equivalent documentation MCP) available?
- Are there other relevant MCP servers?

Do not guess. If you cannot determine availability, report `unknown`.

### Step 2 — Ask user for discovery approval

Ask ONE blocking question:

```markdown
## Question 2: Tooling Discovery

**Context**: I detected N technologies in your stack. I can discover and install skills for library-specific work, and configure documentation sources.

**Available tools**:
- `npx skills` CLI: [paste exact output from Step 1 command]
- `context7` MCP: available / unavailable / unknown

**What I can do**:
1. Discover skills for: Express, MongoDB, Joi, Passport, ... (list key technologies from stack.md)
2. Install approved skills to `.orderspec/skills/`
3. Register bindings in `.orderspec/config/tooling.json`
4. Configure Context7 as required documentation source (if available)

**My recommendation**: Approve discovery — skills improve plan/code quality for library-specific work.

| Option | Answer |
|--------|--------|
| A | Discover and install all found skills (I will ask before each install) |
| B | Discover only, do not install — I will review and install later via amend |
| C | Skip discovery — empty tooling.json is valid, defaults from tooling-protocol.md apply |

**Reply** with `A`, `B`, or `C`.
```

### Step 3 — Perform discovery and installation (if approved)

#### 3a. Pre-discovery: check existing skills (MANDATORY)

Before searching for new skills, check what is already available:

```bash
# Check global skills
echo "=== Global skills ==="
ls ~/.agents/skills/ 2>/dev/null || echo "(none)"

# Check local project skills
echo "=== Local project skills ==="
ls .orderspec/skills/ 2>/dev/null || echo "(none)"
```

Match existing skills (global and local) against technologies in `stack.md`:
- For each existing skill, determine if it covers a technology in the stack
- Build a list of "already available" skills with their target `STACK-NNN`
- If a relevant skill exists globally but not locally, plan to `mv` it to `.orderspec/skills/`

Note: The deterministic `validate_tooling.py` script (run in Step 5) will catch any "installed" skills that are missing their `SKILL.md` file and report them as errors. You will fix them during validation.

#### 3b. Adjusted discovery (requires `npx skills` CLI)

**Skip this step entirely if `npx skills` CLI is unavailable.** Only pre-existing skills from Step 3a will be used.

Only search for skills for technologies NOT already covered by existing skills:

```bash
# Verify CLI is available first
command -v npx >/dev/null 2>&1 && npx skills --help >/dev/null 2>&1 || { echo "npx skills CLI not available — skipping discovery"; exit 0; }

# For each uncovered technology:
npx skills find <technology> 2>&1 | head -30
```

Collect results: skill name, source, install count.

**Quality Filter (MANDATORY)**:
You MUST filter out low-quality or unused skills.
- **Threshold**: Only consider skills with **>= 1000 installs**.
- **Exception**: If a technology has no skills >= 1000 installs, you MAY consider the highest one if it has > 100 installs, but report it as "low popularity".
- **Semantic Fit**: Ensure the skill name and description actually match the technology and your project's needs. Do not install a skill just because the name matches a keyword (e.g., "joinquant" is not a "joi" validation library).

If `npx skills` is unavailable, report: "Skill discovery skipped — npx skills CLI not available. Only pre-existing skills were used."

#### 3c. Present findings to user

Present a single table:
- **Already available (global/local)**: skills found in pre-discovery, with recommendation to move to local
- **Newly discovered**: skills found via `npx skills find`, with install counts

Ask for batch approval (one question for all actions: move + install).

#### 3d. Installation — DIRECT to `.orderspec/skills/`

**CRITICAL**: All project skills MUST end up in `.orderspec/skills/`, not globally.

**Step 1: Move existing global skills to local:**
```bash
mkdir -p .orderspec/skills
for skill in <list-of-global-skills-to-move>; do
    mv ~/.agents/skills/"$skill" .orderspec/skills/"$skill" 2>/dev/null && echo "Moved: $skill"
done
```

**Step 2: Install new skills (only if `npx skills` CLI is available):**
```bash
# Skip entirely if npx skills is not available
command -v npx >/dev/null 2>&1 && npx skills --help >/dev/null 2>&1 || { echo "npx skills CLI not available — skipping installation"; exit 0; }

mkdir -p .orderspec/skills
for skill in "repo1@skill1" "repo2@skill2"; do
    echo "Installing: $skill"
    npx skills add "$skill" -g -y 2>&1 | tail -3
    skill_name=$(echo "$skill" | cut -d'@' -f2)
    mv ~/.agents/skills/"$skill_name" .orderspec/skills/"$skill_name" 2>/dev/null || echo "  -> already moved or not found"
done
```

**Step 3: Verify:**
```bash
ls -la .orderspec/skills/
```

#### 3e. Record bindings via script (MANDATORY)

You MUST NOT edit `.orderspec/config/tooling.json` manually. Use the deterministic script:

```bash
python3 .orderspec/scripts/tooling_config.py add-binding \
  --stack-id STACK-006 \
  --technology "Express" \
  --skills "nodejs-express-server,express-oauth2-jwt-bearer" \
  --status installed
```

**Before setting `status: "installed"`**, verify the skill exists:
```bash
ls .orderspec/skills/<skill-name>/ 2>/dev/null && echo "EXISTS" || echo "MISSING"
```

If you find skills globally (in `~/.agents/skills/`) but not in `.orderspec/skills/`, you MAY move them:
```bash
mv ~/.agents/skills/<skill-name> .orderspec/skills/<skill-name>
```

### Step 4 — Configure Documentation Sources (via script)

If `context7` is available, ensure it is configured as required:
```bash
python3 .orderspec/scripts/tooling_config.py set-docs-policy \
  --source context7 \
  --policy required_if_available \
  --commands "order.plan,order.tasks,order.code" \
  --fallback "block_library_specific_claims_without_other_evidence"
```

Rules:
- Only add bindings for technologies where skills were actually found
- Set `status` to `installed` ONLY if skill files exist in `.orderspec/skills/`
- Set `status` to `discovered_only` if skill was found but not installed
- Do NOT write `skill: null` or use camelCase keys
- Do NOT silently install or register skills without user approval
- Do NOT install skills globally without moving them to `.orderspec/skills/`
- Do NOT manually edit `tooling.json` — always use `tooling_config.py`

### Step 5 — Validate tooling.json (MANDATORY)

Before reporting, run:

```bash
python3 .orderspec/scripts/validate_tooling.py --json
```

If `ok` is `false`:
- Fix every error before completing
- If `status='installed'` but skill not found in `.orderspec/skills/`:
  - Change `status` to `discovered_only` in `tooling.json`
  - Or actually install the skill (if you know how)
- If structural errors — fix JSON shape
- Re-run validation until `ok: true`

You MUST NOT complete bootstrap with invalid `tooling.json`.

### Step 6 — Report

Add to the completion report:

```markdown
### Tooling Discovery
- Tools: npx_skills=[AVAILABLE/UNAVAILABLE], context7=[available/unavailable/unknown]
- Pre-existing skills found: N (list names)
- Newly discovered: M (list names, or "none — npx skills unavailable")
- Skills installed: K (list names)
- Skills pending: L (list names, install via amend later)
- tooling.json bindings: N entries
- Context7 policy: required_if_available / disabled
- Skipped: user chose option C / no MCP tools available
```



## External Rules Integration Phase

After agents are synced and tooling discovery is complete, OrderSpec reads external rule files from enabled agents and offers to integrate uncovered statements into project contracts.

This phase respects the **External Rules Integration Policy** defined in `constitution.md`. If the policy section is absent, default to `constrain_on_bootstrap`.

### Step 1 — Read external rules

```bash
# Get enabled agents from state
ENABLED_AGENTS=$(python3 -c "import json; s=json.load(open('.orderspec/state/agents.json')); print(' '.join(s.get('enabled_agents', [])))")
python3 .orderspec/scripts/agents_sync.py read-rules --agents $ENABLED_AGENTS --json
```

Parse the JSON output. Collect `combined_files` and `combined_contents`.

If `combined_files` is empty, skip this phase entirely and report "No external rule files found."

### Step 2 — Check external rules policy

Read the policy from `constitution.md`:

```bash
grep -A 3 "External Rules Integration" constitution.md 2>/dev/null || echo "NOT_FOUND"
```

Policy values:
- `ignore` → skip this phase entirely. Report "External rules policy: ignore — rules not read."
- `constrain_on_bootstrap` (default) → proceed to Step 3. Rules are read only during bootstrap, not on every command.
- `constrain_always` → proceed to Step 3. Additionally, note that rules will be loaded as `constrain` source on every command via command context resolver. Warn the user about potential conflicts with OrderSpec contracts.

If the policy section is not found in `constitution.md`, assume `constrain_on_bootstrap` and note in the report that the default was used.

### Step 3 — Analyze rules against existing contracts

For each rule file found in `combined_contents`:
1. Read its content
2. Compare against existing `stack.md`, `architecture.md`, `conventions.md`
3. Identify statements not yet covered by existing contract IDs (`STACK-NNN`, `ARCH-NNN`, `CONV-NNN`)

Focus on extractable, enforceable statements:
- Technology choices ("use pnpm", "use PostgreSQL 15")
- Architectural rules ("routes must not call models directly")
- Coding conventions ("all functions must have JSDoc", "errors must use { error: { code, message } }")
- Tool preferences ("use eslint with airbnb config")

Ignore agent-specific formatting instructions (e.g., "respond concisely", "use bullet points") — these are agent configuration, not project contracts.

### Step 4 — Present findings to user

If new statements are found:

```markdown
## External Rules Found

The following statements from agent rule files are not yet reflected in project contracts:

**From AGENTS.md**:
- "Use pnpm instead of npm"
- "All functions must have JSDoc comments"
- "Error responses must use { error: { code, message, details } } format"

**From .cursorrules** (if cursor enabled):
- "Use named exports only"
- "Prefer async/await over .then()"

**Integration options**:
| Option | Answer |
|--------|--------|
| A | Integrate all into conventions.md (assign CONV-NNN IDs) |
| B | Review each — I'll select which to integrate |
| C | Skip — I'll integrate manually later via amend |

**Reply** with `A`, `B`, or `C`.
```

If no new statements are found (all rules already covered by existing contracts), report:

```markdown
### External Rules Integration
- Rule files read: N (list filenames)
- New statements found: 0 (all rules already covered by existing contracts)
- No integration needed.
```

And skip to the next phase.

### Step 5 — Integrate selected rules

If user approves integration (option A or B):

For each statement to integrate:
1. Assign next free `CONV-NNN` ID (sequential, append-only)
2. Append a row to `conventions.md`:

```markdown
| CONV-NNN | <concise statement> | From <source-file> | Auto-imported by bootstrap |
```

If user chose option B, present each statement individually and ask for approval.

**Do NOT remove or modify the original rule files** — they remain owned by their respective agents. The agent will continue reading them; OrderSpec now also has the equivalent in `conventions.md`.

### Step 6 — Report

```markdown
### External Rules Integration
- Policy: constrain_on_bootstrap / constrain_always / ignore / [default: constrain_on_bootstrap]
- Rule files read: N (list filenames)
- New statements found: M
- Statements integrated: K (list CONV-NNN IDs and descriptions)
- Skipped: J (user chose C, or no new statements)
```

## Init Mode Manual Fallback Reference

<details>
<summary>Emergency manual fallback (only when script is missing and user explicitly approves)</summary>

### Step 1 — Infer stack from repo (brownfield) or ask (greenfield)

Check for a manifest file:

```bash
test -f package.json && echo "HAS_PACKAGE_JSON"
test -f go.mod && echo "HAS_GO_MOD"
test -f pyproject.toml && echo "HAS_PYPROJECT"
test -f Cargo.toml && echo "HAS_CARGO"
test -f pom.xml && echo "HAS_POM"
```

- **If a manifest exists** (brownfield): read it. Extract `dependencies` / `require` / listed packages. For each dependency that is a **runtime framework, database, or key library** (not a dev-tool like eslint), create one `STACK-NNN` row. Assign sequential IDs starting at `STACK-001`. Include the runtime itself as `STACK-001`.
- **If no manifest** (greenfield): ask the user one question: "What technologies will this project use? List runtime, framework, database, validation library." Create rows from the answer.
- **If the user provided stack info in `$ARGUMENTS`**: use it directly.

If `stack.md` is missing, create it with this structure:

```markdown
# Project Stack

Technologies used in this project.
Referenced by spec.md and plan.md as STACK-NNN.
Maintained via /order.bootstrap. IDs are append-only.

| ID | Technology | Version | Purpose | Notes |
|----|------------|---------|---------|-------|
| STACK-001 | | | | |
```

Fill the table rows. If `stack.md` already exists, preserve it and read it for validation/reporting only.

### Step 2 — Infer architecture from repo structure (brownfield) or ask (greenfield)

```bash
ls -d src/*/ 2>/dev/null || ls -d */ 2>/dev/null | head -20
```

- **If directories like `routes/`, `controllers/`, `services/`, `models/` exist**: record the layering as `ARCH-001`. Add explicit dependency rules per layer (`ARCH-002` through `ARCH-NNN`).
- **If directories like `modules/`, `features/`, `domains/` exist**: record as modular architecture (`ARCH-001`).
- **If no clear structure** or greenfield: ask the user one question: "What is the intended code structure? (e.g., layered: routes → controllers → services → models, or modular, or other)"
- Record dependency rules as `ARCH-NNN` entries.

If `architecture.md` is missing, create it with this structure:

```markdown
# Project Architecture

Structural contracts: layers and dependency rules.
Referenced by spec.md and plan.md as ARCH-NNN.
Maintained via /order.bootstrap. IDs are append-only.

## Layers

| Layer | Directory | Responsibility |
|-------|-----------|----------------|

## Dependency Rules

| ID | Rule |
|----|------|
```

Fill the sections. If `architecture.md` already exists, preserve it and read it for validation/reporting only.

### Step 3 — Create conventions (sparse)

- **Brownfield**: do NOT attempt to infer conventions from code. If `conventions.md` is missing, create it with the structure below and no invented `CONV-NNN` rows. If `conventions.md` already exists, preserve it and read it for validation/reporting only.
- **Greenfield**: same — create the file only if missing; leave contract rows empty.

```markdown
# Project Conventions

Implementation conventions: error handling, serialization,
validation patterns, shared plugins, etc.
Referenced by spec.md and plan.md as CONV-NNN.
Maintained via /order.bootstrap. IDs are append-only.
This file starts empty and grows as patterns are discovered.

| ID | Convention | Description | Notes |
|----|------------|-------------|-------|
```

Conventions grow organically through future **amend** calls, not through bootstrap inference.

### Step 4 — Create constitution

1. If `constitution.md` is missing, create it. If `constitution.md` already exists, preserve it and read it for validation/reporting only.
2. For a newly created `constitution.md`, fill `PROJECT_NAME` from the repo directory name or user input.
3. For a newly created `constitution.md`, fill `DATE` with today's date.
4. For a newly created `constitution.md`, **ask the user the gate capabilities question** (see Gate Capabilities Question section above).
5. For a newly created `constitution.md`, apply the answer to the Capability Grants section.
6. For a newly created `constitution.md`, fill the three default principles (Contract Stability, Spec-Code Separation, Default-Deny) — these are safe defaults that need no user input.

### Step 5 — Validate all four documents

- `stack.md`: every row has `STACK-NNN` with exactly 3 digits. No duplicate IDs.
- `architecture.md`: layers are listed. At least one dependency rule exists.
- `conventions.md`: file exists, structure is valid.
- `constitution.md`: no `[BRACKET]` placeholders remain (except `[TEST_COMMAND]` if user chose option B/C — that is `[UNRESOLVED]` and must be listed in the report). Every principle uses MUST or SHOULD. Every capability is explicitly ALLOWED or DENIED — no vague wording.

### Step 6 — Write and report manually only in emergency fallback

In normal Init Mode, do not execute this step manually; report the output from `bootstrap_contracts.py`.

If emergency manual fallback was explicitly approved by the user, write only newly created or explicitly amended files. Preserve existing project contracts that were only read for validation. Report to chat:

```markdown
## Bootstrap Complete

### Created / Ensured
- `stack.md` — N technologies (STACK-001 .. STACK-NNN)
- `architecture.md` — M rules (ARCH-001 .. ARCH-NNN)
- `conventions.md` — template structure with existing or 0 convention rows (fill via amend as patterns emerge)
- `constitution.md` — dated YYYY-MM-DD

### Inferred from repo
- [list what was auto-detected: manifest type, directory structure]

### Unresolved
- [list any [UNRESOLVED] markers, or "none"]

### Next steps
- Run `/order.spec` to write your first feature specification.
- Run `/order.bootstrap` again to amend any document as the project evolves.
```

</details>

## Amend Mode

Triggered when all four documents exist and the user requests a change.

### Step 1 — Classify the request

Identify which document(s) the request targets:

| Signal in `$ARGUMENTS` | Target document |
|---|---|
| "add", "remove", "upgrade" + technology name | `stack.md` |
| "layer", "dependency rule", "restructure" | `architecture.md` |
| "convention", "pattern", "error handling", "pagination" | `conventions.md` |
| "principle", "capability", "gate may", "allow", "deny" | `constitution.md` |

If unclear, ask the user once: "Which document should I update — stack, architecture, conventions, or constitution?"

### Step 2 — Apply the change

**stack.md / conventions.md**:
- Add → assign next free `STACK-NNN` / `CONV-NNN`. Append a row.
- Change → edit in place, same ID.
- Remove → tombstone the corresponding row using its existing ID, e.g. `| STACK-NNN | [removed — <reason>] | | | |` or `| CONV-NNN | [removed — <reason>] | | | |`. Do NOT delete the row or renumber.

**architecture.md**:
- Add → assign next free `ARCH-NNN`.
- Edit existing rule → same ID, updated text.
- Remove → mark as `ARCH-NNN: [removed — <reason>]`. Do not renumber.

**constitution.md**:
- Add/change principle → write as MUST or SHOULD (declarative, testable). SHOULD carries a skip-condition note.
- Change capability grant → write as explicit `ALLOWED. run: <command>` or `DENIED.` — nothing in between.
- Update `Last Amended` date.
- **Default-deny is law**: if a capability is not explicitly granted, it is denied. Never leave a capability blank or vague.


### Step 2.5 — Re-sync agents

After applying the requested change, re-synchronize agents to ensure prompt updates propagate:

```bash
# Read current enabled agents
ENABLED_AGENTS=$(python3 -c "import json; s=json.load(open('.orderspec/state/agents.json')); print(' '.join(s.get('enabled_agents', [])))" 2>/dev/null)

if [ -n "$ENABLED_AGENTS" ]; then
    python3 .orderspec/scripts/agents_sync.py sync --agents $ENABLED_AGENTS --json
else
    echo '{"sync_results": [], "warnings": ["No agents enabled — run bootstrap to configure agent support"]}'
fi
```

Parse the output. If any prompts were copied (not skipped), note in the report:

```markdown
### Agent Re-sync
- Agents re-synced: N
- Prompts updated: M files
```

If no agents are enabled, remind the user:

```markdown
### Agent Re-sync
- No agents enabled. Re-run bootstrap to configure agent support.
```

### Step 3 — Detect conflicts and route

Check whether the change **invalidates** existing feature specs or plans:

- A **removed or changed** `STACK-NNN`, `ARCH-NNN`, or `CONV-NNN` that a `spec.md` references → route to `/order.spec` for that feature.
- A **changed architecture rule** or convention that a `plan.md` relies on or violates → route to `/order.plan` for that feature.
- A **changed capability grant** → note which gate's behavior changes (e.g., "code-check may now run tests — existing features should re-run code-check").
- A **changed principle** that existing specs rely on → route to `/order.spec` for each affected feature.

Emit findings as a simple list:

```markdown
### Routing (owner must reconcile)
- `specs/003-user-auth/spec.md` references `STACK-004` which was removed → run `/order.spec` for that feature
- `specs/001-tasks/spec.md` references `ARCH-002` which changed → run `/order.spec` for that feature
- Constitution: test execution grant changed → re-run `/order.code-check` for all implemented features
```

You produce findings, not edits. Cross-artifact reconciliation is `sync-check`'s job.

### Step 4 — Validate and write

Run the same validation as Init Mode. Write the changed file(s). Report:

```markdown
## Bootstrap Amend Complete

### Changed
- `stack.md` — added STACK-008 (Redis 7.x, caching)

### Routing
- [list, or "none — no existing specs reference the changed IDs"]

### Next steps
- [if routing is non-empty: "Run the listed commands to reconcile affected features."]
- [if no routing: "No downstream impact. Continue with /order.spec."]
```

## Targeted Amend Mode (subagent call)

When `order.spec` invokes bootstrap as a subagent, the request is narrow: "add technology X to stack" or "add convention Y".

- Skip mode detection — the target document is named in the request.
- Skip the blocking question — there is no user to ask.
- Apply the change (Amend Mode Step 2).
- Run conflict detection (Amend Mode Step 3) — but output routing as a return value, not to chat.
- Return: the new ID assigned (e.g., `STACK-008`), or the updated ID, plus any routing findings.

## ID Discipline

Applies to `STACK-NNN`, `ARCH-NNN`, `CONV-NNN`:

- **Append-only.** Never renumber, reuse, or shift.
- **Defined once** in their document's table or list.
- **Referenced** by `spec.md` and `plan.md` as `STACK-001`, `ARCH-002`, etc.
- **Tombstone on removal** — never delete.

Constitution principles use named headings (I., II., III.), not numeric IDs.

## Constraints

- Operate only on bootstrap-owned artifacts: `stack.md`, `architecture.md`, `conventions.md`, `constitution.md`. Never edit `spec.md`, `plan.md`, `tasks.md`, or code.
- Preserve heading hierarchy and document structure.
- Never invent governance — if a value cannot be determined, mark `[UNRESOLVED: <field> — <why>]` and list it in the report.
- Brownfield inference is limited to manifest files and directory structure. Do not attempt to infer conventions, principles, or capability grants from code.

## Post-Execution Checks

No operator-defined post-execution extension phases are supported in the current OrderSpec core.

## Done When

- [ ] Command context resolved via `command_context.py` and every `to_read` file was read
- [ ] Mode detected and stated
- [ ] Init Mode: `.orderspec/scripts/bootstrap_contracts.py inspect --json` was run
- [ ] Init Mode: required gate question was asked when `requires_gate_question` was true
- [ ] Init Mode: `.orderspec/scripts/bootstrap_contracts.py init ... --json` was run
- [ ] Init Mode: `.orderspec/scripts/bootstrap_contracts.py validate --json` succeeded
- [ ] All targeted bootstrap-owned artifacts created or amended
- [ ] `.orderspec/config/tooling.json` is valid JSON with `version: 2`, `skills.bindings` array, and `docs_sources` object
- [ ] IDs are append-only, no duplicates, tombstoned on removal
- [ ] Constitution: no vague capabilities, no `[BRACKET]` placeholders (except listed `[UNRESOLVED]`)
- [ ] Conflicts with existing specs/plans detected and routed (not fixed)
- [ ] Report emitted to chat (init/amend) or returned (targeted amend)
- [ ] Agents Discovery & Sync Phase completed: detected agents, asked user, synced prompts and skills
- [ ] External Rules Integration Phase completed: read rule files, offered integration into conventions.md
- [ ] `.orderspec/state/agents.json` exists and is valid
- [ ] Amend Mode: agents re-synced after contract changes
