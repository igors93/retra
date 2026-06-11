# Migration from Retra 0.1

Version 0.2 is a full rewrite. The original architecture is intentionally discarded rather than
supported through a compatibility layer.

## Major changes

- Memory entries are Python objects, not serialized byte payloads.
- Backends were replaced by stores and specialized memory engines.
- `CacheEntry` is replaced by `CacheRecord`.
- Decorators compile a call plan and add `peek`, `contains`, `refresh`, `bypass`, and `clear`.
- `clear()` on a decorated function is logical O(1) invalidation.
- Errors raise by default.
- `ttl=0` means do not cache; `NEVER_EXPIRE` and `DO_NOT_CACHE` are explicit constants.
- Persistent formats are new and cannot read version 0.1 cache files or tables.

## Migration strategy

1. Delete old cache files and databases; caches are reconstructable data.
2. Replace direct backend construction with `Cache.memory()`, `Cache.sqlite()`, or `Cache.file()`.
3. Review mutable return values and choose `reference`, `frozen`, or `copy`.
4. Review ignored parameters and custom keys.
5. Add generation dependencies for event-driven validity.
6. Run correctness tests before performance benchmarks.
