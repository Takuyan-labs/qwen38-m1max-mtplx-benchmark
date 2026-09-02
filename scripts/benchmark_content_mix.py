#!/usr/bin/env python3

import argparse
import hashlib
import json
import statistics
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPTS = REPO_ROOT / "prompts" / "content-mix.json"


def api_request(url: str, model: str, prompt: str, mode: str, depth: int, tokens: int) -> tuple[dict, float]:
    payload = {
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
    client_wall_s = (time.perf_counter_ns() - started) / 1_000_000_000
    return data, client_wall_s


def sanitize(data: dict, client_wall_s: float, content: dict, run: int, mode: str, depth: int) -> dict:
    stats = data["mtplx_stats"]
    text = data["choices"][0]["message"]["content"]
    text_bytes = text.encode("utf-8")
    graph = stats.get("graphbank", {}).get("compiled_verify", {})

    if stats.get("generation_mode") != mode:
        raise RuntimeError(f"requested {mode}, served {stats.get('generation_mode')}")
    if mode == "mtp" and stats.get("mtp_depth") != depth:
        raise RuntimeError(f"requested depth {depth}, served {stats.get('mtp_depth')}")
    if stats.get("cached_tokens", 0) != 0:
        raise RuntimeError(f"cache bypass failed: {stats.get('cached_tokens')} cached tokens")

    generated = stats["generated_tokens"]
    decode_elapsed = stats["decode_elapsed_s"]
    calculated_decode = generated / decode_elapsed
    if abs(stats["decode_tok_s"] - calculated_decode) > 1e-6:
        raise RuntimeError("server decode rate does not equal final tokens / decode time")

    drafted = stats.get("drafted_tokens", 0)
    accepted = stats.get("accepted_drafts", 0)
    characters = len(text)
    non_whitespace = sum(not char.isspace() for char in text)

    return {
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
        "cache_source": stats.get("cache_source"),
        "cached_tokens": stats.get("cached_tokens", 0),
        "server_decode_elapsed_s": decode_elapsed,
        "server_request_elapsed_s": stats.get("request_elapsed_s"),
        "server_decode_tok_s": stats["decode_tok_s"],
        "server_end_to_end_tok_s": stats.get("end_to_end_tok_s"),
        "calculated_decode_tok_s": calculated_decode,
        "client_wall_s": client_wall_s,
        "client_final_output_tok_s": generated / client_wall_s,
        "output_characters": characters,
        "output_non_whitespace_characters": non_whitespace,
        "output_characters_per_decode_s": characters / decode_elapsed,
        "output_bytes": len(text_bytes),
        "output_sha256": hashlib.sha256(text_bytes).hexdigest(),
        "verify_calls": stats.get("verify_calls"),
        "drafted_tokens": drafted,
        "accepted_drafts": accepted,
        "draft_acceptance": accepted / drafted if drafted else None,
        "bonus_tokens": stats.get("bonus_tokens"),
        "accepted_by_depth": stats.get("accepted_by_depth", []),
        "drafted_by_depth": stats.get("drafted_by_depth", []),
        "mean_accept_probability_by_depth": stats.get("mean_accept_probability_by_depth", []),
        "compiled_verify_calls": graph.get("compiled_calls", 0),
        "compiled_verify_fallback_calls": graph.get("fallback_calls", 0),
        "active_memory_bytes": stats.get("active_memory_bytes"),
        "peak_memory_bytes": stats.get("peak_memory_bytes"),
    }


def metric_summary(values: list[float]) -> dict:
    return {
        "values": values,
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "sample_stddev": statistics.stdev(values),
        "min": min(values),
        "max": max(values),
    }


def summarize(rows: list[dict], prompts: list[dict], metadata: dict) -> dict:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["content_id"], row["effective_mode"])].append(row)

    contents = []
    for content in prompts:
        modes = {}
        for mode in ("ar", "mtp"):
            selected = grouped[(content["id"], mode)]
            modes[mode] = {
                "runs": len(selected),
                "decode_tok_s": metric_summary([row["server_decode_tok_s"] for row in selected]),
                "client_final_output_tok_s": metric_summary(
                    [row["client_final_output_tok_s"] for row in selected]
                ),
                "output_characters_per_decode_s": metric_summary(
                    [row["output_characters_per_decode_s"] for row in selected]
                ),
                "prompt_tokens": sorted({row["prompt_tokens"] for row in selected}),
                "generated_tokens": sorted({row["generated_tokens"] for row in selected}),
                "finish_reasons": sorted({row["finish_reason"] for row in selected}),
                "output_sha256": sorted({row["output_sha256"] for row in selected}),
            }
            if mode == "mtp":
                modes[mode]["draft_acceptance"] = metric_summary(
                    [row["draft_acceptance"] for row in selected]
                )
                modes[mode]["verify_calls"] = metric_summary(
                    [row["verify_calls"] for row in selected]
                )
                modes[mode]["compiled_verify_fallback_calls"] = sum(
                    row["compiled_verify_fallback_calls"] for row in selected
                )

        ar_median = modes["ar"]["decode_tok_s"]["median"]
        d3_median = modes["mtp"]["decode_tok_s"]["median"]
        all_hashes = set(modes["ar"]["output_sha256"]) | set(modes["mtp"]["output_sha256"])
        contents.append(
            {
                "id": content["id"],
                "label_en": content["label_en"],
                "label_ja": content["label_ja"],
                "kind": content["kind"],
                "modes": modes,
                "median_speedup_d3_vs_ar": d3_median / ar_median,
                "greedy_output_identical_across_all_runs_and_modes": len(all_hashes) == 1,
            }
        )

    return {"metadata": metadata, "contents": contents}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:18038/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.8-27b-mtplx")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results" / "raw" / "content-mix",
        help="Destination for a local run (default: ignored results/raw/content-mix)",
    )
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
        "prompt_file": str(args.prompts.relative_to(REPO_ROOT)),
        "prompt_manifest_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "runs_per_content_and_mode": args.runs,
        "max_tokens": args.tokens,
        "sampling": {"temperature": 0, "top_p": 1, "top_k": 1, "seed": 123},
        "cache_mode": "bypass",
        "modes": [{"mode": "ar", "depth": 0}, {"mode": "mtp", "depth": 3}],
        "run_order": "rotated content order; AR/D3 order alternates each round",
        "output_retention": "SHA-256, byte and character counts only; generated text is not retained",
    }

    print("Warming AR and MTP D3 compilation paths (not measured)", flush=True)
    warm_prompt = "Write a numbered list of short computer facts."
    for mode, depth in (("ar", 0), ("mtp", 3)):
        api_request(args.api_url, args.model, warm_prompt, mode, depth, 64)

    rows = []
    total = args.runs * len(prompts) * 2
    completed = 0
    for run in range(1, args.runs + 1):
        offset = (run - 1) % len(prompts)
        ordered = prompts[offset:] + prompts[:offset]
        if run % 2 == 0:
            ordered = list(reversed(ordered))
        modes = (("ar", 0), ("mtp", 3)) if run % 2 else (("mtp", 3), ("ar", 0))
        for content in ordered:
            for mode, depth in modes:
                data, client_wall_s = api_request(
                    args.api_url, args.model, content["prompt"], mode, depth, args.tokens
                )
                row = sanitize(data, client_wall_s, content, run, mode, depth)
                rows.append(row)
                completed += 1
                print(
                    f"[{completed:02d}/{total}] run {run} {content['id']} {mode} d{depth}: "
                    f"{row['server_decode_tok_s']:.3f} tok/s, "
                    f"{row['output_characters_per_decode_s']:.1f} char/s",
                    flush=True,
                )

    with raw_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = summarize(rows, prompts, metadata)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for content in summary["contents"]:
        ar = content["modes"]["ar"]["decode_tok_s"]
        d3 = content["modes"]["mtp"]["decode_tok_s"]
        print(
            f"{content['id']}: AR median {ar['median']:.3f}; "
            f"D3 median {d3['median']:.3f}, max {d3['max']:.3f}; "
            f"{content['median_speedup_d3_vs_ar']:.2f}x",
            flush=True,
        )
    print(f"Saved {raw_path} and {summary_path}", flush=True)


if __name__ == "__main__":
    main()
