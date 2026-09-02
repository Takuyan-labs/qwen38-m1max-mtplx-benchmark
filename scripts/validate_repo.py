#!/usr/bin/env python3

import hashlib
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
EXPECTED_OUTPUT_SHA256 = "f6b04bacf2d8010b6053818dc193678ca1a7e8cf083f3347a4f7000e96cf0a9a"


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


def validate_content_mix_results(errors: list[str]) -> None:
    result_dir = ROOT / "results/content-mix-2026-09-01"
    raw_path = result_dir / "raw-runs.jsonl"
    summary_path = result_dir / "summary.json"
    prompt_path = ROOT / "prompts/content-mix.json"
    try:
        rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        prompt_bytes = prompt_path.read_bytes()
        prompts = json.loads(prompt_bytes.decode("utf-8"))
        model_lock = json.loads((ROOT / "model.lock.json").read_text(encoding="utf-8"))
        environment_lock = json.loads((ROOT / "environment.lock.json").read_text(encoding="utf-8"))
        system_info = json.loads((ROOT / "results/system.json").read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"could not load content-mix evidence: {exc}")
        return

    metadata = summary.get("metadata", {})
    if metadata.get("model_repository") != model_lock.get("repository"):
        errors.append("content-mix model repository does not match model.lock.json")
    if metadata.get("model_revision") != model_lock.get("huggingface_revision"):
        errors.append("content-mix model revision does not match model.lock.json")
    if metadata.get("artifact_fingerprint") != model_lock.get("mtplx_artifact_fingerprint"):
        errors.append("content-mix artifact fingerprint does not match model.lock.json")
    expected_runtime = {
        "mtplx": environment_lock.get("mtplx"),
        "mlx": environment_lock.get("mlx"),
        "mlx_lm": environment_lock.get("mlx_lm"),
    }
    if metadata.get("runtime") != expected_runtime:
        errors.append("content-mix runtime versions do not match environment.lock.json")
    expected_hardware = {
        "chip": system_info.get("hardware", {}).get("chip"),
        "gpu_cores": system_info.get("hardware", {}).get("gpu_cores"),
        "unified_memory_gb": system_info.get("hardware", {}).get("unified_memory_gb"),
    }
    if metadata.get("hardware") != expected_hardware:
        errors.append("content-mix hardware does not match results/system.json")
    prompt_hash = hashlib.sha256(prompt_bytes).hexdigest()
    if metadata.get("prompt_manifest_sha256") != prompt_hash:
        errors.append("content-mix prompt manifest hash does not match prompts/content-mix.json")

    expected_ids = [
        "japanese-prose",
        "english-prose",
        "chinese-prose",
        "python-code",
    ]
    if [prompt.get("id") for prompt in prompts] != expected_ids:
        errors.append("content-mix prompt manifest has unexpected IDs or order")
    if len(rows) != 40:
        errors.append(f"content-mix row count is {len(rows)}, expected 40")

    expected_schedule = []
    for run in range(1, 6):
        offset = (run - 1) % len(prompts)
        ordered = prompts[offset:] + prompts[:offset]
        if run % 2 == 0:
            ordered = list(reversed(ordered))
        modes = (("ar", 0), ("mtp", 3)) if run % 2 else (("mtp", 3), ("ar", 0))
        for content in ordered:
            for mode, depth in modes:
                expected_schedule.append((run, content["id"], mode, depth))
    actual_schedule = [
        (row.get("run"), row.get("content_id"), row.get("effective_mode"), row.get("effective_depth"))
        for row in rows
    ]
    if actual_schedule != expected_schedule:
        errors.append("content-mix raw row order does not match the published rotated schedule")

    for row in rows:
        label = f"content-mix {row.get('content_id')} {row.get('effective_mode')} run {row.get('run')}"
        if any(key in row for key in ("text", "response", "output_text", "message")):
            errors.append(f"generated response text field found at {label}")
        if row.get("content_id") not in expected_ids:
            errors.append(f"unexpected content ID at {label}")
        if row.get("generated_tokens") != 512 or row.get("finish_reason") != "length":
            errors.append(f"fixed-length evidence failed at {label}")
        if row.get("cached_tokens") != 0 or row.get("cache_source") != "none":
            errors.append(f"cache bypass evidence failed at {label}")
        if row.get("requested_mode") != row.get("effective_mode"):
            errors.append(f"mode mismatch at {label}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("output_sha256", ""))):
            errors.append(f"invalid output SHA-256 at {label}")
        if row.get("output_bytes", 0) <= 0 or row.get("output_characters", 0) <= 0:
            errors.append(f"invalid output size evidence at {label}")
        if row.get("effective_mode") == "ar" and row.get("effective_depth") != 0:
            errors.append(f"AR depth mismatch at {label}")
        if row.get("effective_mode") == "mtp":
            if row.get("effective_depth") != 3:
                errors.append(f"MTP depth mismatch at {label}")
            if row.get("compiled_verify_fallback_calls") != 0:
                errors.append(f"compiled verification fallback at {label}")
            accepted_by_depth = row.get("accepted_by_depth", [])
            drafted_by_depth = row.get("drafted_by_depth", [])
            if len(accepted_by_depth) != 3 or len(drafted_by_depth) != 3:
                errors.append(f"MTP depth arrays are not length 3 at {label}")
            elif any(drafted <= 0 for drafted in drafted_by_depth):
                errors.append(f"invalid drafted-by-depth count at {label}")
            else:
                if sum(accepted_by_depth) != row.get("accepted_drafts"):
                    errors.append(f"accepted draft total mismatch at {label}")
                if sum(drafted_by_depth) != row.get("drafted_tokens"):
                    errors.append(f"drafted token total mismatch at {label}")
                require_close(
                    errors,
                    f"draft acceptance at {label}",
                    row["draft_acceptance"],
                    row["accepted_drafts"] / row["drafted_tokens"],
                )
                depth_probabilities = row.get("mean_accept_probability_by_depth", [])
                if len(depth_probabilities) != 3:
                    errors.append(f"acceptance probability array is not length 3 at {label}")
                else:
                    for depth, (accepted, drafted, probability) in enumerate(
                        zip(accepted_by_depth, drafted_by_depth, depth_probabilities), 1
                    ):
                        require_close(
                            errors,
                            f"depth {depth} acceptance at {label}",
                            probability,
                            accepted / drafted,
                        )
        calculated = row["generated_tokens"] / row["server_decode_elapsed_s"]
        require_close(errors, f"calculated decode at {label}", row["server_decode_tok_s"], calculated)

    published_by_id = {content.get("id"): content for content in summary.get("contents", [])}
    if set(published_by_id) != set(expected_ids):
        errors.append("content-mix summary has unexpected content IDs")
        return

    for content_id in expected_ids:
        selected = [row for row in rows if row.get("content_id") == content_id]
        hashes = {row.get("output_sha256") for row in selected}
        if len(hashes) != 1:
            errors.append(f"content-mix output hashes differ for {content_id}")
        published = published_by_id[content_id]
        if not published.get("greedy_output_identical_across_all_runs_and_modes"):
            errors.append(f"content-mix summary parity flag is false for {content_id}")

        medians = {}
        for mode in ("ar", "mtp"):
            mode_rows = [row for row in selected if row.get("effective_mode") == mode]
            if len(mode_rows) != 5:
                errors.append(f"content-mix {content_id} {mode} run count is {len(mode_rows)}, expected 5")
                continue
            if {row.get("run") for row in mode_rows} != set(range(1, 6)):
                errors.append(f"content-mix {content_id} {mode} run numbers are not exactly 1 through 5")
            values = [row["server_decode_tok_s"] for row in mode_rows]
            clients = [row["client_final_output_tok_s"] for row in mode_rows]
            chars = [row["output_characters_per_decode_s"] for row in mode_rows]
            mode_summary = published["modes"][mode]
            if mode_summary.get("runs") != 5:
                errors.append(f"content-mix summary run count mismatch for {content_id} {mode}")
            if mode_summary["decode_tok_s"].get("values") != values:
                errors.append(f"content-mix raw speed list differs from summary for {content_id} {mode}")
            for metric, metric_values in (
                ("decode_tok_s", values),
                ("client_final_output_tok_s", clients),
                ("output_characters_per_decode_s", chars),
            ):
                calculations = {
                    "mean": statistics.fmean(metric_values),
                    "median": statistics.median(metric_values),
                    "sample_stddev": statistics.stdev(metric_values),
                    "min": min(metric_values),
                    "max": max(metric_values),
                }
                if mode_summary[metric].get("values") != metric_values:
                    errors.append(f"content-mix raw {metric} list differs for {content_id} {mode}")
                for field, value in calculations.items():
                    require_close(
                        errors,
                        f"content-mix {content_id} {mode} {metric} {field}",
                        mode_summary[metric][field],
                        value,
                    )
                if metric == "decode_tok_s":
                    medians[mode] = calculations["median"]

            if mode == "mtp":
                acceptance = [row["draft_acceptance"] for row in mode_rows]
                verify_calls = [row["verify_calls"] for row in mode_rows]
                for metric, metric_values in (
                    ("draft_acceptance", acceptance),
                    ("verify_calls", verify_calls),
                ):
                    metric_summary = mode_summary[metric]
                    if metric_summary.get("values") != metric_values:
                        errors.append(f"content-mix raw {metric} list differs for {content_id}")
                    calculations = {
                        "mean": statistics.fmean(metric_values),
                        "median": statistics.median(metric_values),
                        "sample_stddev": statistics.stdev(metric_values),
                        "min": min(metric_values),
                        "max": max(metric_values),
                    }
                    for field, value in calculations.items():
                        require_close(
                            errors,
                            f"content-mix {content_id} {metric} {field}",
                            metric_summary[field],
                            value,
                        )
                fallback_sum = sum(row["compiled_verify_fallback_calls"] for row in mode_rows)
                if mode_summary.get("compiled_verify_fallback_calls") != fallback_sum:
                    errors.append(f"content-mix fallback sum differs for {content_id}")

        if set(medians) == {"ar", "mtp"}:
            require_close(
                errors,
                f"content-mix {content_id} median speedup",
                published["median_speedup_d3_vs_ar"],
                medians["mtp"] / medians["ar"],
            )


def validate_license_defenses(errors: list[str]) -> None:
    required_text = {
        "README.md": [
            "Powered by MTPLX by Youssof Altoukhi",
            "THIRD_PARTY_NOTICES.md",
            "results/README.md",
            "Japanese technical prose",
            "33.05",
        ],
        "README.ja.md": [
            "Powered by MTPLX by Youssof Altoukhi",
            "THIRD_PARTY_NOTICES.md",
            "results/README.md",
            "日本語の技術文",
            "33.05",
        ],
        "docs/article-ja.md": [
            "Powered by MTPLX by Youssof Altoukhi",
            "MTPLX/blob/v2.9.0/NOTICE",
            "日本語・英語・中国語・コードの40回比較",
            "18.67",
        ],
        "THIRD_PARTY_NOTICES.md": [
            "Qwen3.8-27B/blob/main/LICENSE",
            "MTPLX/blob/v2.9.0/LICENSE",
            "MTPLX/blob/v2.9.0/NOTICE",
            "Powered by MTPLX by Youssof Altoukhi",
            "MLX",
            "mlx-lm",
        ],
        "scripts/start_server.sh": [
            "Powered by MTPLX by Youssof Altoukhi",
            "https://github.com/youssofal/MTPLX",
            "MTPLX_HOST",
            "MTPLX_PORT",
        ],
        "results/README.md": [
            "does not claim authorship or ownership of text generated by Qwen",
            "do not contain generated response text",
        ],
    }
    for relative, fragments in required_text.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                errors.append(f"required license defense missing from {relative}: {fragment}")

    burst_dir = ROOT / "results/burst-2026-08-31"
    raw_files = sorted(path for path in burst_dir.glob("*.json") if path.name != "summary.json")
    if len(raw_files) != 9:
        errors.append(f"burst evidence file count is {len(raw_files)}, expected 9")
    for path in raw_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            message = data["choices"][0]["message"]
        except Exception as exc:
            errors.append(f"could not inspect sanitized output in {path.relative_to(ROOT)}: {exc}")
            continue
        if "content" in message:
            errors.append(f"generated response text found in {path.relative_to(ROOT)}")
        if message.get("content_sha256") != EXPECTED_OUTPUT_SHA256:
            errors.append(f"output hash missing or changed in {path.relative_to(ROOT)}")
        if message.get("content_bytes") != 1669:
            errors.append(f"output byte count missing or changed in {path.relative_to(ROOT)}")


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
    validate_content_mix_results(errors)
    validate_license_defenses(errors)

    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Repository validation passed")


if __name__ == "__main__":
    main()
