# Third-party notices

This repository contains only original benchmark scripts, documentation, and measurement records. It does not redistribute model weights or MTPLX source code.

## Qwen3.8-27B

- Upstream organization: Qwen
- Base model: `Qwen/Qwen3.8-27B`
- License: see the upstream model repository

## Optimized-Speed-FP16 artifact

- Artifact: [`Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)
- Pinned revision used here: `c984b2932d29676a6dabb6431b27da7ca2411508`
- Author/publisher: Youssof Altoukhi / MTPLX
- License: Apache-2.0 as declared by the artifact repository

The mixed quantization, M1/M2 FP16 sibling conversion, MTP head, and runtime contract are upstream work. This repository's contribution is the M1 Max configuration, repeated measurement, ablation, audit trail, and reproducibility harness.

## MTPLX

- Project: [MTPLX](https://github.com/youssofal/MTPLX)
- Author: Youssof Altoukhi
- Version measured: 2.9.0
- License: Apache-2.0 as declared by the upstream project

All trademarks, model weights, and third-party software remain subject to their respective owners' terms.
