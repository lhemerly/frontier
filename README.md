# Frontier

Frontier is the repository security assurance profile built on the public
[`mcts-agent`](https://github.com/lhemerly/mcts-agent) package. It contributes a
reviewed AppSec brief, state transition rules, evidence validators and a JSON
result. `mcts-agent` owns research orchestration and checkpointing; Codex is the
execution harness and owns terminal commands, tools, skills and code changes.

## First objective

Given an intentionally vulnerable repository, identify one flaw, capture a
reproducible baseline, remediate it, show the original reproduction no longer
succeeds, and pass relevant existing tests. An assessment may return
`budget_exhausted`, `blocked`, `failed` or `inconclusive`; it must not report
closure when required evidence is missing.

## Install and configure

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Configure the providers using the documented `mcts-agent` settings and install
and authenticate Codex CLI separately. Select Codex as the research executor.
Frontier does not install security tools into Codex. The initial experiment
uses the target language runtime, Git and its test runner.

## Run

```bash
frontier-assess ./path/to/target --max-steps 12
```

The run directory under the target's `.mcts-research/` folder contains the
checkpoint, captured evidence, operation records and `assessment.json`. Resume
with the checkpoint path returned by `mcts-agent`:

```bash
frontier-assess ./path/to/target --resume ./path/to/checkpoint.json --max-steps 8
```

The package API is also available directly:

```python
from agent.research.runner import run_research
from frontier.assessment import Assessment, assessment_brief
from frontier.validators import frontier_validators

assessment = Assessment(
    target="./target",
    scope=["application source", "local test environment"],
    prohibited_states=["ordinary user reads another user's private record"],
)
state, run_dir = run_research(
    "Determine whether the app can reach a prohibited state, prove and remediate it.",
    workspace="./target",
    brief=assessment_brief(assessment),
    validators=frontier_validators(),
    max_steps=12,
)
```

The supplied brief fixes three required checks: baseline reproduction,
post-patch reproduction, and regression tests. Their IDs and validator names
are stable API for the first profile. The evidence contract is a compact JSON
artifact in the workspace, for example:

```json
{
  "schema_version": 1,
  "phase": "baseline",
  "reproduction_id": "idor-cross-user-v1",
  "command": "python -m pytest -q tests/test_authorization.py",
  "exit_code": 1,
  "outcome": "reproduced"
}
```

Use phase `post_patch` and outcome `not_reproduced` for the same security test,
with the same `reproduction_id` and exact command; reference both baseline and
post-patch artifacts for that criterion. Use phase `regression` and outcome
`passed` for the existing tests. Codex should
save these as `evidence/*.json` and reference the workspace-relative paths in
its research findings. The artifact validator checks the captured snapshot's
format and declared outcome. It does not rerun the command or prove the
artifact's provenance. Reports disclose this limitation. A future milestone
should add execution provenance that can be checked independently.

## Repository layout

```text
frontier/
├── frontier/             # assessment, methodology, validators, report and CLI
├── codex/skills/appsec/  # one Frontier investigation skill
├── benchmarks/           # intentionally vulnerable targets and evaluator data
└── tests/
```

The benchmark ground truth must be mounted outside the Codex-visible target
workspace by the future benchmark runner. Keeping ground truth in the source
tree alone does not make it hidden.

## Architectural rule

If Frontier needs generic orchestration behavior unavailable through the public
`mcts-agent` API, improve that abstraction in `mcts-agent`; do not create a
private copy or bypass its research runner.

## Development

```bash
pytest
ruff check .
```

The MVP deliberately does not install or invoke Semgrep, CodeQL, ZAP, Trivy,
fuzzers or formal verification tools. Add tools as measured benchmark
experiments in the Codex execution environment.
