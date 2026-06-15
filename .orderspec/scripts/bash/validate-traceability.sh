#!/usr/bin/env bash
#
# validate-traceability.sh — mechanical cross-artifact validation for order.
#
# Deterministic checks only: ID-chain integrity, task numbering/format,
# path consistency, timestamp drift, placeholder residue. Semantic checks
# (role boundaries, contradictions, constitution, E-M-C semantics) are
# intentionally OUT of scope — they belong to /order.analyze (LLM).
#
# Portability: targets POSIX-ish bash. Avoids bash-4 features (no associative
# arrays), GNU-only utilities, and herestrings-with-side-effects. Uses only
# grep -E/-F/-o, sed, awk, sort, head/tail, tr, cut — present on Linux and
# *BSD/macOS alike. stat is probed for both GNU (-c) and BSD (-f) forms.
# Runs under any bash >= 3.2 (incl. macOS system bash). Not meant for plain sh.
#
# Usage:
#   validate-traceability.sh [--json] [--stage spec|plan|tasks] <FEATURE_DIR>
#
# --stage selects how much of the cascade is in scope. If omitted, the stage is
# AUTO-DETECTED from which artifacts exist:
#   spec only            -> stage=spec    (root of cascade; plan/tasks not yet authored)
#   spec + plan          -> stage=plan
#   spec + plan + tasks  -> stage=tasks   (full cascade)
# An explicitly-passed --stage wins; if its required artifact is missing that IS
# a usage error (exit 2). Downstream artifacts absent for an EARLIER stage are
# EXPECTED: dependent checks are skipped (reported), never fatal.
#
# Exit codes:
#   0 — no CRITICAL/HIGH findings AND no checks skipped (clean, full scope for the stage)
#   1 — at least one CRITICAL or HIGH finding (gate should block)
#   2 — usage error / artifact REQUIRED for the resolved stage is missing
#   3 — no CRITICAL/HIGH findings, but some checks were skipped because a
#       downstream artifact is expectedly absent (clean, partial scope)
#
# Checks (finding ID prefixes):
#   M1  Every REQ appears in >=1 UJ "Covers" list                [spec]
#   M2  Every AC referenced by >=1 task                          [tasks]
#   M3  Every EDGE and INV referenced by >=1 task                [tasks]
#   M4  Every [USn] task references >=1 spec ID                  [tasks]
#   M5  No dangling references                                    [plan/tasks]
#   M6  No unresolved Q-NNN / [NEEDS CLARIFICATION] in spec       [spec]
#   M7  Task IDs sequential; task line format valid               [tasks]
#   M8  Every file path in tasks.md exists in plan.md             [tasks]
#   M9  Plan path manifest: every file tagged [NEW]/[MOD]        [plan]
#   M10 Manifest [MOD]/[NEW] vs actual repo (stale-plan)         [plan]
#   M11 Timestamp drift                                           [plan/tasks]
#   M12 [P] tasks must not share file paths                       [tasks]
#   M13 Placeholder residue                                       [spec/plan/tasks present]
#   M14 [USn] labels map 1:1 to existing UJ-00n in spec           [tasks]

set -uo pipefail

# ---------- bash sanity (we use bash arrays + process substitution; not sh) ----------
if [ -z "${BASH_VERSION:-}" ]; then
  echo "FATAL: this script must run under bash, not sh/zsh-as-sh." >&2
  exit 2
fi

# ---------- args ----------
JSON=false
STAGE=""            # explicit stage if user passed --stage
FEATURE_DIR=""
expect_stage=false
for arg in "$@"; do
  if $expect_stage; then STAGE="$arg"; expect_stage=false; continue; fi
  case "$arg" in
    --json)    JSON=true ;;
    --stage)   expect_stage=true ;;
    --stage=*) STAGE="${arg#--stage=}" ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) FEATURE_DIR="$arg" ;;
  esac
done
if [ -z "$FEATURE_DIR" ]; then
  echo "Usage: $0 [--json] [--stage spec|plan|tasks] <FEATURE_DIR>" >&2
  exit 2
fi

SPEC="$FEATURE_DIR/spec.md"
PLAN="$FEATURE_DIR/plan.md"
TASKS="$FEATURE_DIR/tasks.md"

have_spec=false;  [ -f "$SPEC" ]  && have_spec=true
have_plan=false;  [ -f "$PLAN" ]  && have_plan=true
have_tasks=false; [ -f "$TASKS" ] && have_tasks=true

# spec.md is mandatory in every stage — it is the root of the cascade.
if ! $have_spec; then
  echo "FATAL: missing required artifact: $SPEC (re-run /order.spec)" >&2
  exit 2
fi

# ---------- resolve stage ----------
if [ -z "$STAGE" ]; then
  if   $have_tasks && $have_plan; then STAGE=tasks
  elif $have_plan;                then STAGE=plan
  else                                 STAGE=spec
  fi
fi
case "$STAGE" in
  spec|plan|tasks) ;;
  *) echo "Invalid --stage '$STAGE' (use spec|plan|tasks)" >&2; exit 2 ;;
esac

# Explicit stage must have its required artifacts; that's a genuine usage error.
if [ "$STAGE" = "plan" ] && ! $have_plan; then
  echo "FATAL: --stage plan requires plan.md (missing: $PLAN)" >&2; exit 2
fi
if [ "$STAGE" = "tasks" ] && { ! $have_plan || ! $have_tasks; }; then
  echo "FATAL: --stage tasks requires plan.md and tasks.md" >&2; exit 2
fi

# What is in scope for this stage (explicit, no one-line && pitfalls).
need_plan=false
need_tasks=false
case "$STAGE" in
  plan)  need_plan=true ;;
  tasks) need_plan=true; need_tasks=true ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# ---------- findings + skipped store (indexed arrays only; bash 3.2-safe) ----------
F_ID=(); F_CHECK=(); F_SEV=(); F_LOC=(); F_MSG=()
SK_CHECK=(); SK_REASON=()

# Per-check counter WITHOUT associative arrays: dynamic scalar vars COUNT_<check>.
# NOTE: add() MUST run in the current shell (never inside $(...)), otherwise the
# COUNT_* assignment dies in a subshell and IDs collide. It is only ever called
# directly in loop bodies, so this holds.
add() { # $1=check $2=severity $3=location $4=message
  local var="COUNT_$1" cur
  eval "cur=\${$var:-0}"
  cur=$((cur + 1))
  eval "$var=$cur"
  F_ID+=("$1-$(printf '%03d' "$cur")")
  F_CHECK+=("$1"); F_SEV+=("$2"); F_LOC+=("$3"); F_MSG+=("$4")
}
skip() { SK_CHECK+=("$1"); SK_REASON+=("$2"); }  # records an expected-absence skip

mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }
esc()   { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

ID_FAMILIES='REQ|NFR|CON|SC|INV|EDGE|UJ|AC|ASM'
ID_RE="\\b($ID_FAMILIES)-[0-9]+\\b"

# A token is treated as a real path ONLY if the filesystem agrees, so no
# language/extension whitelist is needed (stack-agnostic). A candidate counts
# as a path when it already exists OR its parent directory exists (a plausible
# [NEW] target). This rejects enum/expression noise like CREATE/UPDATE,
# try/catch, field:asc|desc — none of which resolve on disk.
looks_like_real_path() { # $1=candidate (repo-relative)
  local p="$1" parent
  case "$p" in
    *' '*|*'|'*|*':'*) return 1 ;;   # spaces / pipes / colons → enum, sortBy, regex, not a path
  esac
  [ -e "$REPO_ROOT/$p" ] && return 0
  parent="${p%/*}"
  [ "$parent" != "$p" ] && [ -d "$REPO_ROOT/$parent" ] && return 0
  return 1
}

# ---------- inventories ----------
SPEC_IDS=$(grep -oE "$ID_RE" "$SPEC" 2>/dev/null | sort -u || true)
COVERS_IDS=$(grep -iE 'covers' "$SPEC" 2>/dev/null | grep -oE "$ID_RE" | sort -u || true)
TASK_REFS=""; PLAN_REFS=""
$have_tasks && TASK_REFS=$(grep -oE "$ID_RE" "$TASKS" 2>/dev/null | sort -u || true)
$have_plan  && PLAN_REFS=$(grep -oE "$ID_RE" "$PLAN" 2>/dev/null | sort -u || true)

fam() { echo "$1" | grep -E "^$2-" || true; }
SPEC_REQ=$(fam "$SPEC_IDS" REQ);   SPEC_AC=$(fam "$SPEC_IDS" AC)
SPEC_EDGE=$(fam "$SPEC_IDS" EDGE); SPEC_INV=$(fam "$SPEC_IDS" INV)
SPEC_UJ=$(fam "$SPEC_IDS" UJ)

TASK_LINES=""
$have_tasks && TASK_LINES=$(grep -nE '^[[:space:]]*- \[[ xX]\] T[0-9]{3}' "$TASKS" || true)

first_tid() { printf '%s' "$1" | grep -oE 'T[0-9]{3}' | head -1; }

# Extract repo-relative paths from inline-code spans `like/this.ext` only.
# (The old ASCII-tree leaf branch is gone — the plan no longer has a tree, and
# tasks.md cites paths exclusively in backticks.) looks_like_real_path filters
# enum/expression noise so no extension whitelist is needed.
extract_paths() {
  printf '%s\n' "$1" | grep -oE '`[^`]+`' | tr -d '`' \
    | sed 's|^\./||' \
    | grep -vE '^https?:' \
    | while IFS= read -r c; do
        [ -z "$c" ] && continue
        looks_like_real_path "$c" && printf '%s\n' "$c"
      done \
    | sort -u
}

# count non-empty lines in a string; "" -> 0. Early-return avoids grep -c's
# exit-1-on-zero-match emitting a duplicate "0" via the fallback.
cnt() {
  if [ -z "$1" ]; then echo 0; return; fi
  printf '%s\n' "$1" | grep -c '[^[:space:]]' 2>/dev/null || true
}

# ================= SPEC-STAGE CHECKS (always run) =================

# ---------- M1: REQ -> UJ Covers ----------
for id in $SPEC_REQ; do
  echo "$COVERS_IDS" | grep -qx "$id" \
    || add M1 HIGH "spec.md" "$id is not listed in any UJ 'Covers' — requirement has no journey coverage"
done

# ---------- M6: unresolved markers in spec ----------
# Read via process substitution so add() runs in the CURRENT shell (no subshell).
while IFS= read -r h; do
  [ -z "$h" ] && continue
  add M6 HIGH "spec.md:${h%%:*}" "Unresolved clarification marker: ${h#*:}"
done < <(grep -nE '\bQ-[0-9]+\b|\[NEEDS CLARIFICATION' "$SPEC" 2>/dev/null || true)

# ================= PLAN-STAGE CHECKS =================

if $need_plan; then
  # ---------- M5 (plan side): dangling references ----------
  for id in $PLAN_REFS; do
    echo "$SPEC_IDS" | grep -qx "$id" \
      || add M5 HIGH "plan.md" "$id cited in plan.md but not defined in spec.md (dangling reference)"
  done

  # ---------- M9 + M10: machine-readable path manifest ----------
  # The plan emits a ```pathmanifest``` fence: one "<path>  [NEW]|[MOD]" per
  # line, files only, no directories, no tree. We read ONLY that fence — no
  # awk heading-range, no extract_paths, no looks_like_real_path. Every path is
  # checked against the filesystem directly; nothing is silently dropped.
  MANIFEST=$(awk '
    /^[[:space:]]*```pathmanifest/ { inblk=1; next }
    inblk && /^[[:space:]]*```/    { exit }
    inblk                          { print }
  ' "$PLAN")

  if [ -z "$MANIFEST" ]; then
    add M9 HIGH "plan.md" "No \`\`\`pathmanifest\`\`\` block found — plan must emit a machine-readable path manifest (regenerate /order.plan)"
  else
    while IFS= read -r line; do
      case "$line" in ''|'#'*|'<!--'*) continue ;; esac
      path=$(printf '%s\n' "$line" | awk '{print $1}')
      tag=$(printf '%s\n'  "$line" | grep -oE '\[(NEW|MOD)\]' | head -1)
      [ -z "$path" ] && continue
      case "$path" in
        */) add M9 MEDIUM "plan.md" "Manifest lists a directory, not a file: $path"; continue ;;
      esac
      if [ -z "$tag" ]; then
        add M9 MEDIUM "plan.md" "Manifest path lacks [NEW]/[MOD] tag: $path"
      elif [ "$tag" = "[MOD]" ] && [ ! -e "$REPO_ROOT/$path" ]; then
        add M10 HIGH "plan.md" "[MOD] path '$path' does not exist in repo — stale plan, regenerate /order.plan"
      elif [ "$tag" = "[NEW]" ] && [ -e "$REPO_ROOT/$path" ]; then
        add M10 HIGH "plan.md" "[NEW] path '$path' already exists in repo — stale plan, regenerate /order.plan"
      fi
    done < <(printf '%s\n' "$MANIFEST")
  fi
else
  skip M5  "plan.md absent (stage=$STAGE) — plan-side dangling-ref check not applicable yet"
  skip M9  "plan.md absent (stage=$STAGE)"
  skip M10 "plan.md absent (stage=$STAGE)"
fi

# ================= TASKS-STAGE CHECKS =================

if $need_tasks; then
  # ---------- M2: AC -> tasks ----------
  for id in $SPEC_AC; do
    echo "$TASK_REFS" | grep -qx "$id" \
      || add M2 HIGH "tasks.md" "$id is not referenced by any task — acceptance criterion unverified"
  done

  # ---------- M3: EDGE/INV -> tasks ----------
  for id in $SPEC_EDGE $SPEC_INV; do
    echo "$TASK_REFS" | grep -qx "$id" \
      || add M3 HIGH "tasks.md" "$id is not referenced by any task"
  done

  # ---------- M4: [USn] tasks reference >=1 spec ID ----------
  while IFS= read -r ln; do
    [ -z "$ln" ] && continue
    echo "$ln" | grep -qE '\[US[0-9]+\]' || continue
    echo "$ln" | grep -qE "$ID_RE" \
      || add M4 MEDIUM "tasks.md:${ln%%:*}" "Story task $(first_tid "$ln") references no spec ID"
  done < <(printf '%s\n' "$TASK_LINES")

  # ---------- M5 (tasks side): dangling references ----------
  for id in $TASK_REFS; do
    echo "$SPEC_IDS" | grep -qx "$id" \
      || add M5 HIGH "tasks.md" "$id cited in tasks.md but not defined in spec.md (dangling reference)"
  done

  # ---------- M7: task numbering & format ----------
  TNUMS=$(printf '%s\n' "$TASK_LINES" | grep -oE '\] T[0-9]{3}' | grep -oE '[0-9]{3}' || true)
  if [ -n "$TNUMS" ]; then
    DUPES=$(echo "$TNUMS" | sort | uniq -d || true)
    for d in $DUPES; do add M7 MEDIUM "tasks.md" "Duplicate task ID T$d"; done
    SORTED=$(echo "$TNUMS" | sort -n -u)
    FIRST=$(echo "$SORTED" | head -1); LAST=$(echo "$SORTED" | tail -1)
    # Iterate FIRST..LAST without seq (not guaranteed on every system).
    n=$((10#$FIRST))
    last_n=$((10#$LAST))
    while [ "$n" -le "$last_n" ]; do
      printf -v nn '%03d' "$n"
      echo "$SORTED" | grep -qx "$nn" || add M7 MEDIUM "tasks.md" "Gap in task numbering: T$nn missing"
      n=$((n + 1))
    done
  fi
  while IFS= read -r m; do
    [ -z "$m" ] && continue
    add M7 MEDIUM "tasks.md:${m%%:*}" "Task line does not match '- [ ] TNNN [P?] [USn?] description' format"
  done < <(grep -nE '^[[:space:]]*- \[' "$TASKS" 2>/dev/null | grep -E '\bT[0-9]+\b' \
            | grep -vE '^[0-9]+:[[:space:]]*- \[[ xX]\] T[0-9]{3}( \[P\])?( \[US[0-9]+\])? ' || true)

  # ---------- M8: task paths exist in plan manifest ----------
  if $have_plan; then
    # Compare against the manifest's path column only (field 1 per line).
    # MANIFEST is computed in the plan block above; for stage=tasks need_plan
    # is true, so it is in scope (plan block runs before this tasks block).
    MANIFEST_PATHS=$(printf '%s\n' "$MANIFEST" | awk 'NF && $1 !~ /^#/ {print $1}' \
                       | sed 's|^\./||' | sort -u)
    TASK_PATHS=$(extract_paths "$(printf '%s\n' "$TASK_LINES")")
    for p in $TASK_PATHS; do
      printf '%s\n' "$MANIFEST_PATHS" | grep -qxF -- "$p" \
        || add M8 HIGH "tasks.md" "Path '$p' used in tasks.md but not declared in plan.md manifest"
    done
  else
    skip M8 "plan.md absent — cannot cross-check task paths against plan manifest"
  fi

  # ---------- M12: [P] tasks sharing paths (no associative array) ----------
  # Parallel indexed arrays: PM_PATH[i] <-> PM_TID[i]. Linear lookup; path
  # counts per feature are small, so O(n*m) is fine and fully portable.
  PM_PATH=(); PM_TID=()
  _pmap_find() { # $1=path -> echoes owning tid or empty
    local p="$1" i
    for ((i=0; i<${#PM_PATH[@]}; i++)); do
      if [ "${PM_PATH[$i]}" = "$p" ]; then echo "${PM_TID[$i]}"; return; fi
    done
  }
  while IFS= read -r ln; do
    [ -z "$ln" ] && continue
    echo "$ln" | grep -qE '\[[ xX]\] T[0-9]{3} \[P\]' || continue
    tid=$(first_tid "$ln")
    for p in $(extract_paths "$ln"); do
      owner_tid=$(_pmap_find "$p")
      if [ -n "$owner_tid" ] && [ "$owner_tid" != "$tid" ]; then
        add M12 MEDIUM "tasks.md" "[P] tasks $owner_tid and $tid both touch '$p' — parallel marker invalid"
      elif [ -z "$owner_tid" ]; then
        PM_PATH+=("$p"); PM_TID+=("$tid")
      fi
    done
  done < <(printf '%s\n' "$TASK_LINES")

  # ---------- M14: [USn] <-> UJ-00n mapping ----------
  US_LABELS=$(grep -oE '\[US[0-9]+\]' "$TASKS" 2>/dev/null | tr -d '[]' | sort -u || true)
  for us in $US_LABELS; do
    n=${us#US}
    printf -v uj 'UJ-%03d' "$((10#$n))"
    echo "$SPEC_UJ" | grep -qx "$uj" \
      || add M14 HIGH "tasks.md" "Label [$us] has no matching $uj in spec.md"
  done
else
  skip M2  "tasks.md absent (stage=$STAGE) — AC-to-task coverage not applicable yet"
  skip M3  "tasks.md absent (stage=$STAGE)"
  skip M4  "tasks.md absent (stage=$STAGE)"
  skip M7  "tasks.md absent (stage=$STAGE)"
  skip M8  "tasks.md absent (stage=$STAGE)"
  skip M12 "tasks.md absent (stage=$STAGE)"
  skip M14 "tasks.md absent (stage=$STAGE)"
  # M5 tasks-side folded into the above; plan-side handled in plan block.
fi

# ---------- M11: timestamp drift (only between artifacts that exist) ----------
MT_SPEC=$(mtime "$SPEC")
if $have_plan; then
  MT_PLAN=$(mtime "$PLAN")
  [ "$MT_SPEC" -gt "$MT_PLAN" ] \
    && add M11 MEDIUM "spec.md/plan.md" "spec.md modified after plan.md — plan may be stale (verify semantically, regenerate if needed)"
  if $have_tasks; then
    MT_TASKS=$(mtime "$TASKS")
    [ "$MT_PLAN" -gt "$MT_TASKS" ] \
      && add M11 MEDIUM "plan.md/tasks.md" "plan.md modified after tasks.md — tasks may be stale (regenerate /order.tasks)"
  fi
else
  skip M11 "plan.md absent (stage=$STAGE) — no drift to measure"
fi

# ---------- M13: placeholder residue (only on present artifacts) ----------
PLACEHOLDER_FILES=("$SPEC")
$have_plan  && PLACEHOLDER_FILES+=("$PLAN")
$have_tasks && PLACEHOLDER_FILES+=("$TASKS")
for f in "${PLACEHOLDER_FILES[@]}"; do
  while IFS= read -r h; do
    [ -z "$h" ] && continue
    sev=LOW
    echo "$h" | grep -qE '\[path/to/|<placeholder>' && sev=MEDIUM
    add M13 "$sev" "$(basename "$f"):${h%%:*}" "Placeholder residue: $(echo "${h#*:}" | sed 's/^[[:space:]]*//' | cut -c1-80)"
  done < <(grep -nE 'TODO|TKTK|\?\?\?|<placeholder>|\[path/to/' "$f" 2>/dev/null || true)
done

# ---------- coverage map (only meaningful when tasks exist) ----------
COV_JSON=""
if $have_tasks; then
  for id in $SPEC_REQ $SPEC_AC $SPEC_EDGE $SPEC_INV; do
    tlist=""
    while IFS= read -r ln; do
      [ -z "$ln" ] && continue
      echo "$ln" | grep -qF -- "$id" || continue
      tid=$(first_tid "$ln")
      tlist="${tlist:+$tlist,}\"$tid\""
    done < <(printf '%s\n' "$TASK_LINES")
    status="covered"; [ -z "$tlist" ] && status="uncovered"
    COV_JSON="${COV_JSON:+$COV_JSON,}{\"id\":\"$id\",\"tasks\":[$tlist],\"status\":\"$status\"}"
  done
fi

# ---------- summary ----------
TOTAL=${#F_ID[@]}; NC=0; NH=0; NM=0; NL=0
for ((i=0; i<TOTAL; i++)); do
  case "${F_SEV[$i]}" in
    CRITICAL) NC=$((NC+1)) ;; HIGH) NH=$((NH+1)) ;;
    MEDIUM)   NM=$((NM+1)) ;; LOW)  NL=$((NL+1)) ;;
  esac
done
NSKIP=${#SK_CHECK[@]}

TASK_COUNT=$(cnt "$TASK_LINES")

# ---- compute the exit code up front so it can be embedded in the JSON ----
EXIT_CODE=0
if [ $((NC + NH)) -gt 0 ]; then EXIT_CODE=1
elif [ "$NSKIP" -gt 0 ];   then EXIT_CODE=3
fi

# ---- precomputed verdict floor (the gate copies this; it does NOT recompute) ----
# This removes the one decision a weak LLM has historically rationalised away:
# "exit 1 but the findings feel like false positives, so PASS". The floor is a
# deterministic fact derived from CRITICAL/HIGH counts, not a judgement.
#   pass_allowed=false  -> the gate's verdict MUST NOT be PASS (max ROUTING).
#   block_required=true -> a CRITICAL exists -> verdict MUST be BLOCK.
# exit 3 (downstream absent) is clean partial scope: PASS remains allowed.
PASS_ALLOWED=true
BLOCK_REQUIRED=false
VERDICT_FLOOR=PASS_ALLOWED
if [ "$NC" -gt 0 ]; then
  PASS_ALLOWED=false; BLOCK_REQUIRED=true; VERDICT_FLOOR=BLOCK
elif [ "$NH" -gt 0 ]; then
  PASS_ALLOWED=false; VERDICT_FLOOR=ROUTING_REQUIRED
fi

# ---------- output ----------
if $JSON; then
  FJ=""
  for ((i=0; i<TOTAL; i++)); do
    FJ="${FJ:+$FJ,}{\"id\":\"${F_ID[$i]}\",\"check\":\"${F_CHECK[$i]}\",\"severity\":\"${F_SEV[$i]}\",\"location\":\"$(esc "${F_LOC[$i]}")\",\"message\":\"$(esc "${F_MSG[$i]}")\"}"
  done
  SJ=""
  for ((i=0; i<NSKIP; i++)); do
    SJ="${SJ:+$SJ,}{\"check\":\"${SK_CHECK[$i]}\",\"reason\":\"$(esc "${SK_REASON[$i]}")\"}"
  done
  printf '{"stage":"%s","scope":{"spec":true,"plan":%s,"tasks":%s},' \
    "$STAGE" "$($have_plan && echo true || echo false)" "$($have_tasks && echo true || echo false)"
  printf '"summary":{"total":%d,"critical":%d,"high":%d,"medium":%d,"low":%d,"skipped":%d,"exit_code":%d,"pass_allowed":%s,"block_required":%s,"verdict_floor":"%s"},' \
    "$TOTAL" "$NC" "$NH" "$NM" "$NL" "$NSKIP" "$EXIT_CODE" \
    "$PASS_ALLOWED" "$BLOCK_REQUIRED" "$VERDICT_FLOOR"
  printf '"inventory":{"req":%d,"ac":%d,"edge":%d,"inv":%d,"uj":%d,"tasks":%d},' \
    "$(cnt "$SPEC_REQ")" "$(cnt "$SPEC_AC")" "$(cnt "$SPEC_EDGE")" "$(cnt "$SPEC_INV")" \
    "$(cnt "$SPEC_UJ")" "$TASK_COUNT"
  printf '"coverage":[%s],"skipped":[%s],"findings":[%s]}\n' "$COV_JSON" "$SJ" "$FJ"
else
  echo "=== validate-traceability: $FEATURE_DIR (stage=$STAGE) ==="
  echo "Scope: spec=true plan=$($have_plan && echo true || echo false) tasks=$($have_tasks && echo true || echo false)"
  echo "Inventory: REQ=$(cnt "$SPEC_REQ") AC=$(cnt "$SPEC_AC") EDGE=$(cnt "$SPEC_EDGE") INV=$(cnt "$SPEC_INV") UJ=$(cnt "$SPEC_UJ") tasks=$TASK_COUNT"
  if [ "$NSKIP" -gt 0 ]; then
    echo "Skipped checks (expected-absent artifacts): $NSKIP"
    for ((i=0; i<NSKIP; i++)); do printf '  - %s: %s\n' "${SK_CHECK[$i]}" "${SK_REASON[$i]}"; done
  fi
  if [ "$TOTAL" -eq 0 ]; then
    echo "RESULT: CLEAN — no mechanical findings."
  else
    echo "Findings: $TOTAL (CRITICAL=$NC HIGH=$NH MEDIUM=$NM LOW=$NL)"
    for ((i=0; i<TOTAL; i++)); do
      printf '[%s] %s (%s): %s\n' "${F_SEV[$i]}" "${F_ID[$i]}" "${F_LOC[$i]}" "${F_MSG[$i]}"
    done
  fi
fi

[ $((NC + NH)) -gt 0 ] && exit 1
[ "$NSKIP" -gt 0 ]     && exit 3   # clean, but partial scope (expected-absent downstream)
exit "$EXIT_CODE"