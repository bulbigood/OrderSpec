# Hook execution protocol

Shared contract for every `order.*` command. A command invokes this protocol
twice: once **before** its main work (`before_<command>`) and once **after**
(`after_<command>`). Commands reference this file — they never restate the rules.

## Procedure

1. If `.orderspec/extensions.yml` does not exist → skip silently.
2. Read it. If it cannot be parsed as valid YAML → skip silently, continue normally.
3. Read the entries under `hooks.<phase>` (e.g. `hooks.before_spec`, `hooks.after_code_check`).
   If the key is absent or empty → skip silently.
4. For each hook:
   - Skip it if `enabled` is explicitly `false`. Absent `enabled` ⇒ enabled.
   - **Do not interpret `condition`.** If `condition` is present and non-empty,
     skip the hook here and leave evaluation to the HookExecutor. If absent/empty,
     the hook is executable.
5. Emit each executable hook by its `optional` flag:

   **Optional** (`optional: true`):

   ```text
   ## Extension Hook
   Optional {phase} hook: {extension}
   Command: `/{command}` — {description}
   Prompt: {prompt}
   To execute: `/{command}`
   ```

   **Mandatory** (`optional: false`):

   ```text
   ## Extension Hook
   Automatic {phase} hook: {extension}
   EXECUTE_COMMAND: {command}
   ```

   For a **mandatory pre-hook**, wait for its result before continuing.

## Invariants

- This protocol only **detects and emits** hooks. It never evaluates conditions
  and never executes anything beyond surfacing `EXECUTE_COMMAND`.
- Missing file, missing key, or invalid YAML are all non-errors → silent skip.
