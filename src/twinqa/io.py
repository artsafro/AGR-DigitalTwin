# Ported from AGR src/dt_ai/core/io.py (sha256 5b0014c84518) on 2026-10-06;
# changes: removed repo_root()/inside()/write_json (AGR checkout coupling), added
# digest_text() (line-ending neutral) and a UTF-8 strict text reader.
"""Strict JSON/YAML readers: duplicate keys and non-finite numbers are errors."""
import hashlib
import json
from pathlib import Path

import yaml


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_text(path: Path) -> str:
    """SHA-256 of a text file with CRLF normalised to LF (git eol=lf vs Windows checkouts)."""
    return digest(path.read_bytes().replace(b"\r\n", b"\n"))


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key: {key}")
        result[key] = value
    return result


def _reject_constant(name):
    raise ValueError(f"Nonfinite value: {name}")


def read_json(data: bytes | str):
    """Parse JSON; bytes must be UTF-8. Duplicate keys and NaN/Infinity raise ValueError."""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data, object_pairs_hook=unique_pairs, parse_constant=_reject_constant)


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    loader.flatten_mapping(node)
    return unique_pairs((loader.construct_object(k), loader.construct_object(v)) for k, v in node.value)


def _float(loader, node):
    value = yaml.SafeLoader.construct_yaml_float(loader, node)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"Nonfinite value in YAML: {node.value}")
    return value


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
UniqueLoader.add_constructor("tag:yaml.org,2002:float", _float)


def read_yaml(path: Path):
    return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
