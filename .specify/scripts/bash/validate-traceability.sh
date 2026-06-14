#!/usr/bin/env bash
#
# validate-traceability.sh — mechanical cross-artifact validation for speckit.
#
# Deterministic checks only: ID-chain integrity, task numbering/format,
# path consistency, timestamp drift, placeholder residue. Semantic checks
# (role boundaries, contradictions, constitution, E-M-C semantics) are
# intentionally OUT of scope — they belong to /speckit.analyze (LLM).
#
# Usage:
#   validate-traceability.sh [--json] <FEATURE_DIR>
#
# Exit codes:
#   0 — no CRITICAL/HIGH findings (MEDIUM/LOW may be present)
#   1 — at least one CRITICAL or HIGH finding (gate should block)
#   2 — usage error / missing artifacts
#
# Checks (finding ID prefixes):
#   M1  Every REQ appears in >=1 UJ "Covers" list
#   M2  Every AC referenced by >=1 task
#   M3  Every EDGE and INV referenced by >=1 task
#   M4  Every [USn] task references >=1 spec ID
#   M5  No dangling references (IDs cited in plan/tasks must exist in spec)
#   M6  No unresolved Q-NNN / [NEEDS CLARIFICATION] markers in spec
#   M7  Task IDs sequential, no gaps/duplicates; task line format valid
#   M8  Every file path in tasks.md exists in plan.md
#   M9  Every path in plan's Physical Project Structure annotated [NEW]/[MOD]
#   M10 [MOD] paths exist in repo; [NEW] paths do not (stale-plan detection)
#   M11 Timestamp drift: spec newer than plan, or plan newer than tasks
#   M12 [P] tasks must not share file paths
#   M13 Placeholder residue: TODO/TKTK/???/<placeholder>/[path/to/...]
#   M14 [USn] labels map 1:1 to existing UJ-00n in spec

set -uo pipefail

# ---------- args ----------
JSON=false
FEATURE_DIR=""
for arg in "$@"; do
  case "$arg" in
    --json) JSON=true ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) FEATURE_DIR="$arg" ;;
  esac
done
if [ -z "$FEATURE_DIR" ]; then
  echo "Usage: $0 [--json] <FEATURE_DIR>" >&2
  exit 2
fi

SPEC="$FEATURE_DIR/spec.md"
PLAN="$FEATURE_DIR/plan.md"
TASKS="$FEATURE_DIR/tasks.md"
for f in "$SPEC" "$PLAN" "$TASKS"; do
  [ -f "$f" ] || { echo "FATAL: missing artifact: $f" >&2; exit 2; }
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# ---------- findings store ----------
declare -a F_ID=() F_CHECK=() F_SEV=() F_LOC=() F_MSG=()
declare -A COUNT=()
add() { # $1=check $2=severity $3=location $4=message
  local n=${COUNT[$1]:-0}; n=$((n+1)); COUNT[$1]=$n
  F_ID+=("$1-$(printf '%03d' "$n")")
  F_CHECK+=("$1"); F_SEV+=("$2"); F_LOC+=("$3"); F_MSG+=("$4")
}

mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }
esc()   { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

ID_FAMILIES='REQ|NFR|CON|SC|INV|EDGE|UJ|AC|ASM'
ID_RE="\\b($ID_FAMILIES)-[0-9]+\\b"
PATH_RE='[A-Za-z0-9_.~-]+/[A-Za-z0-9_./~-]+|[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,8}'

# ---------- inventories ----------
SPEC_IDS=$(grep -oE "$ID_RE" "$SPEC" 2>/dev/null | sort -u || true)
TASK_REFS=$(grep -oE "$ID_RE" "$TASKS" 2>/dev/null | sort -u || true)
PLAN_REFS=$(grep -oE "$ID_RE" "$PLAN" 2>/dev/null | sort -u || true)
COVERS_IDS=$(grep -iE 'covers' "$SPEC" 2>/dev/null | grep -oE "$ID_RE" | sort -u || true)

fam() { echo "$1" | grep -E "^$2-" || true; }
SPEC_REQ=$(fam "$SPEC_IDS" REQ);   SPEC_AC=$(fam "$SPEC_IDS" AC)
SPEC_EDGE=$(fam "$SPEC_IDS" EDGE); SPEC_INV=$(fam "$SPEC_IDS" INV)
SPEC_UJ=$(fam "$SPEC_IDS" UJ)

# Canonical task lines: "- [ ] TNNN [P?] [USn?] description"
TASK_LINES=$(grep -nE '^[[:space:]]*- \[[ xX]\] T[0-9]{3}' "$TASKS" || true)

first_tid() { printf '%s' "$1" | grep -oE 'T[0-9]{3}' | head -1; }

# Extract path-like tokens from a string (backticked preferred, then bare)
extract_paths() {
  {
    printf '%s\n' "$1" | grep -oE '`[^`]+`' | tr -d '`' || true
    printf '%s\n' "$1" | grep -oE "$PATH_RE" || true
  } | grep -E '/|\.' | grep -vE '^[0-9.]+$' | grep -vE '^https?:' \
    | sed 's|^\./||' | sort -u
}

# ---------- M1: REQ -> UJ Covers ----------
for id in $SPEC_REQ; do
  echo "$COVERS_IDS" | grep -qx "$id" \
    || add M1 HIGH "spec.md" "$id is not listed in any UJ 'Covers' — requirement has no journey coverage"
done

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
if [ -n "$TASK_LINES" ]; then
  while IFS= read -r ln; do
    [ -z "$ln" ] && continue
    echo "$ln" | grep -qE '\[US[0-9]+\]' || continue
    echo "$ln" | grep -qE "$ID_RE" \
      || add M4 MEDIUM "tasks.md:${ln%%:*}" "Story task $(first_tid "$ln") references no spec ID"
  done <<< "$TASK_LINES"
fi

# ---------- M5: dangling references ----------
for id in $TASK_REFS; do
  echo "$SPEC_IDS" | grep -qx "$id" \
    || add M5 HIGH "tasks.md" "$id cited in tasks.md but not defined in spec.md (dangling reference)"
done
for id in $PLAN_REFS; do
  echo "$SPEC_IDS" | grep -qx "$id" \
    || add M5 HIGH "plan.md" "$id cited in plan.md but not defined in spec.md (dangling reference)"
done

# ---------- M6: unresolved markers in spec ----------
M6_HITS=$(grep -nE '\bQ-[0-9]+\b|\[NEEDS CLARIFICATION' "$SPEC" || true)
if [ -n "$M6_HITS" ]; then
  while IFS= read -r h; do
    add M6 HIGH "spec.md:${h%%:*}" "Unresolved clarification marker: ${h#*:}"
  done <<< "$M6_HITS"
fi

# ---------- M7: task numbering & format ----------
TNUMS=$(printf '%s\n' "$TASK_LINES" | grep -oE '\] T[0-9]{3}' | grep -oE '[0-9]{3}' || true)
if [ -n "$TNUMS" ]; then
  DUPES=$(echo "$TNUMS" | sort | uniq -d || true)
  [ -n "$DUPES" ] && for d in $DUPES; do add M7 MEDIUM "tasks.md" "Duplicate task ID T$d"; done
  SORTED=$(echo "$TNUMS" | sort -n -u)
  FIRST=$(echo "$SORTED" | head -1); LAST=$(echo "$SORTED" | tail -1)
  for n in $(seq "$((10#$FIRST))" "$((10#$LAST))"); do
    printf -v nn '%03d' "$n"
    echo "$SORTED" | grep -qx "$nn" || add M7 MEDIUM "tasks.md" "Gap in task numbering: T$nn missing"
  done
fi
MALFORMED=$(grep -nE '^[[:space:]]*- \[' "$TASKS" | grep -E '\bT[0-9]+\b' \
  | grep -vE '^[0-9]+:[[:space:]]*- \[[ xX]\] T[0-9]{3}( \[P\])?( \[US[0-9]+\])? ' || true)
if [ -n "$MALFORMED" ]; then
  while IFS= read -r m; do
    add M7 MEDIUM "tasks.md:${m%%:*}" "Task line does not match '- [ ] TNNN [P?] [USn?] description' format"
  done <<< "$MALFORMED"
fi

# ---------- M8: task paths exist in plan ----------
TASK_PATHS=$(extract_paths "$(printf '%s\n' "$TASK_LINES")")
for p in $TASK_PATHS; do
  grep -qF -- "$p" "$PLAN" \
    || add M8 HIGH "tasks.md" "Path '$p' used in tasks.md but absent from plan.md"
done

# ---------- M9: plan structure paths annotated [NEW]/[MOD] ----------
PLAN_STRUCT=$(awk '/^##+ .*([Pp]hysical|[Pp]roject [Ss]tructure)/{f=1;next} /^##+ /{f=0} f' "$PLAN")
if [ -n "$PLAN_STRUCT" ]; then
  while IFS= read -r ln; do
    [ -z "$ln" ] && continue
    echo "$ln" | grep -qE "$PATH_RE" || continue
    echo "$ln" | grep -qE '\[(NEW|MOD)\]' \
      || add M9 MEDIUM "plan.md" "Structure line lacks [NEW]/[MOD] annotation: $(echo "$ln" | sed 's/^[[:space:]]*//' | cut -c1-80)"
  done <<< "$PLAN_STRUCT"
else
  add M9 LOW "plan.md" "Physical Project Structure section not found — annotation check skipped"
fi

# ---------- M10: [NEW]/[MOD] vs actual repo ----------
ANNOT_LINES=$(grep -E '\[(NEW|MOD)\]' "$PLAN" || true)
if [ -n "$ANNOT_LINES" ]; then
  while IFS= read -r ln; do
    [ -z "$ln" ] && continue
    tag=$(echo "$ln" | grep -oE '\[(NEW|MOD)\]' | head -1)
    for p in $(extract_paths "$ln"); do
      if [ "$tag" = "[MOD]" ] && [ ! -e "$REPO_ROOT/$p" ]; then
        add M10 HIGH "plan.md" "[MOD] path '$p' does not exist in repo — stale plan, regenerate /speckit.plan"
      elif [ "$tag" = "[NEW]" ] && [ -e "$REPO_ROOT/$p" ]; then
        add M10 HIGH "plan.md" "[NEW] path '$p' already exists in repo — stale plan, regenerate /speckit.plan"
      fi
    done
  done <<< "$ANNOT_LINES"
fi

# ---------- M11: timestamp drift ----------
MT_SPEC=$(mtime "$SPEC"); MT_PLAN=$(mtime "$PLAN"); MT_TASKS=$(mtime "$TASKS")
[ "$MT_SPEC" -gt "$MT_PLAN" ] \
  && add M11 MEDIUM "spec.md/plan.md" "spec.md modified after plan.md — plan may be stale (verify semantically, regenerate if needed)"
[ "$MT_PLAN" -gt "$MT_TASKS" ] \
  && add M11 MEDIUM "plan.md/tasks.md" "plan.md modified after tasks.md — tasks may be stale (regenerate /speckit.tasks)"

# ---------- M12: [P] tasks sharing paths ----------
declare -A PMAP=()
if [ -n "$TASK_LINES" ]; then
  while IFS= read -r ln; do
    [ -z "$ln" ] && continue
    echo "$ln" | grep -qE '\[[ xX]\] T[0-9]{3} \[P\]' || continue
    tid=$(first_tid "$ln")
    for p in $(extract_paths "$ln"); do
      if [ -n "${PMAP[$p]:-}" ] && [ "${PMAP[$p]}" != "$tid" ]; then
        add M12 MEDIUM "tasks.md" "[P] tasks ${PMAP[$p]} and $tid both touch '$p' — parallel marker invalid"
      else
        PMAP[$p]="$tid"
      fi
    done
  done <<< "$TASK_LINES"
fi

# ---------- M13: placeholder residue ----------
for f in "$SPEC" "$PLAN" "$TASKS"; do
  HITS=$(grep -nE 'TODO|TKTK|\?\?\?|<placeholder>|\[path/to/' "$f" || true)
  [ -z "$HITS" ] && continue
  while IFS= read -r h; do
    sev=LOW
    echo "$h" | grep -qE '\[path/to/|<placeholder>' && sev=MEDIUM
    add M13 "$sev" "$(basename "$f"):${h%%:*}" "Placeholder residue: $(echo "${h#*:}" | sed 's/^[[:space:]]*//' | cut -c1-80)"
  done <<< "$HITS"
done

# ---------- M14: [USn] <-> UJ-00n mapping ----------
US_LABELS=$(grep -oE '\[US[0-9]+\]' "$TASKS" | tr -d '[]' | sort -u || true)
for us in $US_LABELS; do
  n=${us#US}
  printf -v uj 'UJ-%03d' "$((10#$n))"
  echo "$SPEC_UJ" | grep -qx "$uj" \
    || add M14 HIGH "tasks.md" "Label [$us] has no matching $uj in spec.md"
done

# ---------- coverage map (for report) ----------
COV_JSON=""
for id in $SPEC_REQ $SPEC_AC $SPEC_EDGE $SPEC_INV; do
  tlist=""
  if [ -n "$TASK_LINES" ]; then
    while IFS= read -r ln; do
      [ -z "$ln" ] && continue
      echo "$ln" | grep -qF -- "$id" || continue
      tid=$(first_tid "$ln")
      tlist="${tlist:+$tlist,}\"$tid\""
    done <<< "$TASK_LINES"
  fi
  status="covered"; [ -z "$tlist" ] && status="uncovered"
  COV_JSON="${COV_JSON:+$COV_JSON,}{\"id\":\"$id\",\"tasks\":[$tlist],\"status\":\"$status\"}"
done

# ---------- summary ----------
TOTAL=${#F_ID[@]}; NC=0; NH=0; NM=0; NL=0
for ((i=0; i<TOTAL; i++)); do
  case "${F_SEV[$i]}" in
    CRITICAL) NC=$((NC+1)) ;; HIGH) NH=$((NH+1)) ;;
    MEDIUM)   NM=$((NM+1)) ;; LOW)  NL=$((NL+1)) ;;
  esac
done
cnt() { echo "$1" | grep -c . || true; }

# ---------- output ----------
if $JSON; then
  FJ=""
  for ((i=0; i<TOTAL; i++)); do
    FJ="${FJ:+$FJ,}{\"id\":\"${F_ID[$i]}\",\"check\":\"${F_CHECK[$i]}\",\"severity\":\"${F_SEV[$i]}\",\"location\":\"$(esc "${F_LOC[$i]}")\",\"message\":\"$(esc "${F_MSG[$i]}")\"}"
  done
  printf '{"summary":{"total":%d,"critical":%d,"high":%d,"medium":%d,"low":%d},' "$TOTAL" "$NC" "$NH" "$NM" "$NL"
  printf '"inventory":{"req":%d,"ac":%d,"edge":%d,"inv":%d,"uj":%d,"tasks":%d},' \
    "$(cnt "$SPEC_REQ")" "$(cnt "$SPEC_AC")" "$(cnt "$SPEC_EDGE")" "$(cnt "$SPEC_INV")" \
    "$(cnt "$SPEC_UJ")" "$(printf '%s\n' "$TASK_LINES" | grep -c . || true)"
  printf '"coverage":[%s],"findings":[%s]}\n' "$COV_JSON" "$FJ"
else
  echo "=== validate-traceability: $FEATURE_DIR ==="
  echo "Inventory: REQ=$(cnt "$SPEC_REQ") AC=$(cnt "$SPEC_AC") EDGE=$(cnt "$SPEC_EDGE") INV=$(cnt "$SPEC_INV") UJ=$(cnt "$SPEC_UJ") tasks=$(printf '%s\n' "$TASK_LINES" | grep -c . || true)"
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
exit 0