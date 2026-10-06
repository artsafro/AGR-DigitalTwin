---
name: run-evidence
description: Inspect a saved RunRecord after an interruption or before accepting a saved stage — check input/output file evidence, separate produced from verified, list open gates and choose the next safe action without rerunning a DCC operation. Use when resuming a job stage or reviewing someone else's run.
---

# Inspect a saved run

1. Find the run directory and its `attempt-*/input-manifest.json` through the job's
   `jobs/<JOB>/STATE.md`. Match run_id, inputs and context — never pick a folder only
   because it has the highest number. If the manifest is missing, say so; do not rebuild
   it from the desired result.
2. From the repo root run:

   ```
   uv run python tools/harness_status.py --run <run-dir> --manifest <input-manifest.json>
   ```

   Add `--report <report.json>` when an AdapterReport exists. Pass the mandatory gates of
   the job/profile with repeated `--required-check <id>`; do not invent check names or
   rely only on the report's own list. The command only reads files, prints JSON and always
   returns `delivery_passed=false`. Exit 0 = no file-integrity error found (pending gates may
   remain); 1 = evidence mismatch; 2 = unusable input.
3. Read `current_inputs`, `evidence_integrity`, stage states, errors, `unresolved_gates`,
   `next_action`. Status meanings (Russian original): `docs/agr/local-orchestration/ENGINEERING.md`.
   - `produced` — check the saved output first; do not repeat the mutation.
   - `verified` — that stage's check is recorded; its scope is not full acceptance.
   - `uncertain` — a "running" record does not prove a live process. Confirm process, scene
     and outputs before any retry; never delete locks automatically.
   - `stopped` or changed/missing evidence — keep the facts, classify the cause, use new
     output paths for the next allowed attempt.
   - `reported_pass_unverified` — read the real evidence of that gate. A valid AdapterReport
     with a path in it is not native QA.

Return: run_id/stage, integrity, open checks, paths to full evidence, the justified next
step. Never declare the model delivered.
