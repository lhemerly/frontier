# Declared evidence v2

Each UTF-8 JSON file is snapshotted by mcts-agent. All fields below are required
unless explicitly marked phase-specific. Unknown fields, duplicate JSON keys,
truncated records and incorrect snapshot content hashes are rejected.

| Field | Meaning |
| --- | --- |
| schema_version | Integer `2` |
| assessment_id | ID from the saved Frontier manifest |
| finding_id | One candidate finding, stable across its lifecycle |
| reproduction_id | One unchanged reproduction procedure |
| prohibited_state | An exact member of the saved prohibited states |
| reproduction_sha256 | SHA-256 of the unchanged security test |
| protocol | Currently `pytest_assertion` only |
| phase | `baseline`, `post_patch`, or `regression` |
| command | Exact command used for this phase |
| exit_code | Integer observed process result; booleans are invalid |
| outcome | Semantic result using the protocol table below |
| workspace_revision | Declared target source/test revision, excluding control/evidence files |
| baseline_sha256 | Post-patch and regression: SHA-256 of exact baseline JSON bytes |
| baseline_revision | Post-patch and regression: baseline target revision |
| patch_id | Post-patch and regression: same declared patch identity |
| post_patch_sha256 | Regression: SHA-256 of exact post-patch JSON bytes |

The baseline contains an assertion of the required secure behavior. A failing
security assertion reproduces the prohibited behavior. The same command and test
hash must be preserved when revalidating the patch.

| Phase | Outcome | Exit code | Criterion verdict |
| --- | --- | --- | --- |
| baseline | reproduced | 1 | supported |
| baseline | not_reproduced | 0 | contradicted |
| post_patch | not_reproduced | 0 | supported |
| post_patch | reproduced | 1 | contradicted |
| regression | passed | 0 | supported |
| regression | failed | 1 | contradicted |

All other combinations are inconclusive. An unobserved prohibited state in this
one test does not prove absence of vulnerabilities elsewhere.

Submit baseline evidence for `vulnerability_reproduced`, baseline + post-patch
for `remediation_revalidated`, and all three for `regression_tests_pass`. Include
all three findings in the final StepReport, referencing the captured snapshots.
Each phase must be unambiguous. Later steps may reuse captured evidence IDs.
Duplicate finding or validation criterion IDs are rejected. Closure requires
exactly the three criteria above in both the findings and validation results;
partial steps may still record progress.

Evidence referenced by a finding is an assertion set, not a search space. Every
referenced JSON artifact must be valid for that assertion. Validators parse all
supplied JSON artifacts: a malformed record, another assessment's record, or an
invalid snapshot hash makes the validation inconclusive even when valid evidence
is also supplied. Select only the evidence IDs needed for the assertion.

The final `answer` is a JSON-encoded object with `assessment_id`, `finding_id`,
`reproduction_id`, `patch_id` and `workspace_revision`. Those values must match the
chain. Additional narrative fields are allowed, but cannot change its identity.

Hashes establish that linked JSON records refer to the same captured bytes. They
do not prove that commands ran, that the test observed the claimed security
behavior, or that recorded test/patch/workspace hashes were measured correctly.
Before deriving a report, Frontier reopens the mcts-agent snapshot and checks its
path confinement, `e-<sha256>` ID, content hash, decoded text, and truncation flag
against the cached Evidence object.
Frontier never executes a test inside a validator. Trusted receipts belong in
the upstream execution layer; this version reports `declared_remediated` only.
