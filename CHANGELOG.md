# Changelog

## 0.2.0a1

This release is a complete rewrite. The previous backend-first architecture was removed.

- Added the Retra compiled-call architecture.
- Added exact typed keys and canonical persistent keys.
- Added constant, scalar, tuple, canonical, and custom key plans.
- Added a one-entry inline cache for decorated functions.
- Added single-thread, snapshot/read-heavy, and locked engines.
- Added O(1) generation-based invalidation.
- Added reference, frozen, and copy value modes.
- Added striped miss gates and async miss gates.
- Added direct-object memory storage with no serialization.
- Added binary file persistence with checksums and atomic replacement.
- Added SQLite persistence with canonical-key collision verification.
- Added explicit tiered memory + persistent storage.
- Added off, basic, sampled, and exact statistics modes.
- Added compiled sync decorators and async decorators.
- Added benchmarks, migration guidance, and architecture documentation.

## 0.1.0

Initial experimental architecture. This architecture is no longer supported.
