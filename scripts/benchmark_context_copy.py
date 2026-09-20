#!/usr/bin/env python3
"""Bounded Context Copy A/B for rewrite/edit workloads.

Run this script against two freshly started servers: once with the stock
Context Copy path and once with MTPLX_CONTEXT_COPY=0.  The prompt is
deliberately separate from the fresh-code benchmark: it asks the model to
re-emit an existing file while making one small edit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROMPT = '''Output only the complete edited Python file, with no Markdown fences.
Preserve every unchanged line byte-for-byte. Rename the function `add` to
`sum_two` and update its one call site; do not make any other change.

from __future__ import annotations

def add(left: int, right: int) -> int:
    return left + right

def subtract(left: int, right: int) -> int:
    return left - right

def multiply(left: int, right: int) -> int:
    return left * right

def divide(left: int, right: int) -> float:
    if right == 0:
        raise ValueError("division by zero")
    return left / right

def main() -> None:
    values = [add(2, 3), subtract(9, 4), multiply(3, 7)]
    print(values)

if __name__ == "__main__":
    main()
'''


def request(url: str, model: str, tokens: int) -> tuple[dict, float]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": tokens,
        "temperature": 0,
        "top_p": 1,
        "top_k": 1,
        "seed": 123,
        "stream": False,
        "enable_thinking": False,
        "generation_mode": "mtp",
        "depth": 3,
        "metadata": {"cache_mode": "bypass", "allow_client_controls": True},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-MTPLX-Allow-Client-Controls": "1",
            "X-MTPLX-Cache-Mode": "bypass",
        },
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as response:
        data = json.load(response)
    return data, time.perf_counter() - start


def row(data: dict, wall: float, run: int) -> dict:
    stats = data["mtplx_stats"]
    text = data["choices"][0]["message"]["content"]
    generated = stats["generated_tokens"]
    decode_s = stats["decode_elapsed_s"]
    return {
        "run": run,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "generated_tokens": generated,
        "finish_reason": data["choices"][0].get("finish_reason"),
        "decode_elapsed_s": decode_s,
        "decode_tok_s": stats["decode_tok_s"],
        "client_wall_s": wall,
        "client_final_output_tok_s": generated / wall,
        "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "output_bytes": len(text.encode()),
        "contains_sum_two": "def sum_two" in text and "sum_two(2, 3)" in text,
        "contains_old_call": "add(2, 3)" in text,
        "cached_tokens": stats.get("cached_tokens", 0),
        "verify_calls": stats.get("verify_calls"),
        "drafted_tokens": stats.get("drafted_tokens"),
        "accepted_drafts": stats.get("accepted_drafts"),
        "draft_acceptance": (
            stats.get("accepted_drafts") / stats.get("drafted_tokens")
            if stats.get("drafted_tokens") else None
        ),
        "context_copy_probes": stats.get("context_copy_probes"),
        "context_copy_rounds": stats.get("context_copy_rounds"),
        "context_copy_drafted_tokens": stats.get("context_copy_drafted_tokens"),
        "context_copy_accepted_blocks": stats.get("context_copy_accepted_blocks"),
        "context_copy_accepted_tokens": stats.get("context_copy_accepted_tokens"),
        "peak_memory_bytes": stats.get("peak_memory_bytes"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:18211/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.8-27b-mtplx")
    parser.add_argument("--label", required=True, help="on or off")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--tokens", type=int, default=256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for run in range(1, args.runs + 1):
        data, wall = request(args.api_url, args.model, args.tokens)
        current = row(data, wall, run)
        current["label"] = args.label
        rows.append(current)
        print(f"{args.label} {run}: {current['decode_tok_s']:.3f} tok/s copy_rounds={current['context_copy_rounds']}", flush=True)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "prompt": PROMPT,
        "runs": len(rows),
        "decode_tok_s": {
            "values": [r["decode_tok_s"] for r in rows],
            "mean": statistics.fmean(r["decode_tok_s"] for r in rows),
            "median": statistics.median(r["decode_tok_s"] for r in rows),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
