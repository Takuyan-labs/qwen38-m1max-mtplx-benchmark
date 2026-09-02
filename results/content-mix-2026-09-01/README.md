# Content-mix throughput result

This directory records a 40-request output-domain throughput microbenchmark on the same M1 Max, pinned model artifact, and MTPLX 2.9.0 configuration as the main result.

Four fixed prompts requested Japanese technical prose, English technical prose, Simplified Chinese technical prose, and Python code. AR and MTP D3 were each measured five times per prompt. Content order was rotated and AR/D3 order alternated between rounds.

The prose prompts deliberately request more text than can fit in 512 tokens to prevent early EOS. The harness then stops every response at exactly 512 final tokens; this is a fixed-length throughput test, not a completion-quality test.

Every measured request produced 512 final tokens and ended with `finish_reason=length`. Greedy output was byte-identical across all AR and D3 repetitions for each prompt. Cache restore was disabled, and all compiled verification fallback counts were zero.

The files retain only hashes, byte and character counts, timings, and runtime statistics. Generated response text is not published.

`summary.json` binds the measurement to the exact prompt manifest with SHA-256. The reported D3/AR multiplier is the ratio of the D3 median to the AR median, not the median of five paired ratios.

> Powered by MTPLX by Youssof Altoukhi — https://github.com/youssofal/MTPLX

Third-party components retain their upstream terms; see [`../../THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).

This is an output-domain microbenchmark using one prompt per category, not a general language-quality benchmark. Tokenization differs across languages, so Unicode code points per second are published alongside tokens per second; neither is a direct measure of semantic information per second.

- [`summary.json`](summary.json) — aggregated statistics
- [`raw-runs.jsonl`](raw-runs.jsonl) — sanitized per-request evidence
- [`../../prompts/content-mix.json`](../../prompts/content-mix.json) — exact prompts
- [`../../scripts/benchmark_content_mix.py`](../../scripts/benchmark_content_mix.py) — reproduction harness
