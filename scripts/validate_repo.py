#!/usr/bin/env python3

import json
import math
import re
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".sh", ".json", ".yml", ".yaml", ".cff", ".txt"}
FORBIDDEN = {
    # Split the literal so this validator does not flag its own source.
    "absolute user path": re.compile(r"/" + r"Users/[^/]+/"),
    "bearer credential": re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}"),
    "GitHub token": re.compile(r"gh[opsu]_[A-Za-z0-9_]+"),
    "UUID value": re.compile(r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b"),
    "hardware UUID key": re.compile(r"[\"']hardware_uuid[\"']\s*:", re.I),
    "serial number key": re.compile(r"[\"']serial_number[\"']\s*:", re.I),
    "provisioning UDID key": re.compile(r"[\"']provisioning_udid[\"']\s*:", re.I),
}


def require_close(errors: list[str], label: str, actual: float, expected: float) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        errors.append(f"{label} mismatch: {actual!r} != {expected!r}")


def validate_formal_results(errors: list[str]) -> None:
    raw_path = ROOT / "results/formal/raw-runs.jsonl"
    summary_path = ROOT / "results/formal/summary.json"
    try:
        rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"could not load formal results: {exc}")
        return

    parity = [row for row in rows if row.get("stage") == "parity"]
    speed = [row for row in rows if row.get("stage") == "speed"]
    if len(parity) != 4:
        errors.append(f"formal parity row count is {len(parity)}, expected 4")
    if len(speed) != 10:
        errors.append(f"formal speed row count is {len(speed)}, expected 10")
    if len({row.get("output_sha256") for row in parity}) != 1:
        errors.append("formal parity output hashes differ")
    if not summary.get("parity", {}).get("outputs_identical"):
        errors.append("formal summary does not report identical parity output")

    for row in rows:
        if row.get("cached_tokens") != 0 or row.get("cache_source") != "none":
            errors.append(f"cache bypass evidence failed at {row.get('stage')} run {row.get('run')}")
        if row.get("generated_tokens") != 512 or row.get("finish_reason") != "length":
            errors.append(f"fixed-length evidence failed at {row.get('stage')} run {row.get('run')}")
        calculated = row["generated_tokens"] / row["server_decode_elapsed_s"]
        require_close(
            errors,
            f"calculated decode at {row.get('stage')} run {row.get('run')}",
            row["server_decode_tok_s"],
            calculated,
        )

    mode_rows = {
        "ar": [row for row in speed if row.get("effective_mode") == "ar"],
        "mtp-d3": [
            row
            for row in speed
            if row.get("effective_mode") == "mtp" and row.get("effective_depth") == 3
        ],
    }
    for mode, selected in mode_rows.items():
        values = [row["server_decode_tok_s"] for row in selected]
        clients = [row["client_final_output_tok_s"] for row in selected]
        published = summary.get("speed", {}).get(mode, {})
        if len(values) != 5 or published.get("runs") != 5:
            errors.append(f"formal {mode} run count is not 5")
            continue
        calculations = {
            "mean_server_decode_tok_s": statistics.fmean(values),
            "median_server_decode_tok_s": statistics.median(values),
            "sample_stddev_server_decode_tok_s": statistics.stdev(values),
            "sample_cv_percent": statistics.stdev(values) / statistics.fmean(values) * 100,
            "min_server_decode_tok_s": min(values),
            "max_server_decode_tok_s": max(values),
            "median_client_final_output_tok_s": statistics.median(clients),
        }
        if published.get("server_decode_tok_s") != values:
            errors.append(f"formal {mode} raw value list differs from summary")
        for field, value in calculations.items():
            require_close(errors, f"formal {mode} {field}", published[field], value)

    if all(len(selected) == 5 for selected in mode_rows.values()):
        speedup = statistics.median(
            row["server_decode_tok_s"] for row in mode_rows["mtp-d3"]
        ) / statistics.median(row["server_decode_tok_s"] for row in mode_rows["ar"])
        require_close(
            errors,
            "formal median speedup",
            summary["median_speedup_d3_vs_ar"],
            speedup,
        )


def main() -> None:
    errors = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if relative.parts[:2] == ("results", "raw") and path.name != ".gitkeep":
            continue
        if path.stat().st_size > 5_000_000:
            errors.append(f"file exceeds 5 MB: {relative}")
        if path.suffix == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"invalid JSON {relative}: {exc}")
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    json.loads(line)
                except Exception as exc:
                    errors.append(f"invalid JSONL {relative}:{line_number}: {exc}")
        if path.suffix in TEXT_SUFFIXES or path.name in {"LICENSE", ".gitignore"}:
            text = path.read_text(encoding="utf-8")
            for label, pattern in FORBIDDEN.items():
                if pattern.search(text):
                    errors.append(f"{label} found in {relative}")

    validate_formal_results(errors)

    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Repository validation passed")


if __name__ == "__main__":
    main()
