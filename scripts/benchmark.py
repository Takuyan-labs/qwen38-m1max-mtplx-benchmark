#!/usr/bin/env python3

import argparse
import hashlib
import json
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PROMPT = (
    "Output only valid Python code implementing merge sort, binary search, "
    "and deterministic unit tests."
)


def api_request(url: str, model: str, prompt: str, mode: str, depth: int, max_tokens: int) -> tuple[dict, float]:
    payload = {
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
    start_ns = time.perf_counter_ns()
    with urllib.request.urlopen(request, timeout=900) as response:
        data = json.load(response)
    client_wall_s = (time.perf_counter_ns() - start_ns) / 1_000_000_000
    return data, client_wall_s


def sanitized_row(data: dict, client_wall_s: float, stage: str, run: int, requested_mode: str, requested_depth: int) -> dict:
    stats = data["mtplx_stats"]
    text = data["choices"][0]["message"]["content"]
    text_bytes = text.encode("utf-8")
    graph = stats.get("graphbank", {}).get("compiled_verify", {})

    if stats.get("generation_mode") != requested_mode:
        raise RuntimeError(f"requested mode {requested_mode}, served {stats.get('generation_mode')}")
    if requested_mode == "mtp" and stats.get("mtp_depth") != requested_depth:
        raise RuntimeError(f"requested depth {requested_depth}, served {stats.get('mtp_depth')}")
    if stats.get("cached_tokens", 0) != 0:
        raise RuntimeError(f"cache bypass failed: cached_tokens={stats.get('cached_tokens')}")

    generated = stats["generated_tokens"]
    decode_elapsed = stats["decode_elapsed_s"]
    reported_decode = stats["decode_tok_s"]
    calculated_decode = generated / decode_elapsed
    if abs(reported_decode - calculated_decode) > 1e-6:
        raise RuntimeError("server decode throughput does not match tokens / decode_elapsed_s")

    return {
        "stage": stage,
        "run": run,
        "requested_mode": requested_mode,
        "requested_depth": requested_depth,
        "effective_mode": stats.get("generation_mode"),
        "effective_depth": stats.get("mtp_depth", 0),
        "prompt_tokens": stats.get("prompt_tokens"),
        "generated_tokens": generated,
        "finish_reason": data["choices"][0].get("finish_reason"),
        "cache_source": stats.get("cache_source"),
        "cached_tokens": stats.get("cached_tokens", 0),
        "server_decode_elapsed_s": decode_elapsed,
        "server_request_elapsed_s": stats.get("request_elapsed_s"),
        "server_decode_tok_s": reported_decode,
        "server_end_to_end_tok_s": stats.get("end_to_end_tok_s"),
        "calculated_decode_tok_s": calculated_decode,
        "client_wall_s": client_wall_s,
        "client_final_output_tok_s": generated / client_wall_s,
        "verify_calls": stats.get("verify_calls"),
        "accepted_drafts": stats.get("accepted_drafts"),
        "rejected_drafts": stats.get("rejected_drafts"),
        "drafted_tokens": stats.get("drafted_tokens"),
        "bonus_tokens": stats.get("bonus_tokens"),
        "accepted_by_depth": stats.get("accepted_by_depth", []),
        "drafted_by_depth": stats.get("drafted_by_depth", []),
        "mean_accept_probability_by_depth": stats.get("mean_accept_probability_by_depth", []),
        "compiled_verify_calls": graph.get("compiled_calls", 0),
        "compiled_verify_fallback_calls": graph.get("fallback_calls", 0),
        "active_memory_bytes": stats.get("active_memory_bytes"),
        "peak_memory_bytes": stats.get("peak_memory_bytes"),
        "output_sha256": hashlib.sha256(text_bytes).hexdigest(),
        "output_bytes": len(text_bytes),
    }


def summarize(rows: list[dict], metadata: dict) -> dict:
    parity = [row for row in rows if row["stage"] == "parity"]
    speed = [row for row in rows if row["stage"] == "speed"]

    modes: dict[str, dict] = {}
    for mode in ("ar", "mtp-d3"):
        selected = [row for row in speed if (row["effective_mode"] == "ar") == (mode == "ar")]
        values = [row["server_decode_tok_s"] for row in selected]
        client_values = [row["client_final_output_tok_s"] for row in selected]
        modes[mode] = {
            "runs": len(values),
            "server_decode_tok_s": values,
            "mean_server_decode_tok_s": statistics.fmean(values),
            "median_server_decode_tok_s": statistics.median(values),
            "sample_stddev_server_decode_tok_s": statistics.stdev(values),
            "sample_cv_percent": statistics.stdev(values) / statistics.fmean(values) * 100,
            "min_server_decode_tok_s": min(values),
            "max_server_decode_tok_s": max(values),
            "median_client_final_output_tok_s": statistics.median(client_values),
        }

    return {
        "metadata": metadata,
        "parity": {
            "rows": parity,
            "outputs_identical": len({row["output_sha256"] for row in parity}) == 1,
        },
        "speed": modes,
        "median_speedup_d3_vs_ar": (
            modes["mtp-d3"]["median_server_decode_tok_s"]
            / modes["ar"]["median_server_decode_tok_s"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:18038/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.8-27b-mtplx")
    parser.add_argument(
        "--output-dir",
        default="results/raw",
        help="Destination for a local run (default: ignored results/raw)",
    )
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--tokens", type=int, default=512)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    if args.runs < 2:
        parser.error("--runs must be at least 2 so sample statistics are defined")
    if args.tokens < 1:
        parser.error("--tokens must be positive")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "raw-runs.jsonl"

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_url": args.api_url,
        "model_id": args.model,
        "prompt": args.prompt,
        "max_tokens": args.tokens,
        "sampling": {"temperature": 0, "top_p": 1, "top_k": 1, "seed": 123},
        "cache_mode": "bypass",
        "run_order": "parity AR/D1/D2/D3, then speed ABBA-balanced AR/D3",
    }

    print("Warming compilation paths (not measured)", flush=True)
    for mode, depth in (("ar", 0), ("mtp", 1), ("mtp", 2), ("mtp", 3)):
        api_request(args.api_url, args.model, "Write short computer facts.", mode, depth, 64)

    rows: list[dict] = []
    print("Running parity ablation", flush=True)
    for index, (mode, depth) in enumerate((("ar", 0), ("mtp", 1), ("mtp", 2), ("mtp", 3)), 1):
        data, wall = api_request(args.api_url, args.model, args.prompt, mode, depth, args.tokens)
        row = sanitized_row(data, wall, "parity", index, mode, depth)
        rows.append(row)
        print(f"  {mode} d{depth}: {row['server_decode_tok_s']:.3f} tok/s", flush=True)

    base_order = [("ar", 0), ("mtp", 3), ("mtp", 3), ("ar", 0)]
    speed_order = []
    while sum(1 for mode, _ in speed_order if mode == "ar") < args.runs:
        speed_order.extend(base_order)
    ar_seen = d3_seen = 0
    trimmed_order = []
    for mode, depth in speed_order:
        if mode == "ar" and ar_seen < args.runs:
            trimmed_order.append((mode, depth)); ar_seen += 1
        elif mode == "mtp" and d3_seen < args.runs:
            trimmed_order.append((mode, depth)); d3_seen += 1
        if ar_seen == args.runs and d3_seen == args.runs:
            break

    print("Running interleaved AR/D3 speed trials", flush=True)
    for index, (mode, depth) in enumerate(trimmed_order, 1):
        data, wall = api_request(args.api_url, args.model, args.prompt, mode, depth, args.tokens)
        row = sanitized_row(data, wall, "speed", index, mode, depth)
        rows.append(row)
        print(f"  {index:02d} {mode} d{depth}: {row['server_decode_tok_s']:.3f} tok/s", flush=True)

    with raw_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = summarize(rows, metadata)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["speed"], ensure_ascii=False, indent=2))
    print(f"Median D3/AR speedup: {summary['median_speedup_d3_vs_ar']:.3f}x")
    print(f"Saved {raw_path} and {summary_path}")


if __name__ == "__main__":
    main()
