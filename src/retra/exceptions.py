"""Retra-specific exception hierarchy."""

from __future__ import annotations


class RetraError(Exception):
    """Base class for every public Retra exception."""


class ConfigurationError(RetraError):
    """Raised when cache configuration is invalid."""


class KeyGenerationError(RetraError):
    """Raised when a deterministic key cannot be created."""


class SerializationError(RetraError):
    """Raised when a value cannot be serialized or deserialized."""


class StoreError(RetraError):
    """Raised when a cache store cannot complete an operation."""


class CorruptedEntryError(StoreError):
    """Raised when persisted bytes fail structural or checksum validation."""


class CacheClosedError(RetraError):
    """Raised when an operation is attempted on a closed cache."""


class GenerationRaceError(RetraError):
    """Raised when dependencies keep changing while a value is computed."""
