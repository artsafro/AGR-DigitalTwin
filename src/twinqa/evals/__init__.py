"""Agent-behaviour evals (#122, spec docs/prd/agent-ready-harness.md, "Checks and evals").

Graders are pure Python over evidence files (transcripts, the usage log, benchmark reports); no LLM calls.
`runner.run` executes the task folders under `evals/`; `dt evals` is its command line.
"""
