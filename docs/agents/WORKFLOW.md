# Task workflow

Adapted from the AGR orchestration cycle (`docs/agr/` and the archive). Scale it to the
task: a one-line fix skips most steps; a multi-stage delivery uses all of them.

## Loop

1. **Goal and discovery.** Read `docs/PROJECT_STATE.md`, the relevant `docs/domain/` file,
   the matching accepted case (`docs/cases.md`) and the real inputs. A script or MCP that
   exists is not working until there is current evidence (`CAPABILITIES.md` status).
2. **Questions.** Ask only what changes the result, inputs, architecture, acceptance,
   destructive actions or publication. Decide routine details yourself.
3. **Contract.** For multi-stage work write in `jobs/<JOB>/STATE.md` (or the PR): goal and
   acceptance, exact inputs/versions, profile (NPM-OKS, VPM-OKS, NPM-territory…), owner of
   each scene/port/export, outputs, mandatory checks, stop conditions, next step. "Model"
   alone does not define the profile — ask when it matters.
4. **Plan.** Stages, dependencies, reused tools, checks. An open decision blocks only the
   stages that depend on it.
5. **Execute** in narrow stages. Pure computation in `src/`, DCC calls in adapters/tools,
   object parameters in the job, manual decisions in a record with their source. Every
   rerun writes a new versioned output; keep manifests and hashes.
6. **Verify independently.** The executor's report, exit 0 or a child agent's summary is
   not evidence. Read the actual files back. Classify a failure (source / tool / code /
   test / contract), fix the cause, rerun the affected checks. A failed mandatory check is
   never turned into a pass by rewording. After two failures with the same cause, stop that
   path, save the state and propose the next step.
7. **Hand off.** Compare the result with the original goal; report what is done, what was
   checked (commands, evidence paths) and what is open. On restart, read saved outputs and
   hashes before repeating any mutation (`run-evidence` skill).

## Reports

Keep full arrays, scenes and logs in files. In a report give counts, statuses, up to five
errors and paths to full evidence. `AdapterReport` describes one operation, not readiness
of the whole object.

## Experience capture

When the user accepts a result ("принято", "круто получилось", …) capture it before the
stage ends with the `experience-transfer` skill: exact acceptance scope, inputs/versions and
hashes, code used, checks actually run, failures and fixes, reuse candidates. Add it to
`docs/cases.md`. Praise does not replace QA. A procedure becomes a general tool or skill
only after it works on a second representative object.

## Git

- Start independent work from fresh `main` in a new worktree; continue a task in its own
  worktree. Check existing worktrees, branch, base/head and dirty state before choosing.
- Commit successes and useful failed attempts with an honest status message.
- Merge only after review and the user's approval; remove a worktree only after its
  ignored outputs that matter are saved.
