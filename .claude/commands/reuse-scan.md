---
description: Weekly reuse review - similar job scripts across jobs (src/ candidates), judgement procedures without a skill, user decisions without a pattern; a list with effort estimates, nothing created.
disable-model-invocation: true
argument-hint: "[days, default 7]"
---

Reuse review by the rule of three (`docs/agents/WORKFLOW.md`, "Rule of three"). Period: $ARGUMENTS days (7 if
empty; the facts below are for 7). Measured facts:

!`py -3 tools/reuse_candidates.py --days 7`

!`py -3 tools/hooks/usage_log.py stats --days 7`

This command only reads and reports. Create no code, skill, pattern or issue.

1. **Job scripts → `src/` / `tools/`.** From the pairs above, take the ones that are the same operation in two or
   more jobs (read both files, not only the ratio). For each: what it does, the jobs, what differs (parameters
   vs logic), where it would live (`src/dt_ai/…` or `tools/<stage>/`, `docs/agents/NAMING.md`), whether a
   backlog item already covers it (`docs/backlog.md`, e.g. H10).
2. **Judgement without a skill.** Read the `docs/cases.md` changes above, `jobs/*/STATE.md` changed in the
   period and the "Reuse proposals" in `docs/backlog.md`. Find procedures that need judgement and were done
   twice or more, with no skill in `.agents/skills/` covering them.
3. **Decisions without a pattern.** User decisions (dated "user YYYY-MM-DD" in cases, STATE, handoffs, PRs of
   the period: `gh pr list --state all --search "updated:>=<date>"`) that are not in
   `docs/domain/patterns/INDEX.md` or a domain file.
4. **Unused triggers.** From the usage counts: subagents, skills and commands never called although their
   trigger occurred (`docs/agents/WORKFLOW.md`, "Triggers"). If `logs/agent-usage.jsonl` does not exist yet, say
   so; do not guess counts.

Report in Russian, one list, most valuable first. Each line: kind (src/ module | CLI command | skill | pattern),
what, evidence (paths, counts), effort S (< 1 h) / M (half a day) / L (more), and whether a backlog item exists.
At the end offer to add the chosen lines to `docs/backlog.md` "Reuse proposals" — only after the user picks.
