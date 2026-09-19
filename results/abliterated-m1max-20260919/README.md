# Abliterated M1 Max companion record

This directory records a separate local measurement of the refusal-reduced
Qwen3.8-27B derivative. It is **not** the formal benchmark in the repository
root: that benchmark uses the non-abliterated `Youssofal/Qwen3.8-27B-MTPLX-
Optimized-Speed-FP16` artifact.

The derivative weights are not redistributed here. The record contains only
provenance, runtime settings, aggregate measurements, and output hashes.

## Artifact

- Repository: `PocketAiHub/Qwen3.8-27B-Abliterated-MTPLX-Optimized-Speed`
- Local M1 variant: `Qwen3.8-27B-Abliterated-MTPLX-Optimized-Speed-M1-FP16`
- Base model: `Qwen/Qwen3.8-27B`
- Base revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- Layout: 4-bit body, selected 8-bit modules, FP16 M1 auxiliary tensors, native MTP head
- Payload size: about 20.3 GiB

## M1 Max measurement

Host: Apple M1 Max, 32-core GPU, 64 GB unified memory. Runtime: MTPLX 2.9.0,
single stream, turbo profile, native MTP depth 3, prefix/session cache bypassed.

| Workload | Decode | End-to-end | Notes |
|---|---:|---:|---|
| Japanese technical prose | 20.90 tok/s | 19.81 tok/s | 461 tokens, stopped normally |
| Python/code-like output | 32.55 tok/s | 31.46 tok/s | 512-token fixed limit |
| Mathematical explanation | 33.87 tok/s | 32.68 tok/s | 512-token fixed limit |
| Three-workload mean | **29.11 tok/s** | **27.98 tok/s** | unweighted mean |

Greedy parity on the fixed code prompt produced the same SHA-256 output for
AR, D1, D2, and D3. The D3 row measured 37.21 tok/s in that run. The 512-token
fixed runs ended at `finish_reason=length`; they are throughput records, not
proof of completed coding quality.

The code validation record generated a palindrome implementation and passed its
six assertions at 32.43 decode tok/s and 25.19 end-to-end tok/s.

## Scope

This is a companion record for the local derivative, not a world-record claim.
The formal repeated-run benchmark, raw JSONL, and reproduction harness remain
the canonical public evidence for the non-abliterated artifact. The derivative
should be evaluated separately because abliteration changes behavior and
provenance.
