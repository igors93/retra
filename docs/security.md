# Security

## Pickle

Pickle can execute code while loading. Never allow an untrusted user to modify a Pickle-backed cache
directory or SQLite database. Checksums detect accidental corruption; they do not make Pickle safe
against a malicious writer.

Use `JsonSerializer` when the required values fit JSON and interoperability matters.

## Paths

File names are derived from digests, not user-provided key text. This prevents path traversal and
avoids exposing sensitive key contents in filenames. The full canonical key remains inside the
binary envelope.

## Logging

Retra does not log keys on successful operations. Error messages may include a key representation in
raise mode. Applications handling sensitive identifiers should sanitize their logging pipeline or
wrap public keys in non-sensitive domain identifiers.

## Resource limits

Memory caches require `max_items`. Persistent stores can also receive `max_items`. Size in bytes is
not yet enforced, so applications storing large values should use conservative limits and external
disk monitoring.
