"""ICM platform benchmarking suite.

Three harnesses, all dependency-free (stdlib only) so they run from a laptop or
the VPS without installing anything:

* ``bench.governance_metrics`` — governance-quality & process metrics from the API
* ``bench.load_test``          — system performance / load (latency percentiles, throughput)
* ``bench.rubric_benchmark``   — agent-output-vs-baseline scored through the eval rubrics

See ``docs/benchmarking.md`` for methodology and how to read the numbers.
"""
