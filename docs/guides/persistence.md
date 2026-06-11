# Persistence

Persistence is not part of the memory hot path.

## SQLiteStore

SQLite entries contain:

- 128-bit BLAKE2 digest for indexing;
- full canonical key for identity verification;
- serialized payload;
- payload and metadata checksum;
- creation and deadline timestamps;
- namespace, function, and dependency generations.

Readers use thread-local connections. Writes use one serialized connection and transactions.
`set_many()` performs one transaction for the supplied records.

WAL and `synchronous=NORMAL` are enabled for file databases. Applications with stricter durability
requirements should review SQLite configuration and failure assumptions before production use.

## FileStore

Each digest maps to a small collision directory. Files contain a versioned binary header followed by
the full canonical key, dependency versions, and raw serialized payload. Base64 and JSON are not
used in the storage envelope.

Writes use:

1. a temporary file in the destination directory;
2. flush and `fsync`;
3. `os.replace()`.

The full canonical key is compared after opening a candidate file. Corrupted files discovered during
pruning are renamed with a `.corrupt` suffix for diagnosis.

## TieredStore

A tiered cache has a `MemoryStore` front and a persistent backing store.

- read front;
- on miss, read backing;
- promote a backing hit to the front;
- write backing first, then front;
- invalidate both layers.

Because a front miss can perform I/O, tiering is explicit in the public API.

## Serialization

Pickle is the default persistent serializer because it supports arbitrary Python values. Pickle must
only be used with trusted local storage. `JsonSerializer` is available for interoperable data with a
smaller type surface.
