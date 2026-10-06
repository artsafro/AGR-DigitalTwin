from pathlib import Path

from twinqa.profiles import load_profiles as _load_locked, rule_paths  # noqa: F401  (re-export)

FILES = ("NPM_STANDARD.yaml", "VPM_STANDARD.yaml", "DELIVERY_VALIDATOR.yaml")


def load_profiles(root: Path):
    """Profiles are locked to the reviewed copies in standards/ (one loader: twinqa).

    Returns {file name: profile dict} as before; the `conflicts:` annotation block is
    stripped so pipeline code sees only rule groups.
    """
    locked = _load_locked(Path(root) / "standards")
    data = dict(zip(FILES, (locked.npm, locked.vpm, locked.validator)))
    return {name: {k: v for k, v in value.items() if k != "conflicts"} for name, value in data.items()}
