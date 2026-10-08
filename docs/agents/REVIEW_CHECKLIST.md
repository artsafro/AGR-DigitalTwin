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
- Known sandbox-only failure: `tests/test_run_record.py::test_timeout_preserves_partial_stdout_and_stderr`
  (`taskkill` access denied). It is not a finding.
- `codex review --base` does not take custom instructions; use `codex exec` for this checklist.
