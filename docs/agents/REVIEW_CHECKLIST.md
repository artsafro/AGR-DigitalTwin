# Review checklist

Reviewer: any agent that is not the author (now Codex). The reviewer checks evidence, not
confidence. Source: `docs/HARNESS_PLAN.md` §8. Post the answer as a PR comment: verdict
(clean / changes needed), the three answers with numbers, findings by severity (P1/P2/P3).

1. **Pattern / scope.** Does each module refer to a pattern in `docs/domain/patterns/INDEX.md`,
   or is it honestly marked `new-case`? Does the change stay inside its issue and list what is
   not done?
2. **Invention.** Is there anything in the code or its output that the spec and the inputs do
   not support — guessed levels, made-up geometry, a silent fallback that hides a failure?
3. **Evidence.** Did the checker or the tests pass **with numbers**, run by the reviewer?
   Every regression test must fail on the commit before the fix and pass after it.

## Procedure (user 2026-10-13)

1. **Rounds by risk.**
   - `src/`, hooks, `pipeline_gate`, checkers: 2 rounds; a round 3 only if round 2 found a P1.
   - Patterns, plans, READMEs, briefs (ТЗ), benchmark specs and hashes, `object.json`: 1 round, no test run,
     a check against the rules for contradictions.
   - Jobs: no Codex; `independent-checker` and the user's acceptance.
   - The ceiling stays 3 rounds. The merge waits for the user's command.
2. **P1 in the PR, P2 to an issue.** P1 = a wrong result, a silent skip, data loss, or a hook bypass; it is
   fixed in the PR. Everything else is an issue with a number and a link to the round, and the merge does not
   wait for it. The reviewer's prompt carries this definition.
3. **The review's input** is the diff, this checklist and the affected tests and benchmarks - not the whole
   repository and not the full suite. The author runs the full suite and every benchmark once, before the
   merge.
4. **Timing.** Round 1 starts right after the first code commit; docs and tests are written meanwhile. The
   last round reviews the final version.

## Running a Codex review that can execute tests

Lessons of PR #15 (2026-10-08). The Codex sandbox runs as a separate Windows user
(`CodexSandboxOnline`) with no access to the author's profile and no GitHub token.

- Folder of throwaway worktrees outside the repo: `git worktree add --detach <dir>/head <head>`
  and `<dir>/prev <commit before the fix>`. Remove them after the review.
- Self-contained Python inside that folder: `uv python install 3.13 --install-dir <dir>/py`;
  in each worktree `UV_LINK_MODE=copy uv sync --reinstall --python <dir>/py/<cpython>/python.exe`.
  The default venv points at the author's Python and the uv cache: "access denied" in the sandbox.
- Give the issue text in the prompt (`gh issue view <n>` returns 401 inside the sandbox).
- Run: `codex exec -s workspace-write -C <dir> --skip-git-repo-check --output-last-message <file> -`
  with the prompt on stdin; tests as `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
  --basetemp=../tN`; git as `git -c safe.directory=* ...`.
- Keep `--basetemp` short (`../tN`, `C:/x/t-<name>`), for authors too: a long one passes MAX_PATH (git
  "Filename too long", the Win32 working-directory limit of 258) - PR #79. On the user's machine the default
  `%TEMP%\pytest-of-artsafro` is inaccessible (left as is, user 2026-10-12): plain `uv run pytest` errors there.
- Known sandbox-only failure: `tests/test_run_record.py::test_timeout_preserves_partial_stdout_and_stderr`
  (`taskkill` access denied). It is not a finding.
- `codex review --base` does not take custom instructions; use `codex exec` for this checklist.
