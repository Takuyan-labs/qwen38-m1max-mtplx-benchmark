#!/usr/bin/env python3
"""Run the fixed content mix at AR and every native MTP depth.

This is deliberately separate from benchmark_content_mix.py: the published
content-mix result is an AR/D3 comparison, while this harness is an expensive
depth sweep (AR/D1/D2/D3).  It keeps the same cache-bypass, greedy request
contract and rotating order, and writes only hashes plus runtime statistics.
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
DEFAULT_PROMPTS = REPO_ROOT / "prompts" / "content-mix.json"


def request(
    url: str, model: str, prompt: str, mode: str, depth: int, tokens: int
) -> tuple[dict[str, Any], float]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": tokens,
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
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-MTPLX-Allow-Client-Controls": "1",
            "X-MTPLX-Cache-Mode": "bypass",
        },
    )
    started = time.perf_counter_ns()
    with urllib.request.urlopen(req, timeout=900) as response:
        data = json.load(response)
    return data, (time.perf_counter_ns() - started) / 1_000_000_000


def timing_fields(stats: dict[str, Any]) -> dict[str, Any]:
    """Copy optional server timings without inventing unavailable values."""
    names = (
        "draft_time_s",
        "verify_time_s",
        "target_forward_time_s",
        "verify_forward_time_s",
        "verify_eval_time_s",
        "accept_time_s",
        "commit_time_s",
        "capture_commit_time_s",
        "correction_time_s",
        "repair_time_s",
        "bonus_time_s",
        "lazy_bonus_commit_time_s",
        "snapshot_time_s",
        "rollback_time_s",
        "context_copy_probes",
        "context_copy_rounds",
        "context_copy_drafted_tokens",
        "context_copy_accepted_blocks",
        "context_copy_accepted_tokens",
        "compiled_verify_calls",
        "compiled_verify_fallback_calls",
        "active_memory_bytes",
        "peak_memory_bytes",
    )
    graph = stats.get("graphbank", {}).get("compiled_verify", {})
    row = {name: stats.get(name) for name in names}
    row["compiled_verify_calls"] = graph.get("compiled_calls", row["compiled_verify_calls"] or 0)
    row["compiled_verify_fallback_calls"] = graph.get(
        "fallback_calls", row["compiled_verify_fallback_calls"] or 0
    )
    return row


def sanitize(
    data: dict[str, Any],
    wall_s: float,
    content: dict[str, Any],
    run: int,
    mode: str,
    depth: int,
) -> dict[str, Any]:
    stats = data["mtplx_stats"]
    text = data["choices"][0]["message"]["content"]
    generated = stats["generated_tokens"]
    decode_s = stats["decode_elapsed_s"]
    decode_tps = stats["decode_tok_s"]
    if stats.get("generation_mode") != mode:
        raise RuntimeError(f"requested {mode}, served {stats.get('generation_mode')}")
    if mode == "mtp" and stats.get("mtp_depth") != depth:
        raise RuntimeError(f"requested depth {depth}, served {stats.get('mtp_depth')}")
    if stats.get("cached_tokens", 0) != 0:
        raise RuntimeError(f"cache bypass failed: cached_tokens={stats.get('cached_tokens')}")
    if abs(decode_tps - generated / decode_s) > 1e-6:
        raise RuntimeError("server decode rate does not equal final tokens / decode time")
    drafted = stats.get("drafted_tokens", 0) or 0
    accepted = stats.get("accepted_drafts", 0) or 0
    row: dict[str, Any] = {
        "content_id": content["id"],
        "content_label_en": content["label_en"],
        "content_label_ja": content["label_ja"],
        "content_kind": content["kind"],
        "run": run,
        "requested_mode": mode,
        "requested_depth": depth,
        "effective_mode": stats.get("generation_mode"),
        "effective_depth": stats.get("mtp_depth", 0),
        "prompt_tokens": stats.get("prompt_tokens"),
        "generated_tokens": generated,
        "finish_reason": data["choices"][0].get("finish_reason"),
        "cached_tokens": stats.get("cached_tokens", 0),
        "server_decode_elapsed_s": decode_s,
        "server_request_elapsed_s": stats.get("request_elapsed_s"),
        "server_decode_tok_s": decode_tps,
        "server_end_to_end_tok_s": stats.get("end_to_end_tok_s"),
        "client_wall_s": wall_s,
        "client_final_output_tok_s": generated / wall_s,
        "verify_calls": stats.get("verify_calls", 0),
        "drafted_tokens": drafted,
        "accepted_drafts": accepted,
        "rejected_drafts": stats.get("rejected_drafts", 0),
        "draft_acceptance": accepted / drafted if drafted else None,
        "bonus_tokens": stats.get("bonus_tokens", 0),
        "accepted_by_depth": stats.get("accepted_by_depth", []),
        "drafted_by_depth": stats.get("drafted_by_depth", []),
        "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "output_bytes": len(text.encode("utf-8")),
    }
    row.update(timing_fields(stats))
    return row


def metric(values: list[float | int | None]) -> dict[str, Any]:
    usable = [float(value) for value in values if value is not None]
    if not usable:
        return {"values": [], "mean": None, "median": None, "sample_stddev": None, "min": None, "max": None}
    return {
        "values": usable,
        "mean": statistics.fmean(usable),
        "median": statistics.median(usable),
        "sample_stddev": statistics.stdev(usable) if len(usable) >= 2 else None,
        "min": min(usable),
        "max": max(usable),
    }


def summarize(rows: list[dict[str, Any]], prompts: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["content_id"], row["effective_mode"], row["effective_depth"])].append(row)
    contents = []
    for content in prompts:
        modes = []
        for mode, depth in [("ar", 0), ("mtp", 1), ("mtp", 2), ("mtp", 3)]:
            selected = grouped[(content["id"], mode, depth)]
            modes.append(
                {
                    "mode": mode,
                    "depth": depth,
                    "runs": len(selected),
                    "decode_tok_s": metric([r["server_decode_tok_s"] for r in selected]),
                    "acceptance": metric([r["draft_acceptance"] for r in selected]) if mode == "mtp" else None,
                    "verify_calls": metric([r["verify_calls"] for r in selected]) if mode == "mtp" else None,
                    "final_tokens_per_verify": metric(
                        [r["generated_tokens"] / r["verify_calls"] for r in selected if r["verify_calls"]]
                    ) if mode == "mtp" else None,
                    "output_sha256": sorted({r["output_sha256"] for r in selected}),
                    "finish_reasons": sorted({r["finish_reason"] for r in selected}),
                }
            )
        all_hashes = {h for item in modes for h in item["output_sha256"]}
        contents.append({"id": content["id"], "label_ja": content["label_ja"], "modes": modes, "all_mode_hashes_identical": len(all_hashes) == 1})
    return {"metadata": metadata, "contents": contents}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:18038/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.8-27b-mtplx")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "results" / "raw" / "content-depths")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--tokens", type=int, default=512)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2")
    if args.tokens < 1:
        parser.error("--tokens must be positive")

    prompt_bytes = args.prompts.read_bytes()
    prompts = json.loads(prompt_bytes.decode("utf-8"))
    model_lock = json.loads((REPO_ROOT / "model.lock.json").read_text(encoding="utf-8"))
    environment_lock = json.loads((REPO_ROOT / "environment.lock.json").read_text(encoding="utf-8"))
    system_info = json.loads((REPO_ROOT / "results" / "system.json").read_text(encoding="utf-8"))
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
        "runtime": {"mtplx": environment_lock["mtplx"], "mlx": environment_lock["mlx"], "mlx_lm": environment_lock["mlx_lm"]},
        "hardware": {"chip": system_info["hardware"]["chip"], "gpu_cores": system_info["hardware"]["gpu_cores"], "unified_memory_gb": system_info["hardware"]["unified_memory_gb"]},
        "prompt_file": str(args.prompts.relative_to(REPO_ROOT)),
        "prompt_manifest_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "runs_per_content_mode_depth": args.runs,
        "max_tokens": args.tokens,
        "sampling": {"temperature": 0, "top_p": 1, "top_k": 1, "seed": 123},
        "cache_mode": "bypass",
        "modes": [{"mode": "ar", "depth": 0}, {"mode": "mtp", "depth": 1}, {"mode": "mtp", "depth": 2}, {"mode": "mtp", "depth": 3}],
        "run_order": "rotated content order; depth order rotates each run; AR/MTP order alternates",
        "output_retention": "SHA-256, byte counts, timings and runtime counters only",
    }

    print("Warming AR and MTP depth 1/2/3 paths (not measured)", flush=True)
    for mode, depth in (("ar", 0), ("mtp", 1), ("mtp", 2), ("mtp", 3)):
        request(args.api_url, args.model, "Write a numbered list of short computer facts.", mode, depth, 64)

    rows: list[dict[str, Any]] = []
    total = args.runs * len(prompts) * 4
    completed = 0
    for run in range(1, args.runs + 1):
        offset = (run - 1) % len(prompts)
        ordered = prompts[offset:] + prompts[:offset]
        if run % 2 == 0:
            ordered = list(reversed(ordered))
        depth_order = [("ar", 0), ("mtp", 1), ("mtp", 2), ("mtp", 3)]
        shift = (run - 1) % len(depth_order)
        depth_order = depth_order[shift:] + depth_order[:shift]
        if run % 2 == 0:
            depth_order = list(reversed(depth_order))
        for content in ordered:
            for mode, depth in depth_order:
                data, wall_s = request(args.api_url, args.model, content["prompt"], mode, depth, args.tokens)
                row = sanitize(data, wall_s, content, run, mode, depth)
                rows.append(row)
                completed += 1
                print(f"[{completed:02d}/{total}] run {run} {content['id']} {mode} d{depth}: {row['server_decode_tok_s']:.3f} tok/s", flush=True)

    with raw_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = summarize(rows, prompts, metadata)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {raw_path} and {summary_path}", flush=True)


if __name__ == "__main__":
    main()
