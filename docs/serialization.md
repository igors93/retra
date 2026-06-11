# Serialization

Backends store `CacheEntry.payload` as bytes. The configured serializer controls how application
values are converted to and from those bytes.

## PickleSerializer

Pickle supports many Python-specific objects and is the default serializer. Only use it with
trusted cache storage. Loading untrusted Pickle data can execute arbitrary code.

Pickle entries may also become unreadable when classes move, disappear, or change significantly.
Version function caches when deployments alter result formats.

## JsonSerializer

JSON is suitable for dictionaries, lists, strings, numbers, booleans, and null values. It is
human-readable and interoperable, but does not support arbitrary Python objects without a custom
conversion layer.

## Custom serializer

Implement the `Serializer` protocol:

```python
class Serializer:
    def dumps(self, value: object) -> bytes: ...
    def loads(self, payload: bytes) -> object: ...
```

Serializer implementations should raise `SerializationError` with a useful message when input
cannot be processed.
