# Qwen3.8-27B on M1 Max: 2.10x in interleaved repeated runs with MTP D3

Reproducible single-stream benchmark of Qwen3.8-27B on an Apple M1 Max (32-core GPU, 64 GB unified memory) using MTPLX 2.9.0 and MTP depth 3 speculative decoding.

> **Interleaved five-run medians: AR 13.89 tok/s, MTP D3 29.16 tok/s.**
> Interleaved repeated-run speedup: **2.10x**. A shorter D3-only series reached 39.90 tok/s.
> Prefix cache disabled. Greedy AR/D1/D2/D3 outputs were byte-identical.
> Separate content-mix D3 medians: Japanese 18.67, English 22.28, Chinese 19.43, Python code 33.05 tok/s.

This is not a claim that the 27B target model natively decodes at 29–40 tok/s. It is final-output throughput with speculative decoding. Only committed output tokens are counted; draft tokens are not. The primary result alternates AR and D3 across a multi-minute sequence to expose performance drift. It is not a long-duration endurance test or one continuous long response.

[日本語版](README.ja.md) · [Technical article in Japanese](docs/article-ja.md)

## Result

### Formal interleaved run: AR and D3, five runs each

| Metric | AR | MTP D3 |
|---|---:|---:|
| Mean server decode | 13.854 tok/s | 30.173 tok/s |
| Median server decode | **13.892 tok/s** | **29.160 tok/s** |
| Range | 13.372–14.340 | 27.251–33.097 |
| Sample standard deviation | 0.415 | 2.521 |
| Median client-observed final-output rate | 13.744 tok/s | 28.438 tok/s |

Median D3/AR speedup: **2.099x**.

The monotonic decline across the multi-minute sequence is consistent with sustained-load or thermal effects, but temperature and power were not instrumented, so this repository reports the drift without assigning a proven cause.

### Short D3-only series

A separate five-run series immediately following warmup measured 35.201–39.897 tok/s, with a 38.909 tok/s median. It is published as a burst result, not the primary interleaved result.

### Greedy ablation

All four modes produced the same 512-token byte sequence and SHA-256 digest.

| Mode | Decode tok/s | Speedup vs AR |
|---|---:|---:|
| AR | 14.321 | 1.00x |
| MTP D1 | 21.931 | 1.53x |
| MTP D2 | 21.749 | 1.52x |
| **MTP D3** | **35.434** | **2.47x** |

### Longer run

A separate single 1,024-token run measured 35.061 tok/s decode and 34.046 tok/s end-to-end (`n=1`). It used a different 42-token prompt, so it is supporting evidence rather than a direct output-length comparison with the 29-token formal prompt.

### Content-mix throughput: Japanese, English, Chinese, and code

A separate 40-request run compared four output domains under the same 512-token greedy, cache-bypassed AR/D3 conditions. Each prompt and mode was repeated five times; content order was rotated and AR/D3 order alternated between rounds.

| Output domain | AR median | MTP D3 median | D3 range | D3/AR ratio of medians | D3 draft acceptance | D3 code points/s median |
|---|---:|---:|---:|---:|---:|---:|
| Japanese technical prose | 14.73 | **18.67** | 18.41–20.12 | 1.27x | 41.00% | 33.84 |
| English technical prose | 14.87 | **22.28** | 20.94–23.72 | 1.50x | 54.84% | 127.24 |
| Simplified Chinese technical prose | 14.55 | **19.43** | 18.50–19.89 | 1.34x | 40.87% | 36.17 |
| Python code | 14.76 | **33.05** | 31.83–34.70 | 2.24x | 93.55% | 107.74 |

All 40 requests produced 512 final tokens, used zero cached tokens, and had zero compiled-verification fallbacks. For each prompt, every AR and D3 repetition had the same output SHA-256. The code-only burst maximum remains 39.90 tok/s; it should not be presented as the expected speed of Japanese or other unconstrained prose.

The observed speed differences tracked draft acceptance and output predictability, not a simple ranking of languages. In these prompts, Python syntax coincided with much higher draft accuracy and reduced target verification calls to 135 per 512 tokens, versus 194 for English, 229 for Japanese, and 230 for Chinese. This is a one-prompt-per-category throughput microbenchmark, not a general language or quality benchmark. A token also represents different amounts of visible text across tokenizers and languages, so code points/s is included but is not semantic information per second.

### Public comparison context

As of 2026-08-31, the [exact FP16 artifact's model card](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16) says that its publisher has not published M1/M2 numbers. It reports 58.7 tok/s for the BF16 parent on an M5 Max coding task, under different sampling and stop conditions. That is useful context, not an apples-to-apples comparison. This repository therefore presents an auditable M1 Max data point rather than claiming an absolute rank.

## What was measured

- One request at a time (`serial`, `solo`)
- 512 final output tokens per repeated run
- `temperature=0`, `top_p=1`, `top_k=1`, fixed seed
- Thinking disabled
- Prefix/session cache bypassed
- MTPLX `turbo` profile, native MTP, depth 3
- Decode throughput reported as `final generated tokens / decode wall time`
- End-to-end throughput reported separately

The fixed prompt asks for Python implementations of merge sort and binary search plus deterministic tests. Every 512-token run ends at the fixed length limit and the emitted code is incomplete. This is a code-like deterministic decode microbenchmark, not a code-completion or agent-quality benchmark. Code is unusually predictable, so MTP acceptance is high. The result should not be generalized to unconstrained Japanese prose or long-context agent sessions.

## Hardware and software

| Component | Value |
|---|---|
| Mac | MacBook Pro `MacBookPro18,2` |
| SoC | Apple M1 Max |
| GPU | 32 cores |
| Unified memory | 64 GB |
| macOS | 26.6.2 (25G83) |
| Runtime | MTPLX 2.9.0; MLX 0.32.1; mlx-lm 0.31.3 |
| Model | `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16` |
| Model revision | `c984b2932d29676a6dabb6431b27da7ca2411508` |
| Model format | MLX mixed quantization, M1/M2 FP16 variant |

No serial number, hardware UUID, authentication token, model weight, or local user path is included in this repository.

## Reproduce

### 1. Obtain the runtime and model

Install [MTPLX](https://github.com/youssofal/MTPLX) according to its upstream instructions, then download the pinned model revision:

[`Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)

The model weights are not redistributed here. The mixed quantization, M1/M2 FP16 artifact conversion, MTP head, and MTPLX runtime are upstream work by Youssof Altoukhi/MTPLX. This repository contributes the M1 Max configuration, repeated measurements, ablation, audit, and reproducibility harness.

To fetch the exact measured revision with the `huggingface_hub` CLI:

```bash
export MODEL_PATH="$PWD/models/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16"
hf download Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16 \
  --revision c984b2932d29676a6dabb6431b27da7ca2411508 \
  --local-dir "$MODEL_PATH"
```

The revision and artifact fingerprint are also recorded in [`model.lock.json`](model.lock.json).

> Powered by MTPLX by Youssof Altoukhi — https://github.com/youssofal/MTPLX

### 2. Start the server

```bash
# Skip this line if MODEL_PATH was exported during the download step.
export MODEL_PATH="/absolute/path/to/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16"
export MTPLX_BIN="mtplx"
./scripts/start_server.sh
```

Keep this process running. The API should become available at `http://127.0.0.1:18038/v1`.

For a 64 GB Mac, stop other large local-model servers before loading the 27B model to avoid swap or GPU-memory contention.

### 3. Run the benchmark

In another terminal:

```bash
./scripts/benchmark.sh
```

Local output is written to the git-ignored `results/raw/` directory, leaving the published evidence unchanged. Use `--output-dir` to select another destination.

To repeat the Japanese/English/Chinese/code content-mix run:

```bash
python3 scripts/benchmark_content_mix.py
```

Required command-line tools: Python 3. The server-start and safe-system-info helpers also use standard macOS shell tools and `jq`.

### 4. Capture safe system metadata

```bash
./scripts/capture_system_info.sh
```

The script deliberately excludes serial numbers, UUIDs, and provisioning identifiers.

## Published evidence

- [`results/formal/raw-runs.jsonl`](results/formal/raw-runs.jsonl)
- [`results/formal/summary.json`](results/formal/summary.json)
- [`results/burst-2026-08-31/summary.json`](results/burst-2026-08-31/summary.json)
- [`results/content-mix-2026-09-01/summary.json`](results/content-mix-2026-09-01/summary.json)
- [`results/content-mix-2026-09-01/raw-runs.jsonl`](results/content-mix-2026-09-01/raw-runs.jsonl)
- [`results/m1max-1024-d3.json`](results/m1max-1024-d3.json)
- [`results/system.json`](results/system.json)
- [`model.lock.json`](model.lock.json)
- [`results/README.md`](results/README.md) — data and generated-output scope

## Interpretation

During the inspected 512-token D3 run, MTPLX reported 135 target verification cycles, 403 drafted tokens, 377 accepted drafts, and 119 bonus tokens. Bonus tokens are part of the target-produced output accounting and must not be added to accepted drafts as an independent final-token total. Acceptance probability by draft position was 96.30%, 95.52%, and 88.81%. All 135 verification calls used the compiled path with zero fallback calls.

That combination reduced the effective target-model iteration count while preserving the greedy output for this prompt. The interleaved repeated-run median gain was 2.10x. It is lower than `512 / 135` because a block verification is more expensive than one AR step and draft generation has its own cost.

## Scope and claims

This repository documents a local measurement, not an independently certified world record. A defensible public description is:

> Qwen3.8-27B reached a 29.16 output tok/s interleaved repeated-run median (n=5) on a 32-GPU-core M1 Max 64 GB using MTPLX 2.9.0 native MTP D3 speculative decoding, versus a 13.89 tok/s interleaved AR median (2.10x). A separate short D3-only series peaked at 39.90 tok/s. This was a 29-token-prompt/512-token-output greedy single-stream microbenchmark with prefix caching bypassed.

Comparisons with NVIDIA or newer Apple Silicon results require matching the model artifact, prompt length, output length, quantization, cache state, sampling, and throughput definition.

## Licenses

The original benchmark scripts, documentation, prompts, configuration, and the maintainer's copyrightable interest in the selection and arrangement of measurement records are released under the MIT License. Factual measurements may not be copyrightable. Model-generated text is not claimed as original work and is not published in the current result files; output parity is recorded with SHA-256 hashes and byte counts.

Qwen model weights, the optimized artifact, MTPLX, MLX, mlx-lm, and all other third-party components remain under their respective upstream terms. See [Third-party notices](THIRD_PARTY_NOTICES.md) and [results data scope](results/README.md).
