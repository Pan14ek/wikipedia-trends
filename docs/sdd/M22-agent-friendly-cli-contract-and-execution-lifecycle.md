# M22 — Agent-Friendly CLI Contract and Execution Lifecycle

**Spec ID:** WT-M22  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Implemented — awaiting WT-M18 revalidation
**Depends on:** WT-M21  
**Revalidation after completion:** WT-M18 agent evaluation

## SDD rule

This document is the source of truth for the agent-facing CLI contract and execution lifecycle.

The implementation agent must:

- preserve WT-M01–WT-M21 analytical behavior unless this specification explicitly changes the CLI execution contract;
- optimize the CLI for reliable use by fast/inexpensive tool-capable models;
- make execution semantics explicit rather than requiring the agent to infer them;
- keep stdout machine-readable on successful runs;
- make optional artifacts unambiguous;
- return every generated chart path, not only one representative path;
- document the complete request-to-response lifecycle;
- keep Python responsible for resolution, collection, calculations, comparison, and report generation;
- avoid adding new analytics capabilities or external data sources.

WT-M22 intentionally includes both documentation and small runtime hardening of the CLI contract.

---

# 1. Context

WT-M21 successfully changed the skill documentation into:

```text
SKILL.md
    ↓
workflow routing
    ↓
references/workflows/*
    ↓
CLI execution
    ↓
artifact validation
    ↓
interpretation
```

The remaining weak point for inexpensive models is the execution boundary.

The current `SKILL.md` tells the agent to run:

```bash
python scripts/analyze.py --config <config.json> --output-dir <output-dir>
```

but the agent still has to infer several important details:

- where the skill root is;
- where to create the config file;
- what must happen before the command is run;
- how to interpret process exit codes;
- what stdout contains;
- which artifact paths are authoritative;
- what to do when an artifact is disabled;
- what to do after exit code `0`;
- how to distinguish CLI success from a semantically valid comparison;
- how to recover from configuration errors without inventing user intent.

The current CLI also has two machine-readability problems:

```python
str(None)
```

serializes a disabled artifact as the string:

```json
"None"
```

rather than JSON `null`.

The current success payload also exposes:

```json
"chart": "..."
```

as a singular value, while the chart pipeline can generate multiple PNG files for comparisons with more than six language editions.

WT-M22 makes this boundary explicit and stable.

---

# 2. Goal

Make the CLI usable as a simple state machine by a weaker agent.

The target lifecycle is:

```text
USER REQUEST
    ↓
SKILL.md
    ↓
select relevant workflow references
    ↓
resolve required user inputs
    ↓
build AnalysisConfig
    ↓
write config.json
    ↓
run CLI
    ↓
inspect exit code
    ↓
parse CLI machine-readable result
    ↓
inspect analysis.json when enabled
    ↓
inspect resolution / metrics / warnings / quality / comparison
    ↓
validate requested artifacts
    ↓
USER RESPONSE
```

A model should not need to reverse-engineer Python code to understand this sequence.

---

# 3. In scope

WT-M22 includes:

- new `references/cli.md`;
- complete documented execution lifecycle;
- skill-root and working-directory guidance;
- config-file execution guidance;
- stable success payload;
- structured optional-artifact semantics;
- plural `charts`;
- exact exit-code semantics;
- agent recovery rules;
- explicit post-success validation steps;
- stdout/stderr responsibilities;
- CLI contract tests;
- multi-chart regression coverage;
- updates to `SKILL.md`;
- minimal updates to workflow references that need to point to the CLI contract;
- minimal pipeline return-contract refactoring if necessary to expose every actual generated artifact.

---

# 4. Out of scope

Do not add:

- new analytics metrics;
- new resolver behavior;
- new comparison rules;
- new report formats;
- interactive CLI prompts;
- shell-specific wrappers;
- external web/search providers;
- automatic agent reasoning inside the CLI;
- a second analysis command;
- a daemon/server mode;
- a general job queue;
- hidden fallback calculations.

Do not redesign `AnalysisConfig` or `AnalysisReport` unless a change is strictly required by this CLI contract.

---

# 5. Documentation architecture after WT-M22

The intended structure is:

```text
SKILL.md
│
├── orchestration / routing
│
references/
├── cli.md
├── input-schema.md
├── output-schema.md
├── methodology.md
│
└── workflows/
    ├── article-analysis.md
    ├── topic-analysis.md
    ├── multi-language-comparison.md
    ├── period-selection.md
    ├── criteria-and-thresholds.md
    ├── follow-up-analysis.md
    ├── proxy-resolution.md
    └── artifact-validation.md
```

Responsibilities:

```text
SKILL.md
→ what should the agent do next?

references/workflows/*
→ how should the agent handle this request type?

references/cli.md
→ how should the agent execute the analysis engine?

references/input-schema.md
→ what configuration can the agent send?

references/output-schema.md
→ what report can the agent read?

references/methodology.md
→ what do the results mean?
```

---

# 6. New `references/cli.md`

Create:

```text
references/cli.md
```

Recommended structure:

```text
# CLI Execution Reference

## Purpose
## Execution Lifecycle
## Step 0 — Locate the Skill Root
## Step 1 — Build the Configuration
## Step 2 — Write the Configuration File
## Step 3 — Choose the Python Interpreter
## Step 4 — Run the CLI
## Step 5 — Check the Exit Code
## Step 6 — Parse CLI Output
## Step 7 — Inspect the Report
## Step 8 — Validate Artifacts
## Step 9 — Respond to the User
## CLI Arguments
## Success Payload
## Error Behavior
## Recovery Rules
## Examples
## Prohibited Shortcuts
```

The exact headings may vary slightly, but the complete lifecycle must remain explicit.

---

# 7. Execution lifecycle

The CLI reference must contain a prominent lifecycle diagram.

Required conceptual flow:

```text
USER REQUEST
     │
     ▼
1. Route request with SKILL.md
     │
     ▼
2. Load only relevant workflow references
     │
     ▼
3. Resolve missing required inputs
     │
     ▼
4. Build config using input-schema.md
     │
     ▼
5. Write config JSON to a writable path
     │
     ▼
6. Run scripts/analyze.py
     │
     ├── exit 2
     │      ↓
     │   configuration/usage failure
     │      ↓
     │   fix only if request + schema determine the fix
     │   otherwise ask user
     │
     ├── exit 1
     │      ↓
     │   analysis failure
     │      ↓
     │   do not reconstruct metrics manually
     │
     └── exit 0
            ↓
        parse stdout JSON
            ↓
        inspect analysis.json if generated
            ↓
        inspect semantic/result statuses
            ↓
        validate requested artifacts
            ↓
        answer user
```

The documentation must explicitly state:

> Exit code `0` means the pipeline completed. It does not by itself mean that every requested language resolved, every criterion was evaluable, or a direct comparison is valid.

After exit code `0`, the agent must still inspect the report status fields when JSON is enabled.

---

# 8. Step 0 — Locate the skill root

Define the skill root as the directory containing:

```text
SKILL.md
scripts/analyze.py
references/
src/
```

The agent must not depend on an absolute installation path such as `/mnt/...`.

Preferred execution forms:

```bash
python <skill-root>/scripts/analyze.py \
  --config <config-path> \
  --output-dir <output-dir>
```

or, after changing to the skill root:

```bash
python scripts/analyze.py \
  --config <config-path> \
  --output-dir <output-dir>
```

The config and output directories do not need to live inside the skill source directory.

Prefer a writable working location for generated request configs and outputs.

Do not modify files under `examples/` merely to execute a user request.

---

# 9. Step 1 — Build the configuration

Before the CLI is invoked:

1. follow `SKILL.md` preflight;
2. load relevant workflows;
3. read `references/input-schema.md`;
4. construct a valid JSON configuration;
5. do not add unknown fields;
6. do not invent values that require clarification.

The CLI accepts a configuration file, not inline JSON.

The agent must not attempt to pass the user request directly as a CLI argument.

---

# 10. Step 2 — Write the configuration file

Write the configuration as UTF-8 JSON.

Requirements:

- valid JSON;
- no Markdown code fences;
- no comments;
- no YAML;
- one top-level `AnalysisConfig` object.

The filename is not semantically meaningful.

Example:

```text
/tmp/wikipedia-trends-request.json
```

is only illustrative. Documentation must not require `/tmp` or any platform-specific path.

The agent must use the actual file path it created in `--config`.

For a follow-up, derive the new configuration from the previous:

```text
analysis.json.input
```

according to `follow-up-analysis.md`.

---

# 11. Step 3 — Choose the Python interpreter

The skill requires Python 3.12+ according to project documentation.

Interpreter policy:

1. use the environment already configured for the skill when available;
2. if the repository virtual environment exists, its Python is preferred because dependencies are more likely to be installed;
3. otherwise use the available compatible `python` executable.

On Unix-like skill installations, the common repository interpreter is:

```text
<skill-root>/.venv/bin/python
```

Do not hard-code that path as the only supported runtime.

The skill should keep a concise fallback in `SKILL.md`, while full guidance lives in `references/cli.md`.

---

# 12. Step 4 — Run the CLI

Canonical command:

```bash
python <skill-root>/scripts/analyze.py \
  --config <config-path> \
  --output-dir <output-dir>
```

Agent reliability rule:

> Always pass `--output-dir` explicitly.

Although the CLI has a default, explicit output roots make runs easier to audit and prevent a weak agent from guessing where artifacts were written.

The agent may reuse an output root across runs, but it must use the artifact paths returned by the current run rather than scanning directories for the “latest” file.

---

# 13. CLI arguments

Document exactly:

## `--config`

Required.

Meaning:

```text
path to UTF-8 JSON matching AnalysisConfig
```

## `--output-dir`

Agent-required even if CLI technically has a default.

Meaning:

```text
root directory for generated artifacts
```

## `--help`

Safe informational command:

```bash
python <skill-root>/scripts/analyze.py --help
```

It does not run an analysis.

No other CLI flags should be documented unless they exist.

---

# 14. Exit-code contract

Document:

| Exit code | Meaning | Required agent behavior |
|---|---|---|
| `0` | Pipeline completed | Parse success stdout, then inspect result/report statuses and validate artifacts |
| `1` | Analysis/runtime failure | Do not invent results; inspect stderr and report or resolve the concrete execution problem |
| `2` | CLI/configuration failure | Correct only what can be determined from the request and input schema; otherwise ask the user |

## Important distinction

Exit `0` is process success, not necessarily analytical success.

Examples of conditions that may still exist in a completed report:

```text
requires_clarification
unresolved language mapping
comparison.comparable = false
criterion = not_evaluable
quality warning/fail
requested period truncated to available period
```

The agent must preserve those statuses.

---

# 15. Stable success payload

Change CLI success stdout to one JSON object.

Target contract:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": "output/.../analysis.json",
  "charts": [
    "output/.../trend.png"
  ],
  "pdf": "output/.../report.pdf"
}
```

Optional outputs use JSON-native absence:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": null,
  "charts": [],
  "pdf": null
}
```

Mandatory properties:

```text
cli_schema_version
status
analysis_json
charts
pdf
```

Rules:

- `status` is exactly `"success"` on exit `0`;
- `analysis_json` is string or `null`;
- `charts` is always an array of zero or more strings;
- `pdf` is string or `null`;
- never serialize a missing value as `"None"`;
- stdout must contain the final machine-readable payload rather than explanatory prose.

---

# 16. Multi-chart correctness

The current chart subsystem may generate:

```text
1 chart
```

for up to six languages, but:

```text
multiple per-language charts
```

for seven through twenty languages.

The CLI must expose every generated chart path.

Forbidden contract:

```json
{
  "chart": "one-path-only.png"
}
```

Required contract:

```json
{
  "charts": [
    "trend-en.png",
    "trend-pl.png",
    "trend-cs.png",
    "trend-uk.png"
  ]
}
```

Do not expose a base chart path that was never actually created.

---

# 17. Internal run-result contract

Refactor the internal pipeline return value if required so the CLI can know the exact set of generated artifacts.

Preferred conceptual shape:

```python
AnalysisRunResult(
    analysis_json: Path | None,
    charts: list[Path],
    pdf: Path | None,
)
```

The exact type/class name is not mandatory.

Required properties:

- typed;
- no sentinel strings;
- every actual user-visible chart is represented;
- disabled artifacts are represented explicitly;
- CLI does not guess chart filenames after the pipeline completes.

If the existing tuple can be safely evolved without introducing ambiguity, an alternate implementation is acceptable. Correctness of artifact enumeration is mandatory.

---

# 18. Error output

Configuration and analysis errors must remain distinguishable by exit code.

Prefer structured JSON on stderr for errors handled by the application.

Recommended configuration error:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "error",
  "error_type": "configuration_error",
  "message": "..."
}
```

with exit code:

```text
2
```

Recommended analysis error:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "error",
  "error_type": "analysis_error",
  "message": "..."
}
```

with exit code:

```text
1
```

If argparse-level syntax errors remain conventional text on stderr, document that they still use non-zero exit status and do not produce a success payload.

Never emit a success-shaped stdout object after failure.

---

# 19. Stdout/stderr responsibilities

For normal analysis execution:

```text
stdout
→ final machine-readable success payload only

stderr
→ configuration errors, analysis errors, diagnostics/logging
```

The agent must not parse arbitrary stderr text as metrics.

The agent must not treat logging output as analysis output.

---

# 20. Step 6 — Parse CLI output

After exit `0`:

1. parse stdout as JSON;
2. verify:
   ```text
   cli_schema_version == "1.0.0"
   status == "success"
   ```
3. read `analysis_json`, `charts`, and `pdf`;
4. never convert `null` into a path;
5. never invent an artifact path not listed by the current run.

The agent must not search the output directory and choose files by modification time when valid CLI paths are available.

---

# 21. Step 7 — Inspect `analysis.json`

When:

```text
analysis_json != null
```

follow `references/output-schema.md`.

At minimum inspect the fields relevant to the request:

```text
schema_version
input
resolution
requested_period
period
languages
comparison
criteria
quality
warnings
artifacts
```

The agent does not need to narrate every field.

It must inspect enough to avoid claiming:

- a valid direct comparison when `comparison.comparable = false`;
- a resolved topic when resolution requires clarification;
- a threshold pass/fail when status is `not_evaluable`;
- full requested coverage when the available period was truncated;
- a proxy as a direct equivalent.

---

# 22. JSON-disabled runs

When:

```text
analysis_json == null
```

the agent must not assume a report file exists.

Rules:

- validate only configured/generated artifacts;
- do not invent metrics;
- do not infer a report path;
- do not reconstruct `analysis.json`;
- if the user expects detailed numeric interpretation and has not explicitly forbidden JSON, the workflow may keep JSON enabled as the audit artifact;
- if the user explicitly disabled JSON, respect that choice.

CLI stdout JSON is an execution protocol, not a generated report artifact, so it does not violate `output.json = false`.

---

# 23. Step 8 — Validate artifacts

After parsing stdout, follow:

```text
references/workflows/artifact-validation.md
```

Validation source hierarchy:

```text
1. current CLI success payload
2. analysis.json.artifacts when report JSON exists
3. filesystem validation
```

Do not predict artifact paths from slug rules.

For each enabled artifact:

```text
JSON
→ path exists and parses

charts
→ every listed path exists and is a valid generated PNG according to current validation rules

PDF
→ path exists and is readable
```

The artifact workflow remains authoritative for detailed validation.

---

# 24. Path rules

Do not guess paths.

Use only paths returned by the current run or recorded in its report.

If a returned path is relative, interpret it relative to the working directory used for the CLI process.

Documentation should recommend absolute config/output paths where the agent runtime can easily provide them, but must not require a platform-specific path scheme.

Never reuse an older run's paths merely because filenames look similar.

---

# 25. Recovery rules

The cheap-model path must be deterministic.

## Exit 2 — configuration failure

The agent may correct and rerun when the correction is mechanically determined by:

```text
user request
+
input-schema.md
+
error message
```

Examples:

```text
unknown field
invalid date shape
duplicate languages
missing required comparison_period for growth_pct
```

If correction requires choosing user intent, stop and ask.

Do not invent:

```text
source language
topic meaning
threshold
baseline
proxy approval
```

## Exit 1 — analysis failure

Do not calculate fallback results manually.

Do not switch to direct Wikimedia API calls.

Do not enter an unbounded retry loop.

A retry is allowed only when the failure is clearly transient and retrying cannot alter analytical meaning. Existing HTTP clients already own their configured network retry behavior, so agent-level retries should be rare.

If failure persists, report it.

## Exit 0 — completed run with unresolved result

Do not rerun merely to force a resolved result.

Use the structured report state.

If clarification is required, ask the user.

---

# 26. Prohibited shortcuts

`references/cli.md` must explicitly prohibit:

- calling Wikimedia directly instead of the project CLI;
- copying numbers from terminal logs instead of `analysis.json`;
- manually calculating metrics;
- inventing canonical titles;
- predicting output filenames;
- choosing the newest file in an output directory instead of using current-run paths;
- treating `"None"` or another sentinel string as a valid path;
- treating exit `0` as proof that the comparison is valid;
- silently changing config fields after a failed validation;
- infinite/automatic retry loops;
- editing generated `analysis.json`.

---

# 27. CLI examples

`references/cli.md` should include a small number of execution examples.

Do not replicate the complete input schema.

## Example A — standard analysis

```bash
python <skill-root>/scripts/analyze.py \
  --config <workspace>/analysis-config.json \
  --output-dir <workspace>/wikipedia-trends-output
```

Then:

```text
check exit code
→ parse stdout JSON
→ open analysis_json
→ validate charts/PDF
```

## Example B — JSON-only output

Expected success shape:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": ".../analysis.json",
  "charts": [],
  "pdf": null
}
```

## Example C — PDF-only output

Expected shape:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": null,
  "charts": [],
  "pdf": ".../report.pdf"
}
```

If a chart is generated internally only to build the PDF but was not requested as a chart artifact, it must not appear in `charts`.

## Example D — multi-chart output

For more than six languages:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": ".../analysis.json",
  "charts": [
    "...-en.png",
    "...-pl.png",
    "...-cs.png",
    "...-uk.png",
    "...-de.png",
    "...-fr.png",
    "...-es.png"
  ],
  "pdf": ".../report.pdf"
}
```

The number shown is illustrative. The contract is that all user-visible generated chart paths are returned.

---

# 28. SKILL.md changes

Keep `SKILL.md` compact.

Update `Run the Analysis` to link to the CLI reference.

Recommended shape:

```md
## Run the Analysis

All analyses must use the project CLI. Before execution, follow
[`cli.md`](references/cli.md) for the complete config → CLI → report →
artifact-validation lifecycle.

```bash
python <skill-root>/scripts/analyze.py \
  --config <config.json> \
  --output-dir <output-dir>
```

Do not call Wikimedia APIs directly or calculate results manually.

After the CLI completes, follow
[`artifact-validation.md`](references/workflows/artifact-validation.md)
before reporting success.
```

Add to the reference table:

```md
| Execute the analysis CLI and interpret exit/output state | [`cli.md`](references/cli.md) |
```

Do not copy the entire lifecycle into `SKILL.md`.

---

# 29. Workflow-reference changes

Workflow files should not duplicate CLI mechanics.

Where a workflow currently says:

```text
run the project CLI
```

it may link to:

```text
../cli.md
```

or rely on the global SKILL execution step.

At minimum, add `cli.md` as a related reference where doing so makes execution sequencing clearer.

`artifact-validation.md` should align with the new plural `charts` success payload and JSON-native `null`.

---

# 30. README changes

Keep README human/developer oriented.

Update only where needed so the example CLI output/behavior does not contradict the new contract.

README does not need the complete agent lifecycle.

`references/cli.md` is the authoritative agent execution reference.

---

# 31. Tests

Add deterministic tests for the CLI contract.

## 31.1 Success payload — all outputs

Assert exit `0` and JSON stdout equivalent to:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": "<path>",
  "charts": ["<path>"],
  "pdf": "<path>"
}
```

## 31.2 Disabled outputs

Test combinations including:

```text
JSON false
charts false
PDF false
```

Assertions:

```text
disabled JSON → null
disabled charts → []
disabled PDF → null
```

Never `"None"`.

## 31.3 Multiple charts

Create a deterministic run/result that represents seven or more language charts.

Assert:

- `charts` contains every generated chart;
- every returned chart path corresponds to an actual generated chart;
- no nonexistent base chart path is returned.

## 31.4 Configuration error

Invalid config:

```text
exit code = 2
```

If structured errors are implemented, assert:

```text
status = error
error_type = configuration_error
```

## 31.5 Analysis error

Mock deterministic pipeline failure:

```text
exit code = 1
```

If structured errors are implemented, assert:

```text
status = error
error_type = analysis_error
```

## 31.6 Stdout cleanliness

For successful analysis:

- stdout contains one parseable JSON object;
- it does not contain explanatory prose before or after the object.

## 31.7 Existing regression suite

All current unit/integration/E2E tests must continue to pass after intentional return-contract updates.

---

# 32. Agent-oriented documentation acceptance tests

Review `references/cli.md` against these scenarios.

## Scenario A — cheap model, default article analysis

The model must be able to determine:

```text
where to get config rules
where to write config
what command to run
what to inspect after exit 0
what artifact paths to use
```

without reading Python source.

## Scenario B — invalid config

The model must know:

```text
exit 2
→ config problem
→ consult input-schema
→ fix only mechanically determined fields
→ rerun
```

without changing unrelated user intent.

## Scenario C — resolver clarification with exit 0

The model must understand:

```text
process completed
≠
topic resolved
```

and ask for clarification rather than claiming successful topic analysis.

## Scenario D — seven-language comparison

The model must use all paths from:

```text
charts[]
```

and must not invent a singular chart path.

## Scenario E — PDF only

The model must understand:

```text
analysis_json = null
charts = []
pdf = <path>
```

without trying to open `"None"` or a nonexistent report JSON.

## Scenario F — analysis failure

The model must not switch to direct Wikimedia API calls or manually calculate results.

---

# 33. Expected implementation surface

Primary runtime files:

```text
src/wiki_trends/cli.py
src/wiki_trends/pipeline.py
```

Potential typed result model:

```text
src/wiki_trends/models.py
```

only if needed for a clean internal run-result contract.

Agent documentation:

```text
SKILL.md
references/cli.md
references/workflows/artifact-validation.md
```

Potential small link/consistency edits:

```text
references/workflows/article-analysis.md
references/workflows/topic-analysis.md
references/workflows/multi-language-comparison.md
references/workflows/period-selection.md
references/workflows/criteria-and-thresholds.md
references/workflows/follow-up-analysis.md
references/workflows/proxy-resolution.md
README.md
```

Tests:

```text
tests/e2e/test_cli_scenarios.py
tests/unit/test_smoke.py
```

or a dedicated:

```text
tests/unit/test_cli.py
```

SDD:

```text
docs/sdd/M22-agent-friendly-cli-contract-and-execution-lifecycle.md
docs/sdd/INDEX.md
docs/sdd/STATUS.md      # if used
```

---

# 34. Implementation order

Recommended order:

```text
1. Define the stable CLI payload contract
2. Introduce a typed internal run-result shape if needed
3. Make pipeline return every generated user-visible chart
4. Update CLI serialization
5. Remove string "None" artifact values
6. Add CLI contract tests
7. Add multi-chart regression test
8. Create references/cli.md
9. Update SKILL.md to route execution through cli.md
10. Update artifact-validation.md for the new payload
11. Update related references/README only where necessary
12. Run full verification
```

Implement runtime contract before writing final documentation so the reference describes actual behavior.

---

# 35. Verification commands

Run:

```bash
python -m pytest
ruff check .
mypy
git diff --check
```

Use repository-configured equivalents if needed.

Also run:

```bash
python scripts/analyze.py --help
```

and at least one deterministic/mocked CLI contract test.

A live Wikimedia call is not required for WT-M22 acceptance.

---

# 36. Acceptance criteria

WT-M22 is accepted only when all of the following are true.

## CLI protocol

- success stdout is valid JSON;
- `cli_schema_version` is present;
- `status = "success"` on exit `0`;
- disabled artifact paths use `null` or `[]`, never `"None"`;
- `charts` is plural and includes every user-visible generated PNG;
- the CLI does not return nonexistent chart paths;
- success stdout contains no extra prose.

## Errors

- config errors remain distinguishable as exit `2`;
- analysis errors remain distinguishable as exit `1`;
- the agent documentation explains what to do for each exit code;
- no failure path instructs the agent to reconstruct metrics manually.

## Lifecycle documentation

- `references/cli.md` exists;
- the complete request → config → CLI → output → report → artifact-validation → response lifecycle is explicit;
- skill-root handling is documented without hard-coded installation paths;
- config writing is explicit;
- post-exit-0 report inspection is explicit;
- exit `0` is clearly distinguished from analytical/comparison validity;
- path-authority rules are explicit;
- retry behavior is bounded;
- prohibited shortcuts are explicit.

## Skill integration

- `SKILL.md` links to `references/cli.md`;
- the reference table includes CLI execution;
- `SKILL.md` remains compact;
- workflow files do not duplicate the entire CLI guide;
- artifact-validation uses the new payload semantics.

## Regression safety

- WT-M20 topic correctness remains unchanged;
- WT-M21 workflow routing remains unchanged except for CLI-reference integration;
- report schema remains `2.1.0` unless an independently justified schema change is required;
- all existing tests pass after intentional return-contract updates;
- new CLI tests pass;
- Ruff passes;
- strict mypy passes;
- `git diff --check` passes.

---

# 37. Relationship to WT-M18 inexpensive-model evaluation

WT-M22 directly targets inexpensive-model reliability.

After implementation, WT-M18 revalidation should include observation of whether the model:

- reads the correct workflow(s);
- reads `references/cli.md` before execution;
- writes a valid config;
- invokes the CLI correctly;
- responds correctly to exit `1` and `2`;
- parses success stdout;
- does not interpret `null` as a path;
- handles multiple charts;
- inspects report statuses after exit `0`;
- does not treat process success as comparison validity;
- does not fall back to direct Wikimedia calls;
- validates artifacts before claiming success.

Raw evaluation evidence remains local under ignored `evaluation/`.

---

# Definition of Done

WT-M22 is done when a weaker tool-capable model can execute Wikipedia Trends by following an explicit documented state machine instead of inferring CLI behavior, and the CLI exposes a stable machine-readable contract with unambiguous optional artifacts and complete chart paths.
