"""Exception hierarchy exposed by Retra."""


class RetraError(Exception):
    """Base class for every exception raised by Retra."""


class ConfigurationError(RetraError):
    """Raised when cache configuration is invalid."""


class KeyGenerationError(RetraError):
    """Raised when a deterministic cache key cannot be generated."""


class SerializationError(RetraError):
    """Raised when a value cannot be serialized or deserialized."""


class BackendError(RetraError):
    """Raised when a backend operation fails."""


class CorruptedEntryError(BackendError):
    """Raised when persisted cache data cannot be decoded safely."""
