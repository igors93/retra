# Benchmarking

Retra includes two benchmark entry points.

## Smoke benchmark

```bash
python benchmarks/smoke_benchmark.py
```

This uses `timeit` and is useful only for quick local comparisons.

## Pyperf benchmark

```bash
python benchmarks/bench_hot_path.py -o result.json
python -m pyperf stats result.json
```

Pyperf runs worker processes and attempts to reduce measurement noise.

## Required context

Record at least:

- Python implementation and version;
- operating system and kernel;
- CPU model and power mode;
- virtualization status;
- cache profile;
- argument types;
- hit ratio;
- thread count;
- whether inline cache was warm.

Do not compare a primitive-key memory hit with a complex canonical-key persistent lookup as if they
were the same operation.
