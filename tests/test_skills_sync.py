"""`.claude/skills/` must be the generated copy of the canonical `.agents/skills/`."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("sync_skills", ROOT / "tools/sync_skills.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_claude_skills_match_agents_skills():
    assert load().differences() == [], "run: py -3 tools/sync_skills.py"


def test_every_skill_has_frontmatter():
    for skill in (ROOT / ".agents/skills").glob("*/SKILL.md"):
        head = skill.read_text(encoding="utf-8").splitlines()[:4]
        assert head[0] == "---" and any(line.startswith("name:") for line in head), skill
