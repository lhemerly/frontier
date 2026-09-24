---
name: frontier-appsec
description: Perform bounded repository security assurance investigations for Frontier.
---

# Frontier AppSec investigation

Frontier supplies the assessment scope, prohibited states, fixed criteria and
validators. Investigate only the supplied repository and local test environment.

## Method

1. Inspect the application and its existing tests before changing files.
2. Identify plausible paths from the permitted starting state to a defined
   prohibited state. State falsifiable hypotheses and prioritize a testable one.
3. Reproduce the behavior on the unmodified target. Save the exact command,
   exit code and observed outcome in a JSON evidence artifact. Do not treat a
   scanner alert or narrative as proof.
4. If the behavior reproduces, preserve a focused test, make the smallest
   reasonable fix, then rerun the same security reproduction and relevant
   pre-existing tests.
5. Save post-patch and regression evidence using the JSON contract in the
   Frontier README. Reference artifact paths in findings; describe failed and
   inconclusive experiments accurately.

Do not claim that a vulnerability is confirmed, fixed, or closed unless the
corresponding evidence was captured. Do not broaden scope, access external
systems, or make unrelated changes.
