"""Spec v0.2 (v0.1 + openings across levels): the normalized exterior description every modelling run starts from.

Contract: docs/HARNESS_PLAN.md §3-§4; term `Spec` in GLOSSARY.md.
"""
from dt_ai.spec.mesh import SpecError, SpecStops, extract_spec
from dt_ai.spec.model import Spec

__all__ = ["Spec", "SpecError", "SpecStops", "extract_spec"]
