# Blocking Feedback Protocol

This protocol is the single cross-command handoff mechanism for a command that
cannot continue because an earlier author-owned artifact or project contract is
missing, contradictory, incomplete, or invalid.

## Three distinct evidence layers

- `*-report.md` is canonical gate output and is written only by its matching
  `*-check` command. Never create an informal report, relax its format, or call
  a check recursively merely to record an already-observed blocker.
- `.state/feedback/{FB,PFB}-*.json` is a persistent, typed owner handoff.
- `.state/code-attempts/*` is local execution evidence, not a handoff. Close an
  active attempt before creating feedback. Reference its attempt ID when useful.

## Intake

`command_context.py resolve` returns `feedback.open` for owner commands. Treat
every open item targeting the current command as mandatory input. With empty
semantic input it selects the command's repair-capable mode (`Refine`,
`Reconcile`, or the bootstrap equivalent). Explicit input may add scope but
never suppress an open item.

Do not consume feedback before mutation. Consume each item only after the
owned artifact has been repaired and its deterministic validation succeeds.
Use the item's `scope` and `id`:

```bash
# scope: feature
python3 .orderspec/framework/scripts/workflow_feedback.py consume \
  --feature-dir "$FEATURE_DIR" --id "FB-NNN" --consumer order.<owner>

# scope: project
python3 .orderspec/framework/scripts/workflow_feedback.py consume \
  --scope project --project-root "$PWD" \
  --id "PFB-NNN" --consumer order.<owner>
```

A malformed canonical `*-report.md` is not an informal fix-list. Leave it to
the matching check command to regenerate. Resolver feedback remains independent
of report formatting.

## Persistence before a routed stop

Before `STOP`/`HALT` for an evidenced defect owned by an earlier author command:

1. If a valid active canonical gate report contains a finding routed to that
   report's own author command, cite the report and finding ID; the owner
   already loads its self-report, so it is persistent intake.
2. A finding routed from a gate report to a different author command must also
   create a compact feedback item referencing the report path and finding ID;
   the other owner does not scan unrelated gate reports.
3. Otherwise create feedback before returning. Use feature scope when a safe
   feature directory is resolved; otherwise use project scope.
4. Use the shortest decisive evidence and one bounded requested change. The
   script fingerprints open items, so repeating the same route is idempotent.

```bash
python3 .orderspec/framework/scripts/workflow_feedback.py create \
  --feature-dir "$FEATURE_DIR" --input-file - <<'JSON'
{"source":"order.<source>","target":"order.<owner>","category":"<category>","summary":"<summary>","evidence":"<evidence>","location":"<location>","requested_change":"<bounded change>"}
JSON
```

For project scope replace `--feature-dir "$FEATURE_DIR"` with
`--scope project --project-root "$PWD"`.

Do not create feedback for a user clarification, an operator refusal, or a
transient environment failure that does not identify an earlier author-owned
defect. Do not route a framework implementation failure to an artifact owner.

When an automation supervisor run is active, submit the created report without
translating its fields or hand-authoring a ROUTE event:

```bash
python3 .orderspec/framework/scripts/workflow_supervisor.py route-feedback \
  --run-file "$RUN_FILE" --feedback-file "$FEEDBACK_REPORT"
```

Execute an `AUTO_ROUTE` result's exact `next_action`. On `PAUSE` or `STOP`, show
the returned `operator_action` verbatim; never replace it with a generic repair
or diagnosis request.

## Gate commands

After finalizing its canonical report, a gate creates feedback only for routed
findings owned by a different author command. This script-owned bookkeeping is
not artifact repair. A finding routed to the matching artifact author remains
in the self-report without duplication. When no safe report target exists but
an earlier owner and decisive defect are known, use project feedback. Gates
remain inspectors and never consume owner feedback.
