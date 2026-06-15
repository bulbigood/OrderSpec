#!/usr/bin/env bash
# Cascade gate guard. Two checks, in order:
#   1. The upstream ARTIFACT must exist — else HARD STOP (cannot build on nothing).
#   2. If a gate REPORT exists, its verdict must be PASS — else HALT (overridable).
# Deterministic; no LLM judgement.
#
# Usage:
#   check-upstream-gate.sh --report <path> --artifact <path> --upstream-name <name> \
#                          --this <cmd> --build <cmd> --fix <cmd> --recheck <cmd> [--force]
#
# Output: single JSON line on stdout.
# Exit 0 = proceed (status ok|advisory|forced). Exit 2 = HARD STOP (missing artifact).
# Exit 1 = HALT (gate non-PASS).
set -euo pipefail

REPORT="" ARTIFACT="" UPSTREAM_NAME="" THIS="" BUILD="" FIX="" RECHECK="" FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --report)        REPORT="$2";        shift 2 ;;
    --artifact)      ARTIFACT="$2";      shift 2 ;;
    --upstream-name) UPSTREAM_NAME="$2"; shift 2 ;;
    --this)          THIS="$2";          shift 2 ;;
    --build)         BUILD="$2";         shift 2 ;;
    --fix)           FIX="$2";           shift 2 ;;
    --recheck)       RECHECK="$2";       shift 2 ;;
    --force)         FORCE=1;            shift ;;
    *) shift ;;
  esac
done

j() { printf '%s\n' "$1"; }

# ── Check 1: the upstream artifact MUST exist. No --force escape. ──
if [ -z "$ARTIFACT" ] || [ ! -f "$ARTIFACT" ]; then
  j "{\"status\":\"stop\",\"block\":true,\"reason\":\"upstream artifact missing\",\"artifact\":\"$ARTIFACT\",\"upstream_name\":\"$UPSTREAM_NAME\",\"this\":\"$THIS\",\"build\":\"$BUILD\"}"
  exit 2
fi

# ── Check 2: the gate report (optional) ──
if [ ! -f "$REPORT" ]; then
  j "{\"status\":\"advisory\",\"block\":false,\"reason\":\"upstream gate ($RECHECK) was not run\",\"recheck\":\"$RECHECK\"}"
  exit 0
fi

VERDICT="$(grep -m1 '^\*\*Verdict\*\*:' "$REPORT" 2>/dev/null | sed 's/^\*\*Verdict\*\*: *//' || true)"
DATE="$(grep -m1 '^<!-- ' "$REPORT" 2>/dev/null | sed 's/.*· \([0-9-]*\) ·.*/\1/' || echo unknown)"

case "$VERDICT" in
  *PASS*)
    if [ -n "$ARTIFACT" ] && [ "$ARTIFACT" -nt "$REPORT" ]; then
      j "{\"status\":\"advisory\",\"block\":false,\"verdict\":\"PASS\",\"reason\":\"artifact changed after last PASS (stale)\",\"recheck\":\"$RECHECK\"}"
      exit 0
    fi
    j "{\"status\":\"ok\",\"block\":false,\"verdict\":\"PASS\"}"
    exit 0
    ;;
  *ROUTING*|*BLOCK*)
    if [ "$FORCE" -eq 1 ]; then
      j "{\"status\":\"forced\",\"block\":false,\"verdict\":\"$VERDICT\",\"date\":\"$DATE\"}"
      exit 0
    fi
    j "{\"status\":\"halt\",\"block\":true,\"verdict\":\"$VERDICT\",\"date\":\"$DATE\",\"this\":\"$THIS\",\"fix\":\"$FIX\",\"recheck\":\"$RECHECK\"}"
    exit 1
    ;;
  *)
    if [ "$FORCE" -eq 1 ]; then
      j "{\"status\":\"forced\",\"block\":false,\"verdict\":\"unparseable\"}"
      exit 0
    fi
    j "{\"status\":\"halt\",\"block\":true,\"verdict\":\"unparseable\",\"this\":\"$THIS\",\"fix\":\"$FIX\",\"recheck\":\"$RECHECK\"}"
    exit 1
    ;;
esac