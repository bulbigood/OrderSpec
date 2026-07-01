---
orderspec:
  artifact: gate_report
  command: "{generator_cmd}"
  model: "{model_name}"
  generated_at: "{DATE}"
  verdict: "{VERDICT}"
  feature_id: "{FEATURE_ID}"
  feature_directory: "{FEATURE_DIR}"
---

## {gate_title} ({target_doc} — {gate_focus})

**Verdict**: {VERDICT}

### Auto-Fixed (applied automatically — mechanical / meaning-preserving only)
| ID | What was changed | Why meaning-preserving |
|----|------------------|------------------------|
| {auto_fixed_rows} |

### Routing Required (owned by {owner_cmd} — gate did NOT modify content)
{routing_blocks}

### Deferred to Plan (owned by /order.plan or later checks)
| ID | Location | Why deferred |
|----|----------|--------------|
| {deferred_rows} |

### Findings
| ID | Source | Severity | Disposition | Location | Summary |
|----|--------|----------|-------------|----------|---------|
| {findings_rows} |

### Coverage Taxonomy
| Category | § | Status | Disposition |
|----------|---|--------|-------------|
| {coverage_taxonomy_rows} |

### Contradiction Grid
| Pair | Verdict | Reason |
|------|---------|--------|
| {contradiction_grid_rows} |

### Journey Coverage Matrix
| UJ | Priority | Covers REQs | ACs | ACs trace to REQs | Status |
|----|----------|-------------|-----|-------------------|--------|
| {journey_matrix_rows} |

### IF Coverage Matrix
| IF | Kind | Actor | Success | Failure | Covered by ACs | Status |
|----|------|-------|---------|---------|----------------|--------|
| {if_matrix_rows} |

### Metrics
- Inventory: {inventory_summary}
- Findings by severity: CRITICAL={critical_count} · HIGH={high_count} · MEDIUM={medium_count} · LOW={low_count}
- Auto-fixed: {auto_fixed_count} · Routing required: {routing_count} · Deferred to Plan: {deferred_count}
- Script exit code: {exit_code} · verdict floor applied: {floor_status}
- Report file: {report_path}
