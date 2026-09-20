# MTPLX runtime pilot (2026-09-21)

This file records a bounded Phase-1 runtime pilot. It is not a replacement for the repository's formal 512-token, five-run baseline.

## Fixed conditions

- Apple M1 Max, 32-core GPU, 64 GB unified memory
- `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`
- pinned resolved revision `c984b2932d29676a6dabb6431b27da7ca2411508`
- prompt: `Output only valid Python code implementing merge sort, binary search, and deterministic unit tests.`
- 128 generated tokens, greedy (`temperature=0`, `top_p=1`, `top_k=1`, `seed=123`)
- single stream, serial/solo, Turbo, native MTP depth 3, prefix/session cache bypass
- two AR and two D3 requests per runtime, alternating; one server at a time
- server-side `decode_tok_s` is the primary metric

## Results

| MTPLX | MLX | AR mean/median | D3 mean/median | Output SHA | Compiled verify |
|---:|---:|---:|---:|---|---:|
| 2.9.2 | 0.32.1 | 14.5997 / 14.5997 | 37.4077 / 37.4077 | AR=D3 | 34 / 0 fallback |
| 2.10.2 | 0.32.2 | 14.6235 / 14.6235 | 37.5840 / 37.5840 | AR=D3 | 34 / 0 fallback |
| 2.11.3* | 0.32.2 | 14.5791 / 14.5791 | 36.9259 / 36.9259 | AR=D3 | 34 / 0 fallback |
| 2.11.3 (clean) | 0.32.2 | 14.3499 / 14.3499 | 36.6470 / 36.6470 | AR=D3 | 34 / 0 fallback |

Each median above has `n=2`; the two individual values and full stats are in [`runtime-pilots-2026-09-21.jsonl`](runtime-pilots-2026-09-21.jsonl).

`*` The first 2.11.3 pilot inherited the host `transformers==5.9.0`, while MTPLX 2.11.3 declares `transformers>=5.10.0,<5.15` (excluding 5.13.0). It started and produced parity output, but it is a provisional compatibility smoke result, not a valid release-performance comparison. A clean 2.11.3 environment with the declared dependency is prepared separately; its speed run must be done after thermal cooldown and without another benchmark server.

The clean 2.11.3 row uses an isolated environment with the declared dependency (`transformers==5.12.1`) and stock PyPI MLX layout. MTPLX reports NAX enabled but unavailable on this M1 Max run (`capacity_below_threshold`), so the M1 path used compiled verify without the NAX route.

## Interpretation

No requested version with a valid dependency result clears the project's +3% adoption threshold in this pilot. 2.10.2 is only about 0.47% above 2.9.2 on D3; clean 2.11.3 is about 2.5% below 2.10.2. The starred 2.11.3 row is provisional because of the dependency mismatch described above; the clean row is the valid 2.11.3 dependency result. This is a short-output pilot, so it does not establish long-run ranking or replace the published 2.9.0 five-run result.

2.9.2 and later intentionally default Turbo to lazy target-distribution preparation (`MTPLX_LAZY_TARGET_DISTRIBUTIONS=1`, `MTPLX_BATCH_TARGET_ARRAYS=0`); 2.9.0 reports the older `BATCH_TARGET_ARRAYS=1` flag. The 2.9.2 runtime source states that the old setting was a dead flag and that the batched candidate is an explicit A/B (`LAZY_TARGET_DISTRIBUTIONS=0` and `BATCH_TARGET_ARRAYS=1`). Therefore these are version-default measurements, not a claim that all versions ran the same internal strategy.

The exact target model was not modified. The target weights were loaded from the existing local MTPLX cache; its `.mtplx-source.json` records the same resolved revision.
