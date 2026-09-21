#!/usr/bin/env python3
"""Measure prompt processing separately from one-token decode.

This baseline harness sends deterministic English prompts of approximately
1k/2k/4k/8k tokens, records MTPLX's actual prompt_tokens value, and keeps
prefill, TTFT, request, and decode timings in separate fields. The server is
the authority for the actual tokenizer count.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_BLOCK = (
    "This is a deterministic prefill measurement sentence. "
    "The benchmark must preserve the prompt and must not answer it. "
    "Apple silicon unified memory, transformer inference, attention, "
    "speculative decoding, and token accounting are repeated here only "
    "to create a stable prompt-processing workload. "
)


def make_prompt(target_tokens: int) -> str:
    """Construct a stable ASCII prompt near the requested token count.

    Exact tokenization is not guessed. Every response stores prompt_tokens
    reported by MTPLX, so comparisons use that value.
    """
    target_chars = max(64, int(target_tokens * 4.0))
    chunks: list[str] = []
    chars = 0
    index = 0
    while chars < target_chars:
        part = f"[prefill block {index:06d}] {PROMPT_BLOCK}"
        chunks.append(part)
        chars += len(part)
        index += 1
    return "".join(chunks)[:target_chars]


def api_request(
    url: str,
    model: str,
    prompt: str,
    mode: str,
    depth: int,
    max_tokens: int,
) -> tuple[dict[str, Any], float]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "top_k": 1,
        "seed": 123,
        "stream": False,
        "enable_thinking": False,
        "generation_mode": mode,
        "metadata": {"cache_mode": "bypass", "allow_client_controls": True},
    }
    if mode == "mtp":
        payload["depth"] = depth
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-MTPLX-Allow-Client-Controls": "1",
            "X-MTPLX-Cache-Mode": "bypass",
        },
    )
    started = time.perf_counter_ns()
    with urllib.request.urlopen(request, timeout=900) as response:
        data = json.load(response)
    wall_s = (time.perf_counter_ns() - started) / 1_000_000_000
    return data, wall_s


def sanitize(
    data: dict[str, Any],
    client_wall_s: float,
    target_prompt_tokens: int,
    prompt: str,
    run: int,
    mode: str,
    depth: int,
) -> dict[str, Any]:
    stats = data["mtplx_stats"]
    text = data["choices"][0]["message"]["content"]
    effective_mode = stats.get("generation_mode")
    effective_depth = stats.get("mtp_depth", 0)
    if effective_mode != mode:
        raise RuntimeError(f"requested {mode}, served {effective_mode}")
    if mode == "mtp" and effective_depth != depth:
        raise RuntimeError(f"requested depth {depth}, served {effective_depth}")
    if stats.get("cached_tokens", 0) != 0:
        raise RuntimeError(f"cache bypass failed: cached_tokens={stats.get('cached_tokens')}")
    cache_source = stats.get("cache_source")
    if cache_source not in (None, "none"):
        raise RuntimeError(f"session/prefix cache was used: cache_source={cache_source}")
    if stats.get("ssd_cache_hit", False):
        raise RuntimeError("SSD session cache was used despite cache bypass")
    if stats.get("context_copy_active") is True:
        raise RuntimeError(
            "Context Copy is active; start the baseline server with MTPLX_CONTEXT_COPY=0"
        )
    generated = int(stats["generated_tokens"])
    decode_s = float(stats["decode_elapsed_s"])
    if generated < 1:
        raise RuntimeError(f"prefill probe generated no token: {generated}")
    if abs(float(stats["decode_tok_s"]) - generated / decode_s) > 1e-6:
        raise RuntimeError("server decode rate does not equal final tokens / decode time")

    text_bytes = text.encode("utf-8")
    row: dict[str, Any] = {
        "run": run,
        "target_prompt_tokens": target_prompt_tokens,
        "prompt_chars": len(prompt),
        "prompt_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "requested_mode": mode,
        "requested_depth": depth,
        "effective_mode": effective_mode,
        "effective_depth": effective_depth,
        "prompt_tokens": stats.get("prompt_tokens"),
        "generated_tokens": generated,
        "finish_reason": data["choices"][0].get("finish_reason"),
        "cached_tokens": stats.get("cached_tokens", 0),
        "cache_source": cache_source,
        "context_copy_active": stats.get("context_copy_active"),
        "context_copy_disabled_reason": stats.get("context_copy_disabled_reason"),
        "client_wall_s": client_wall_s,
        "server_request_elapsed_s": stats.get("request_elapsed_s"),
        "server_end_to_end_tok_s": stats.get("end_to_end_tok_s"),
        "server_decode_elapsed_s": decode_s,
        "server_decode_tok_s": stats.get("decode_tok_s"),
        "ttft_s": stats.get("ttft_s"),
        "prompt_eval_time_s": stats.get("prompt_eval_time_s"),
        "prompt_target_prefill_time_s": stats.get("prompt_target_prefill_time_s"),
        "prompt_mtp_history_time_s": stats.get("prompt_mtp_history_time_s"),
        "prompt_target_prefill_tok_s": stats.get("prompt_target_prefill_tok_s"),
        "prompt_tps": stats.get("prompt_tps"),
        "prefill_tok_s": stats.get("prefill_tok_s"),
        "prefill_compute_tok_s": stats.get("prefill_compute_tok_s"),
        "prefill_wall_tok_s": stats.get("prefill_wall_tok_s"),
        "prefill_route": stats.get("prefill_route"),
        "new_prefill_tokens": stats.get("new_prefill_tokens"),
        "active_memory_bytes": stats.get("active_memory_bytes"),
        "peak_memory_bytes": stats.get("peak_memory_bytes"),
        "output_sha256": hashlib.sha256(text_bytes).hexdigest(),
        "output_bytes": len(text_bytes),
    }
    for name in (
        "verify_calls",
        "drafted_tokens",
        "accepted_drafts",
        "rejected_drafts",
        "bonus_tokens",
        "draft_time_s",
        "verify_time_s",
        "target_forward_time_s",
        "verify_forward_time_s",
        "verify_eval_time_s",
        "accept_time_s",
        "context_copy_probes",
        "context_copy_rounds",
        "context_copy_accepted_tokens",
    ):
        row[name] = stats.get(name)
    return row


def metric(values: list[float | int | None]) -> dict[str, Any]:
    usable = [float(value) for value in values if value is not None]
    if not usable:
        return {
            "values": [],
            "mean": None,
            "median": None,
            "sample_stddev": None,
            "min": None,
            "max": None,
        }
    return {
        "values": usable,
        "mean": statistics.fmean(usable),
        "median": statistics.median(usable),
        "sample_stddev": statistics.stdev(usable) if len(usable) >= 2 else None,
        "min": min(usable),
        "max": max(usable),
    }


def summarize(rows: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[int, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                int(row["target_prompt_tokens"]),
                str(row["effective_mode"]),
                int(row["effective_depth"]),
            )
        ].append(row)
    groups: list[dict[str, Any]] = []
    for key in sorted(grouped):
        target, mode, depth = key
        selected = grouped[key]
        groups.append(
            {
                "target_prompt_tokens": target,
                "effective_mode": mode,
                "effective_depth": depth,
                "runs": len(selected),
                "actual_prompt_tokens": sorted({r["prompt_tokens"] for r in selected}),
                "generated_tokens": sorted({r["generated_tokens"] for r in selected}),
                "cache_bypass_ok": all(r["cached_tokens"] == 0 for r in selected),
                "prompt_tps": metric([r["prompt_tps"] for r in selected]),
                "prefill_tok_s": metric([r["prefill_tok_s"] for r in selected]),
                "prefill_compute_tok_s": metric(
                    [r["prefill_compute_tok_s"] for r in selected]
                ),
                "prefill_wall_tok_s": metric(
                    [r["prefill_wall_tok_s"] for r in selected]
                ),
                "prompt_eval_time_s": metric(
                    [r["prompt_eval_time_s"] for r in selected]
                ),
                "prompt_target_prefill_time_s": metric(
                    [r["prompt_target_prefill_time_s"] for r in selected]
                ),
                "prompt_mtp_history_time_s": metric(
                    [r["prompt_mtp_history_time_s"] for r in selected]
                ),
                "ttft_s": metric([r["ttft_s"] for r in selected]),
                "server_request_elapsed_s": metric(
                    [r["server_request_elapsed_s"] for r in selected]
                ),
                "server_decode_elapsed_s": metric(
                    [r["server_decode_elapsed_s"] for r in selected]
                ),
                "server_decode_tok_s": metric(
                    [r["server_decode_tok_s"] for r in selected]
                ),
                "client_wall_s": metric([r["client_wall_s"] for r in selected]),
                "peak_memory_bytes": metric([r["peak_memory_bytes"] for r in selected]),
                "prompt_sha256": sorted({r["prompt_sha256"] for r in selected}),
                "output_sha256": sorted({r["output_sha256"] for r in selected}),
            }
        )
    return {"metadata": metadata, "groups": groups}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:18038/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.8-27b-mtplx")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results" / "raw" / "prefill",
    )
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=1)
    parser.add_argument(
        "--targets",
        default="1024,2048,4096,8192",
        help="Approximate prompt-token targets, comma separated",
    )
    parser.add_argument(
        "--mode",
        choices=("ar", "mtp", "both"),
        default="ar",
        help="Prefill lane to measure; AR is the clean baseline",
    )
    parser.add_argument("--depth", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2")
    if args.max_tokens < 1:
        parser.error("--max-tokens must be positive")
    try:
        targets = tuple(int(v.strip()) for v in args.targets.split(",") if v.strip())
    except ValueError as exc:
        parser.error(f"invalid --targets: {exc}")
    if not targets or any(v < 1 for v in targets):
        parser.error("--targets must contain positive integers")
    if args.depth < 1:
        parser.error("--depth must be positive")

    model_lock = json.loads((REPO_ROOT / "model.lock.json").read_text(encoding="utf-8"))
    environment_lock = json.loads((REPO_ROOT / "environment.lock.json").read_text(encoding="utf-8"))
    system_info = json.loads((REPO_ROOT / "results" / "system.json").read_text(encoding="utf-8"))
    modes = [("ar", 0)] if args.mode == "ar" else [("mtp", args.depth)]
    if args.mode == "both":
        modes = [("ar", 0), ("mtp", args.depth)]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "raw-runs.jsonl"
    summary_path = args.output_dir / "summary.json"
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_url": args.api_url,
        "model_id": args.model,
        "model_repository": model_lock["repository"],
        "model_revision": model_lock["huggingface_revision"],
        "artifact_fingerprint": model_lock["mtplx_artifact_fingerprint"],
        "runtime": {
            "mtplx": environment_lock["mtplx"],
            "mlx": environment_lock["mlx"],
            "mlx_lm": environment_lock["mlx_lm"],
        },
        "hardware": {
            "chip": system_info["hardware"]["chip"],
            "gpu_cores": system_info["hardware"]["gpu_cores"],
            "unified_memory_gb": system_info["hardware"]["unified_memory_gb"],
        },
        "target_prompt_tokens_approx": list(targets),
        "modes": [{"mode": mode, "depth": depth} for mode, depth in modes],
        "runs_per_group": args.runs,
        "max_tokens": args.max_tokens,
        "sampling": {"temperature": 0, "top_p": 1, "top_k": 1, "seed": 123},
        "cache_mode": "bypass",
        "context_copy": "off required for baseline; enforced when server reports active",
        "ssd_session_cache": "off required at server startup",
        "prompt_generator": "deterministic ASCII blocks; server prompt_tokens is authoritative",
        "output_retention": "prompt/output SHA-256 and timing/statistics only",
    }

    print("Warming selected prefill paths (not measured)", flush=True)
    for mode, depth in modes:
        api_request(
            args.api_url,
            args.model,
            "Warmup only. Return one token.",
            mode,
            depth,
            args.max_tokens,
        )

    rows: list[dict[str, Any]] = []
    total = args.runs * len(targets) * len(modes)
    completed = 0
    for run in range(1, args.runs + 1):
        ordered_targets = list(targets)
        shift = (run - 1) % len(ordered_targets)
        ordered_targets = ordered_targets[shift:] + ordered_targets[:shift]
        if run % 2 == 0:
            ordered_targets.reverse()
        ordered_modes = list(modes)
        if run % 2 == 0:
            ordered_modes.reverse()
        for target in ordered_targets:
            prompt = make_prompt(target)
            for mode, depth in ordered_modes:
                data, wall_s = api_request(
                    args.api_url, args.model, prompt, mode, depth, args.max_tokens
                )
                row = sanitize(data, wall_s, target, prompt, run, mode, depth)
                rows.append(row)
                completed += 1
                print(
                    f"[{completed:02d}/{total}] run {run} target~{target} "
                    f"{mode} d{depth}: actual_prompt={row['prompt_tokens']} "
                    f"TTFT={row['ttft_s']} prompt_tps={row['prompt_tps']}",
                    flush=True,
                )

    with raw_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary_path.write_text(
        json.dumps(summarize(rows, metadata), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {raw_path} and {summary_path}", flush=True)


if __name__ == "__main__":
    main()
