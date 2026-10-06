---
name: experience-transfer
description: Reuse an accepted case in a similar task, or capture a result the user just accepted as a scoped case. Use when the user praises/accepts a result ("принято", "круто получилось"), before starting a task similar to an accepted case, or when deciding whether a job script should become an adapter or skill.
---

# Reuse and capture experience

## Before a similar task

1. Open `docs/cases.md`, read the matching write-up and its real artifacts in `jobs/<JOB>/`.
2. Compare with the new task: source and version, profile (NPM-OKS / VPM-OKS /
   NPM-territory), units, object names, materials/UV, assumptions, transport (MCP, CLI) and
   QA scope. Differences that change the result become parameters — or a reason the case
   does not apply. A saved successful run does not prove today's DCC session works.

## Capturing an accepted result

Record, in the job's `STATE.md` and a row in `docs/cases.md` (full write-up next to the
others, template `docs/agr/case_studies/TEMPLATE.md`):
- the exact scope the user accepted (what was looked at, which version) — unknowns stay unknown;
- inputs/versions with hashes, code and commands used, outputs;
- checks actually run and their results; failures and how they were fixed;
- what is reusable and what is object-specific.

Praise never closes topology, export, Checker or delivery checks.

## Choosing a reuse form

- one object and its revision constants → keep it as a job script;
- a general computation with explicit parameters → adapter candidate (hand to Codex,
  `docs/agents/ROLES.md`);
- a repeatable choice of context/tools → a narrow skill that links to them.

Generalise only after a second representative input (a different object, not a second run
on the same one) and at least one counter-example. A new proposal never overwrites approved
decisions or the regulation; record it as a conflict instead.

Return: case used or updated, proven scope, limits, what was saved, which check is still
needed to generalise.
