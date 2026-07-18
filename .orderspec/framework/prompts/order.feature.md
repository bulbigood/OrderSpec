---
orderspec:
  artifact: command_prompt
  command: order.feature
  phase: state
description: Inspect or atomically switch the active OrderSpec feature.
---

## Role

`/order.feature` owns selection of an existing active feature. It writes only
`.orderspec/state/active-feature.json` through `active_feature.py`. It does not
create features, edit artifacts, update project contracts, or inspect code.

## Input

```text
$ARGUMENTS
```

Supported control: `--select <feature-ref>`.

Unflagged text is semantic input, never selection authority. With semantic text
but no `--select`, use the feature list to identify matching candidates and
return the exact `/order.feature --select <feature-id>` command. Do not mutate.
With neither control nor semantic text, report current selection and available
features.

## Procedure

1. Resolve context and parsed input before other work:

   ```bash
   python3 .orderspec/framework/scripts/command_context.py resolve order.feature \
     --arguments "$ARGUMENTS" --json
   ```

   Stop on failure. Read every `to_read` item once in returned order.

2. Inspect canonical state and candidates:

   ```bash
   python3 .orderspec/framework/scripts/active_feature.py get --json
   python3 .orderspec/framework/scripts/active_feature.py validate --json
   python3 .orderspec/framework/scripts/active_feature.py list --json
   ```

   Missing state routes to `/order.bootstrap`. Invalid state stops with script
   output. Never repair state manually.

3. If `input.controls.select` exists, resolve it read-only:

   ```bash
   python3 .orderspec/framework/scripts/active_feature.py resolve \
     --feature "<input.controls.select>" --json
   ```

   Zero matches stops as not found. Multiple matches stop as ambiguous and list
   candidates. Never choose a winner semantically.

4. Select only the exact resolved reference:

   ```bash
   python3 .orderspec/framework/scripts/active_feature.py select \
     --feature "<input.controls.select>" \
     --last-command order.feature --json
   ```

5. Run `active_feature.py validate --json`. Report previous and current
   `feature_id`, `feature_directory`, and restored lifecycle `status`. Claim
   success only when selection and validation both succeed.
