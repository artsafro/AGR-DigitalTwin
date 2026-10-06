import importlib.util
import os
from pathlib import Path

import pytest


def load_module():
    path = Path(__file__).resolve().parents[1] / "tools/project_hygiene.py"
    spec = importlib.util.spec_from_file_location("project_hygiene", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_classification_keeps_repository_content_and_local_data_separate():
    module = load_module()
    limit = 5_000_000
    assert module.classify_path("src/dt_ai/check.py", 100, limit) == "promote_candidate"
    assert module.classify_path("docs/case_studies/CASE.md", 100, limit) == "promote_candidate"
    assert module.classify_path(".cursor/rules/github.mdc", 100, limit) == "promote_candidate"
    assert module.classify_path("jobs/ABC/project.json", 100, limit) == "review_candidate"
    assert module.classify_path("jobs/ABC/outputs/model.fbx", 100, limit) == "keep_local"
    assert module.classify_path("docs/large.md", limit + 1, limit) == "keep_local"


def test_sensitive_names_are_blocked_before_promotion():
    module = load_module()
    assert module.classify_path("src/tokenizer.py", 100, 1000) == "promote_candidate"
    assert module.classify_path(".cursor/mcp.json", 100, 1000) == "blocked_sensitive"
    assert module.classify_path("docs/passwords.md", 100, 1000) == "blocked_sensitive"
    assert module.classify_path("docs/api-key.txt", 100, 1000) == "blocked_sensitive"
    assert module.classify_path("tools/id_rsa.txt", 100, 1000) == "blocked_sensitive"
    assert module.classify_path("tools/private.pem", 100, 1000) == "blocked_sensitive"
    assert module.classify_path(".env", 100, 1000) == "blocked_sensitive"


def test_sensitive_content_is_detected_without_returning_content(tmp_path):
    module = load_module()
    path = tmp_path / "config.txt"
    path.write_text("api_key=do-not-publish", encoding="utf-8")
    assert module.contains_sensitive_content(path, path.stat().st_size) is True


def test_duplicate_groups_hash_only_small_files(tmp_path):
    module = load_module()
    (tmp_path / "a.txt").write_text("same", encoding="utf-8")
    (tmp_path / "b.txt").write_text("same", encoding="utf-8")
    (tmp_path / "large.txt").write_text("larger", encoding="utf-8")
    groups, errors = module.duplicate_groups(
        tmp_path, ["a.txt", "b.txt", "large.txt"], 4)
    assert len(groups) == 1
    assert groups[0]["paths"] == ["a.txt", "b.txt"]
    assert errors == []


def test_duplicate_scan_does_not_follow_symlink(tmp_path):
    module = load_module()
    target = tmp_path / "target.txt"
    target.write_text("outside candidate", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    groups, errors = module.duplicate_groups(tmp_path, ["link.txt"], 1000)
    assert groups == []
    assert errors == [{"path": "link.txt", "error": "symlink or reparse point not hashed"}]
