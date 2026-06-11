# Retra Documentation

## Reference

- [API Guide](reference/api.md) — manual operations, decorated functions, and configuration options
- [Architecture](reference/architecture.md) — compiled-call design, inline cache, key plans, and engines

## Guides

- [Concurrency](guides/concurrency.md) — selecting single, read-heavy, or balanced mode
- [Persistence](guides/persistence.md) — SQLite, file, and tiered stores
- [Precision](guides/precision.md) — typed keys, canonical keys, and key correctness
- [Serialization](guides/serialization.md) — JSON and Pickle serializers; custom serializers
- [Error Handling](guides/error_handling.md) — raise vs. suppress; `CacheClosedError`
- [Security](guides/security.md) — checksum validation; trusted-publisher workflow

## Performance

- [Performance Model](performance/performance.md) — hot-path rules and profiling guidance
- [Benchmarks](performance/benchmarks.md) — reference numbers and methodology

## Examples

- [Trading and Low-Latency](examples/trading.md) — guidance for latency-sensitive workloads

## Internationalisation

- [Visão geral (pt-br)](i18n/overview-pt-br.md)

## Migration

- [Migrating to 0.1.0](migration.md) — upgrading from the original experimental architecture
