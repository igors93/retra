# Latest smoke benchmark

This result is a development smoke test, not a portable performance claim.

```text
Python: 3.13.5
Platform: Linux-4.4.0-x86_64-with-glibc2.41
functools.cache median: 57.1 ns; best: 56.6 ns
Retra speed median:    277.7 ns; best: 270.1 ns
Retra / functools median ratio: 4.86x
```

Command:

```bash
python benchmarks/smoke_benchmark.py
```

The Retra measurement includes exact typed key construction, inline-key comparison, namespace and
function generation checks, and the prepared-value return path. `functools.cache` is intentionally a
much thinner unbounded memoization wrapper and remains the lower-bound reference.
