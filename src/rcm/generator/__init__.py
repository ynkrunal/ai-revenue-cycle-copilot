"""Seeded synthetic data generator for claims (no real PHI or PII, ever)."""

from rcm.generator import reference
from rcm.generator.build import generate
from rcm.generator.config import GeneratorConfig

__all__ = ["GeneratorConfig", "generate", "reference"]
