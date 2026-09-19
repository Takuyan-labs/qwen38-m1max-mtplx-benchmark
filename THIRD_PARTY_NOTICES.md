# Third-party notices and license scope

This repository contains original benchmark scripts, documentation, prompts, configuration, and measurement records. It does not redistribute model weights, MTPLX source code, MLX source code, or mlx-lm source code.

The repository's original scripts, documentation, prompts, configuration, and any copyrightable interest held by the maintainer in the selection and arrangement of the measurement records are licensed under the repository's MIT License. Factual measurements may not be copyrightable. The maintainer does not claim authorship or ownership of model-generated text. Published result files retain output hashes and byte counts rather than generated text; see [`results/README.md`](results/README.md).

## Qwen3.8-27B

- Upstream organization: Qwen
- Base model: `Qwen/Qwen3.8-27B`
- License: Apache-2.0
- License text: [Qwen3.8-27B/LICENSE](https://huggingface.co/Qwen/Qwen3.8-27B/blob/main/LICENSE)
- Model card and citation: [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)

## Optimized-Speed-FP16 artifact

- Artifact: [`Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)
- Pinned revision used here: `c984b2932d29676a6dabb6431b27da7ca2411508`
- Author/publisher: Youssof Altoukhi / MTPLX
- License: the Hugging Face repository metadata declares Apache-2.0; the pinned artifact tree does not contain a standalone license file
- Base model license: Apache-2.0

The mixed quantization, M1/M2 FP16 sibling conversion, MTP head, and runtime contract are upstream work. This repository's contribution is the M1 Max configuration, repeated measurement, ablation, audit trail, and reproducibility harness.

## Abliterated companion artifact

- Artifact: [`PocketAiHub/Qwen3.8-27B-Abliterated-MTPLX-Optimized-Speed`](https://huggingface.co/PocketAiHub/Qwen3.8-27B-Abliterated-MTPLX-Optimized-Speed)
- Local measurement variant: `Qwen3.8-27B-Abliterated-MTPLX-Optimized-Speed-M1-FP16`
- Base model: `Qwen/Qwen3.8-27B`, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- Conversion and refusal-direction projection: PocketAiHub
- License: Apache-2.0; the artifact's `LICENSE` and `NOTICE` files govern the derivative
- Safety note: abliteration changes refusal behavior; it is not a safety improvement or a guarantee of correctness or compliance

The companion record under `results/abliterated-m1max-20260919/` does not
redistribute the derivative weights. It publishes only provenance, aggregate
measurements, hashes, and reproduction conditions.

## MTPLX

- Project: [MTPLX](https://github.com/youssofal/MTPLX)
- Author: Youssof Altoukhi
- Version measured: 2.9.0
- License: Apache-2.0 — [v2.9.0 LICENSE](https://github.com/youssofal/MTPLX/blob/v2.9.0/LICENSE)
- Attribution terms: [v2.9.0 NOTICE](https://github.com/youssofal/MTPLX/blob/v2.9.0/NOTICE)
- Citation metadata: [v2.9.0 CITATION.cff](https://github.com/youssofal/MTPLX/blob/v2.9.0/CITATION.cff)

Required benchmark credit, displayed in the README files, technical article, and server-start helper:

> Powered by MTPLX by Youssof Altoukhi — https://github.com/youssofal/MTPLX

## Runtime dependencies not redistributed here

- [MLX](https://github.com/ml-explore/mlx), measured version 0.32.1 — MIT License
- [mlx-lm](https://github.com/ml-explore/mlx-lm), measured version 0.31.3 — MIT License

All trademarks, model weights, and third-party software remain subject to their respective owners' terms.
