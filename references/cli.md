# CLI Execution Reference

## Purpose

This reference defines the agent-facing execution contract for one Wikipedia
Trends analysis. The CLI accepts a UTF-8 JSON `AnalysisConfig` file; it does
not accept the user's natural-language request. Follow the relevant workflow
references and [`input-schema.md`](input-schema.md) before execution. Python
performs resolution, data collection, calculations, comparison, and report
generation.

## Execution Lifecycle

```text
USER REQUEST
    ↓
SKILL.md routing and preflight
    ↓
Relevant references/workflows/*
    ↓
Resolve required inputs; ask if intent is unclear
    ↓
Build AnalysisConfig from input-schema.md
    ↓
Write config JSON to a writable location
    ↓
Run scripts/analyze.py with --config and --output-dir
    ↓
Check process exit code
    ├── 2: configuration/usage failure → fix only a mechanically known error
    ├── 1: analysis/runtime failure → report the failure; do not recreate results
    └── 0: parse stdout JSON
              ↓
          Inspect analysis.json when its path is non-null
              ↓
          Inspect resolution, period, metrics, warnings, quality,
          criteria, and comparison status as relevant
              ↓
          Validate each requested artifact
              ↓
          Respond to the user
```

Exit code `0` means the process and pipeline completed. It does not prove that
every language resolved, a topic was resolved semantically, each criterion was
evaluable, quality checks passed, the requested period was fully available, or
a direct comparison is valid. Inspect the report statuses after every
successful run when JSON output is enabled.

A successful run may intentionally return no chart or PDF when resolution
leaves no analyzable series. Inspect `analysis.json` warnings before treating
empty artifact paths as a runtime failure.

## Step 0 — Locate the Skill Root

The skill root is the directory containing all four of:

```text
SKILL.md
scripts/analyze.py
references/
src/
```

Do not depend on an installation-specific absolute path. The config and output
directories may be outside the skill root. Use writable locations and pass the
actual paths used for this run. Do not modify `examples/` to execute a user
request.

Run either from the skill root:

```bash
python scripts/analyze.py --config <config-path> --output-dir <output-dir>
```

or with an explicit skill-root path:

```bash
python <skill-root>/scripts/analyze.py \
  --config <config-path> \
  --output-dir <output-dir>
```

## Step 1 — Build the Configuration

1. Complete `SKILL.md` preflight and read the relevant workflow references.
2. Read [`input-schema.md`](input-schema.md) for supported fields and defaults.
3. Build one `AnalysisConfig` object from the user's request and safe defaults.
4. Do not add unknown fields or invent a source language, ambiguous concept,
   threshold, baseline, or proxy approval.

The CLI does not interpret natural language or inline JSON. Pass a config file
through `--config`.

## Step 2 — Write the Configuration File

Write the configuration as UTF-8 JSON with exactly one top-level
`AnalysisConfig` object. It must contain valid JSON only: no Markdown fences,
comments, YAML, or explanatory prose. Use the actual path in the CLI command.
For a follow-up, derive the config from the previous report's `input` and apply
only the user's requested changes, following
[`workflows/follow-up-analysis.md`](workflows/follow-up-analysis.md).

## Step 3 — Choose the Python Interpreter

Use the Python environment already configured for the skill. Prefer the
repository virtual environment when it exists; otherwise use an available
Python 3.12+ interpreter with the skill dependencies installed. A common
Unix-like repository path is `<skill-root>/.venv/bin/python`, but it is not the
only supported interpreter. The command examples use `python` for brevity.

## Step 4 — Run the CLI

Pass both `--config` and `--output-dir` on every analysis run, even though
`--output-dir` has a default. This makes the current run's output root
unambiguous.

```bash
python <skill-root>/scripts/analyze.py \
  --config <config-path> \
  --output-dir <output-dir>
```

Capture the process exit code, stdout, and stderr separately. A relative path
in the success payload is relative to the CLI process working directory.

## Step 5 — Check the Exit Code

| Exit code | Meaning | Next action |
|---|---|---|
| `0` | Pipeline completed | Parse stdout, inspect report state, and validate requested artifacts. |
| `1` | Analysis/runtime failure | Read structured stderr; report the failure or address its concrete cause. Do not reconstruct results. |
| `2` | Configuration/CLI failure | Correct only a problem mechanically determined by the request, input schema, and error. Otherwise ask the user. |

Argparse syntax or usage errors, including a missing required argument, may use
argparse's native stderr format. They do not produce a success payload and use
exit code `2`. Application-controlled config and analysis errors use
structured JSON on stderr.

## Step 6 — Parse CLI Output

For exit `0`, parse stdout as exactly one JSON object and verify:

```text
cli_schema_version == "1.0.0"
status == "success"
```

Read the current run's `analysis_json`, `charts`, and `pdf` values. `null` means
there is no corresponding output path; `charts` is always an array. Do not
convert `null` to a path. Do not use stderr logs as analysis data.

## Step 7 — Inspect the Report

When `analysis_json` is a string, open that exact file and follow
[`output-schema.md`](output-schema.md). Inspect the fields relevant to the
request, including `schema_version`, `input`, `resolution`, `requested_period`,
`period`, `languages`, `comparison`, `criteria`, `quality`, `warnings`, and
`artifacts`. Preserve statuses such as `requires_clarification`, unresolved
language mappings, `comparison.comparable = false`, `not_evaluable`, quality
warnings/failures, and requested/available-period differences.

When `analysis_json` is `null`, do not assume a report exists, invent metrics,
or reconstruct `analysis.json`. Respect an explicit `output.json = false`.
The CLI stdout object is an execution protocol, not the analysis report.

## Step 8 — Validate Artifacts

Follow [`workflows/artifact-validation.md`](workflows/artifact-validation.md).
Use the current CLI payload as the path authority, then cross-check
`analysis.json.artifacts` when the report exists, then validate the filesystem.
Check every requested chart in `charts[]`, not a representative chart only.
Confirm JSON exists and parses, every PNG exists and is valid, and a requested
PDF exists and is readable. A path string alone does not prove the artifact is
valid.

Never predict paths from slug rules, scan for the newest output file, or reuse a
previous run's path because its name looks similar.

## Step 9 — Respond to the User

Summarize only Python-produced findings that are supported by the report and
validated outputs. State material resolution, period, quality, criterion, or
comparison limitations. Provide verified paths for requested artifacts. If
clarification is required, ask the user instead of rerunning to force a
different resolution.

## CLI Arguments

| Argument | Meaning |
|---|---|
| `--config <FILE>` | Required path to a UTF-8 JSON `AnalysisConfig` file. |
| `--output-dir <DIR>` | Root directory for generated artifacts. Agents must pass it explicitly. |
| `--help` | Safe informational command; prints CLI usage and does not run an analysis. |

## Success Payload

Exit `0` writes one JSON object to stdout and no explanatory prose around it:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": "output/run/analysis.json",
  "charts": ["output/run/trend.png"],
  "pdf": "output/pdf/report.pdf"
}
```

`analysis_json` and `pdf` are strings or JSON `null`. `charts` is always an
array of paths. Disabled outputs use `null` or `[]`, never the string `"None"`.
The CLI reports exact generated paths; for comparisons with seven or more
languages, `charts[]` contains every generated per-language PNG. A chart used
internally as PDF input is omitted from `charts[]` when chart output was not
requested.

All-disabled outputs are still a successful protocol response:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": null,
  "charts": [],
  "pdf": null
}
```

## Error Behavior

Application-controlled failures are JSON on stderr, with no success-shaped
stdout payload or expected-failure traceback.

Configuration failure, exit `2`:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "error",
  "error_type": "configuration_error",
  "message": "..."
}
```

Analysis/runtime failure, exit `1`:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "error",
  "error_type": "analysis_error",
  "message": "..."
}
```

On failure, do not parse stderr as metrics and do not expect a success object on
stdout. Argparse-native usage errors are the documented exception to structured
application errors.

## Recovery Rules

- **Exit 2:** Correct and rerun only if the request, `input-schema.md`, and
  error response determine one mechanical correction. If choosing would
  change user intent, stop and ask.
- **Exit 1:** Do not calculate fallback metrics, bypass the CLI with direct
  Wikimedia requests, or retry without a bound. The HTTP clients already
  perform bounded network retries. Retry only a clearly transient failure
  when doing so cannot change analytical meaning; otherwise report it.
- **Exit 0 with unresolved analysis:** Inspect the structured result. Do not
  rerun repeatedly to force resolution. Ask the user when clarification is
  required.

Never invent a source language, ambiguous concept, threshold, growth baseline,
or proxy approval.

## Examples

### Standard analysis

```bash
python <skill-root>/scripts/analyze.py \
  --config <workspace>/analysis-config.json \
  --output-dir <workspace>/wikipedia-trends-output
```

Then check the exit code, parse stdout, inspect `analysis_json` when present,
and validate all requested artifacts.

### JSON-only output

The payload has an `analysis_json` path, `charts: []`, and `pdf: null`.

### PDF-only output

The payload has `analysis_json: null`, `charts: []`, and a PDF path. Do not
publish the internal chart used to render the PDF as a requested chart.

### Seven-language comparison

Read every path in `charts[]` and validate each PNG. Do not expect a shared
base `*-trend.png` file when the actual files have language suffixes.

## Prohibited Shortcuts

- Calling Wikimedia directly instead of running the project CLI.
- Calculating metrics manually or copying metrics from terminal logs.
- Inventing canonical titles or promoting rejected resolver candidates.
- Predicting artifact filenames or selecting the newest file in an output directory.
- Reusing a prior run's path instead of the current run's returned path.
- Treating `"None"` as an artifact path.
- Treating exit `0` as proof of analytical or comparison validity.
- Silently changing user intent after config validation fails.
- Entering an unbounded retry loop.
- Manually editing generated `analysis.json`.
