@echo off
rem Single guard implementation: .claude\hooks\guard.py (shared with Claude Code).
if exist "%~dp0..\..\.claude\hooks\guard.py" (
    py -3 "%~dp0..\..\.claude\hooks\guard.py"
) else (
    py -3 .claude\hooks\guard.py
)
