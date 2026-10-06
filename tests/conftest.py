from pathlib import Path

import pytest

from dt_ai.core.io import read_json
from dt_ai.core.models import BuildJob


@pytest.fixture
def root():
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def job(root):
    return BuildJob.model_validate(read_json((root / "jobs/SYNTH-001/project.json").read_bytes()))
