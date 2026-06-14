# [PROJECT_NAME] Constitution
<!--
  Supreme governance document. Two distinct jobs:
    1. Core Principles      — human-facing rules the project must uphold.
    2. Capability Grants    — machine-readable permissions that GATES EXECUTE LITERALLY.
  LAW: any capability not explicitly granted below is DENIED. Gates degrade to
  static inspection on anything unstated. Silence is never permission.
  Edit only via `/order.constitution`. Keep heading levels intact.
-->

## Core Principles

### [PRINCIPLE_1_NAME]
<!-- Example: I. Contract Stability -->
[PRINCIPLE_1_RULE]
<!--
  State as MUST / SHOULD, declarative and testable.
  Example: "spec.md MUST remain the source of truth; behavior changes start there, not in code."
  Add a one-line rationale if the rule is not self-evident.
  Every SHOULD carries a note on when it may be skipped.
-->

### [PRINCIPLE_2_NAME]
[PRINCIPLE_2_RULE]

### [PRINCIPLE_3_NAME]
[PRINCIPLE_3_RULE]

<!-- Add or remove principle blocks freely; the count above is a default, not a quota. -->

## Capability Grants
<!--
  THIS SECTION IS READ BY GATES. Write flat, unambiguous yes/no statements with
  explicit commands. A gate must be able to scan this and answer "am I allowed
  to do X?" with a literal yes/no — no prose it could misread.
  Anything omitted here is DENIED.
-->

### Test execution
[GRANT_TESTS]
<!--
  Granted example:  "ALLOWED. Gates MAY run tests as evidence. run: [TEST_COMMAND]"
  Denied  example:  "DENIED. Gates MUST NOT run tests; rely on static inspection."
-->

### Build / compile / lint as evidence
[GRANT_BUILD]
<!-- Example: "ALLOWED. run: [BUILD_COMMAND]"  |  "DENIED." -->

### Network access during a gate
[GRANT_NETWORK]
<!-- Example: "DENIED."  |  "ALLOWED for: [explicit scope]" -->

### Mechanical auto-fixes by gates
[GRANT_AUTOFIX]
<!--
  Whether gates may APPLY reversible normalizations (glossary terms, stale-ID
  references) vs. only ROUTE them. Example:
  "ALLOWED for glossary-term normalization and unambiguous stale-ID references only;
   anything touching meaning or scope MUST be routed, never applied."
-->

## [SECTION_NAME]
<!--
  Optional extra sections: security requirements, performance standards,
  tech-stack constraints, compliance. Add as needed; keep them principle-like
  (testable, MUST/SHOULD). Remove this block if unused.
-->
[SECTION_CONTENT]

## Governance

[GOVERNANCE_RULES]
<!--
  Example:
  - This constitution supersedes all other practices; on conflict, it wins.
  - Amendments are made only via `/order.constitution`, which versions the document
    and ROUTES conflicting artifacts to their owning commands (it does not rewrite them).
  - Version policy (semantic):
      MAJOR — a principle or capability grant is removed, reversed, or made stricter.
      MINOR — a principle or grant is added or materially expanded.
      PATCH — wording / clarification, no change to what is required or permitted.
  - Default-deny on capabilities is non-negotiable: unstated ⇒ denied.
-->

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
<!-- Dates ISO YYYY-MM-DD. Unknown values → [UNRESOLVED: <field> — <why>]. -->