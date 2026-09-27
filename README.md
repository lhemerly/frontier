# Frontier

Frontier supplies repository AppSec assessment semantics to
[`mcts-agent`](https://github.com/lhemerly/mcts-agent). It imports the pinned
upstream package: MCTS owns research and checkpoints; a selectable execution
connector owns tool use and changes. Frontier supplies the reviewed brief,
assessment manifest, validation adapters, lifecycle derivation and JSON report.

This is an assurance prototype. It validates **declared artifacts**, not trusted
execution receipts. A coherent completed chain is labeled `declared_remediated`,
with `verification: declared_artifacts`. It does not issue a certificate or claim
that an executor actually ran the recorded commands.

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
frontier-assess ./target --prohibited-state 'ordinary user reads another user record'
```

Configure the planner and System One providers using `mcts-agent` configuration.
Install and authenticate Codex or OpenCode separately. New assessments use
Codex by default; select the OpenCode connector with:

```bash
frontier-assess ./target --connector opencode
frontier-assess ./target --connector opencode --model provider/model
```

The connector invokes OpenCode's non-interactive `opencode run` command in the
target workspace. If `--model` is omitted, OpenCode uses its configured default.
The CLI discovers any registered mcts-agent executor. To add another connector,
implement `BaseExecutorProvider`, expose a registration function in the
`mcts_agent.harnesses` Python entry point group, and register it through
`frontier.connectors.register_connector`.

No live providers are used in normal CI.

Resume without supplying a target or replacement assessment criteria:

```bash
frontier-assess --resume ./target/.mcts-research/RUN_ID/checkpoint.json --max-steps 8
```

Resume uses the connector and model persisted in the checkpoint; connector and
model overrides are rejected. Target, scope, prohibited states, creation time,
assessment ID and a hash of the reviewed brief are persisted before research
begins in `.frontier/ASSESSMENT_ID/manifest.json`. The same manifest is embedded
in the reviewed brief, which `mcts-agent` checkpoints before execution. Resume
compares the saved copies, validates the brief and workspace, and rejects
replacement metadata. Legacy checkpoints without this manifest must start a new
assessment. These consistency checks do not protect against an attacker rewriting
every local control file; trusted execution/storage provenance is future upstream
work.

The run directory contains `assessment.json`, the research checkpoint and
captured evidence. Report generation reopens and verifies every referenced
mcts-agent snapshot against its cached text and SHA-256 before deriving
assurance. A snapshot changed after the runner returns cannot retain support.
Missing or failed evidence remains explicit; budget exhaustion is not a
conclusion that the target is secure.

## Evidence and closure

The reviewed brief includes the complete schema and submission instructions.
See [the evidence contract](docs/evidence-contract.md). Each observation carries:

- Assessment, finding and reproduction identity and the prohibited state tested.
- A hash of the unchanged reproduction test and the declared workspace revision.
- The explicit `pytest_assertion` protocol, command, exit code and semantic outcome.
- Baseline/post-patch content hashes linking phases, plus patch and revision identity.

The baseline must reproduce the issue. The post-patch record cites that exact
baseline snapshot and the same reproduction test and command. Regression evidence
cites that exact successful post-patch record and the same patch/workspace revision.
Validators return all evidence IDs needed to establish each relationship.

Final synthesis must cite all three criteria in **one successful StepReport**.
Its JSON answer must name the matching assessment, finding, reproduction, patch
and patched workspace revision. Ambiguous records, mismatched identities,
truncated/tampered snapshots, contradictory outcomes and changed tests cannot
support closure. Pytest collection errors and other unexpected exit codes are
inconclusive. Exit code 1 has reproduction meaning only under this named protocol;
other reproduction protocols are not yet supported.

Reporting calls `derive_assurance_state()` to replay the current checked chain
through `AssuranceState`. It never assembles a finding from independent historical
latest verdicts. Closure additionally requires `candidate_ready` and the matching
current answer. Failed, blocked, mock and incomplete runs cannot close. The report
includes the lifecycle history, exact evidence chain and provenance limitation.

## Python API

```python
from pathlib import Path
from frontier.cli import run_assessment

state, run_dir, report = run_assessment(
    target=Path('./target'),
    scope=['application source', 'local test environment'],
    prohibited_states=['ordinary user reads another user record'],
    max_steps=12,
    connector='opencode',  # optional; Codex is the default
)
state, run_dir, report = run_assessment(resume=run_dir / 'checkpoint.json', max_steps=8)
```

For direct adapter integration, `prepare_assessment(Assessment(...))` returns a
manifest and reviewed brief. Pass `frontier_validators(manifest)` to the public
`run_research` API. `assessment_result(state)` takes all identity from the saved
manifest and ledger, with no fresh target or assessment-ID arguments.

## Development

```bash
python -m pytest -q
python -m ruff check .
```

CI covers Python 3.10, 3.11 and 3.12. Tests include mixed-finding/patch regressions,
metadata substitution, snapshot corruption, final-answer binding and a synthetic
harness running through the real pinned `mcts-agent` checkpoint/evidence APIs.
The synthetic harness tests integration; it does not measure security performance.

`benchmarks/idor-simple` is a **tier 0 plumbing fixture** with an obvious flaw and
an existing failing test. Ground truth lives outside its target folder. There is
no isolated benchmark controller yet; the layout alone does not hide ground truth
from an executor with broader filesystem access. Benchmark tiers, negative cases,
comparative performance experiments and upstream trusted execution receipts remain
future milestones.

If a generic orchestration capability is missing, improve `mcts-agent`'s public
API. Do not copy its research engine into Frontier.
