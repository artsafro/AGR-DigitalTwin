"""tools/hooks/context_watch.py: context share from the transcript, thresholds once per session."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tools/hooks/context_watch.py"
sys.path.insert(0, str(HOOK.parent))
import context_watch  # noqa: E402

MODEL_200K = "claude-opus-4-6"


def response(tokens, model=MODEL_200K, text="ok"):
    return {"type": "assistant", "message": {"id": f"m{tokens}", "model": model, "content": [{"type": "text",
            "text": text}], "usage": {"input_tokens": 2, "cache_creation_input_tokens": 1000,
                                      "cache_read_input_tokens": tokens - 1002, "output_tokens": 50}}}


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def write(path, *entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def run(payload, env=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_")} | (env or {})
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else None


def test_hook_is_wired():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"].endswith('context_watch.py"')


@pytest.mark.parametrize("model, env, size", [
    ("claude-opus-4-6", {}, 200_000),
    ("claude-opus-4-6[1m]", {}, 1_000_000),
    ("claude-opus-5-5", {}, 1_000_000),
    ("claude-sonnet-5-5", {}, 1_000_000),
    ("claude-fable-5-1", {}, 1_000_000),
    ("claude-haiku-4-5", {}, 200_000),
    ("claude-opus-5-5", {"CLAUDE_CODE_DISABLE_1M_CONTEXT": "1"}, 200_000),
    ("claude-opus-5-5", {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "300000"}, 300_000),
    (None, {}, 200_000),
])
def test_window(model, env, size, monkeypatch):
    for k in ("CLAUDE_CODE_DISABLE_1M_CONTEXT", "CLAUDE_CODE_MAX_CONTEXT_TOKENS"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert context_watch.window(model) == size


def test_usage_plus_tail(tmp_path):
    t = write(tmp_path / "s.jsonl", user("hi"), response(80_000), user("abc " * 500),
              {"type": "user", "message": {"content": [{"type": "tool_result", "content": [
                  {"type": "image", "source": {"type": "base64", "data": "A" * 50_000}}]}]}},
              {"type": "assistant", "isSidechain": True, "message": {"usage": {"input_tokens": 900_000}}})
    used, model = context_watch.used_tokens(t, "y" * 200)
    assert model == MODEL_200K
    assert used == 80_000 + 1 + 1000 + 1600 + 100          # response text "ok", 2000 chars, an image, the prompt


def test_compaction_resets_the_count(tmp_path):
    t = write(tmp_path / "s.jsonl", response(150_000), {"type": "system", "subtype": "compact_boundary"},
              user("abc " * 1000))
    assert context_watch.used_tokens(t)[0] == 2000


def test_thresholds_fire_once_per_session(tmp_path):
    t = write(tmp_path / "s.jsonl", response(50_000))
    payload = {"session_id": "a", "transcript_path": str(t), "prompt": "go"}
    assert run(payload) is None                                        # 25 %
    write(t, response(95_000))
    first = run(payload)
    assert first.startswith("context ≈48 % (95k of 200k tokens): suggest /handover")
    assert run(payload) is None                                        # 45 % spent
    write(t, response(140_000))
    assert "strongly urge" in run(payload)
    assert run(payload) is None
    assert run({**payload, "session_id": "b"}) is not None              # another session: flags start again


def test_jump_past_both_thresholds_speaks_once(tmp_path):
    t = write(tmp_path / "s.jsonl", response(150_000))
    payload = {"session_id": "a", "transcript_path": str(t)}
    assert "strongly urge" in run(payload)
    assert run(payload) is None
    assert json.loads(Path(f"{t}.context-watch.json").read_text())["fired"] == [45, 65]


@pytest.mark.parametrize("raw", ["not json", "[]", json.dumps({"transcript_path": "C:/nope/x.jsonl"}), "{}"])
def test_bad_input_is_silent(raw):
    r = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout == ""
