#!/usr/bin/env python3
"""
S9 — 导出测试产物（FR 6.0）
读入 08_reviewed.json，导出 JSON（cases + suites + risk）及 CSV 风险/用例表。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _priority_rank(p: str) -> int:
    return {"High": 0, "Medium": 1, "Low": 2}.get(p, 3)


def build_suites(
    test_cases: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    req_priority: dict[str, str] = {}
    for req in requirements:
        if isinstance(req, dict) and req.get("req_id"):
            req_priority[req["req_id"]] = req.get("test_priority", "Low")

    buckets: dict[str, list[str]] = defaultdict(list)
    for tc in test_cases:
        if not isinstance(tc, dict) or not tc.get("case_id"):
            continue
        links = tc.get("links") or {}
        req_ids = links.get("req") or []
        if not req_ids:
            buckets["Low"].append(tc["case_id"])
            continue
        best = min((_priority_rank(req_priority.get(rid, "Low")) for rid in req_ids), default=2)
        label = {0: "High", 1: "Medium", 2: "Low"}.get(best, "Low")
        buckets[label].append(tc["case_id"])

    suites: list[dict[str, Any]] = []
    order = ["High", "Medium", "Low"]
    for i, pri in enumerate(order, start=1):
        case_ids = sorted(buckets.get(pri, []))
        if not case_ids:
            continue
        suites.append({
            "suite_id": f"SUITE-{i:03d}",
            "name": f"{pri} 优先级回归套件",
            "priority": pri,
            "case_ids": case_ids,
            "case_count": len(case_ids),
        })

    # technique-based suites
    tech_buckets: dict[str, list[str]] = defaultdict(list)
    for tc in test_cases:
        if isinstance(tc, dict) and tc.get("case_id") and tc.get("technique"):
            tech_buckets[tc["technique"]].append(tc["case_id"])
    base = len(suites)
    for j, (tech, case_ids) in enumerate(sorted(tech_buckets.items()), start=1):
        suites.append({
            "suite_id": f"SUITE-T{base + j:03d}",
            "name": f"{tech} 技术专项套件",
            "priority": "Medium",
            "technique": tech,
            "case_ids": sorted(case_ids),
            "case_count": len(case_ids),
        })
    return suites


def export_cases_rows(test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tc in test_cases:
        if not isinstance(tc, dict):
            continue
        links = tc.get("links") or {}
        rows.append({
            "case_id": tc.get("case_id", ""),
            "title": tc.get("title", ""),
            "technique": tc.get("technique", ""),
            "expected_result": tc.get("expected_result", ""),
            "steps": " | ".join(tc.get("steps") or []),
            "test_data": json.dumps(tc.get("test_data") or {}, ensure_ascii=False),
            "linked_req_ids": ",".join(links.get("req") or []),
            "linked_coverage_ids": ",".join(links.get("coverage") or []),
            "linked_strategy_id": links.get("strategy", ""),
        })
    return rows


def export_risk_rows(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for req in requirements:
        if not isinstance(req, dict):
            continue
        rows.append({
            "req_id": req.get("req_id", ""),
            "raw_text": req.get("raw_text", ""),
            "risk_score": req.get("risk_score", ""),
            "test_priority": req.get("test_priority", ""),
            "risk_rationale": "；".join(req.get("risk_rationale") or []),
        })
    return rows


def export_payload(data: dict[str, Any]) -> dict[str, Any]:
    reqs = data.get("requirements") or []
    cases = data.get("test_cases") or []
    suites = build_suites(cases, reqs)

    risk_summary = {
        "requirement_count": len(reqs),
        "case_count": len(cases),
        "suite_count": len(suites),
        "by_priority": {},
    }
    for req in reqs:
        if isinstance(req, dict):
            pri = req.get("test_priority", "Unknown")
            risk_summary["by_priority"][pri] = risk_summary["by_priority"].get(pri, 0) + 1

    return {
        "schema_version": data.get("schema_version", "1.0"),
        "pipeline_stage": "09_export",
        "exported_at": _utc_now(),
        "document_id": data.get("document_id"),
        "suites": suites,
        "cases": export_cases_rows(cases),
        "risk": {
            "requirements": export_risk_rows(reqs),
            "summary": risk_summary,
        },
        "traceability_summary": (data.get("analysis") or {}).get("summary", ""),
        "improvement_record_count": len(data.get("improvement_records") or []),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S9 导出：08_reviewed.json → 09_export_cases.json + CSV（FR 6.0）"
    )
    parser.add_argument("--in", dest="in_path", metavar="PATH", required=True, help="输入 08_reviewed.json")
    parser.add_argument("--out", dest="out_path", metavar="PATH", required=True, help="输出 09_export_cases.json")
    parser.add_argument(
        "--csv-dir",
        metavar="DIR",
        default=None,
        help="可选：同时写出 CSV 到目录（09_export_cases.csv、09_export_risk.csv）",
    )
    args = parser.parse_args()

    in_path = Path(args.in_path)
    if not in_path.is_file():
        eprint(f"错误：找不到输入文件：{in_path}")
        return 1

    try:
        with in_path.open(encoding="utf-8") as f:
            loaded = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        eprint(f"错误：无法读取 JSON：{ex}")
        return 1

    out_obj = export_payload(loaded)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as ex:
        eprint(f"错误：无法写入：{ex}")
        return 1

    csv_written: list[str] = []
    if args.csv_dir:
        csv_dir = Path(args.csv_dir)
        cases_csv = csv_dir / "09_export_cases.csv"
        risk_csv = csv_dir / "09_export_risk.csv"
        case_fields = [
            "case_id", "title", "technique", "expected_result",
            "steps", "test_data", "linked_req_ids", "linked_coverage_ids", "linked_strategy_id",
        ]
        risk_fields = ["req_id", "raw_text", "risk_score", "test_priority", "risk_rationale"]
        write_csv(cases_csv, out_obj.get("cases") or [], case_fields)
        write_csv(risk_csv, (out_obj.get("risk") or {}).get("requirements") or [], risk_fields)
        csv_written = [str(cases_csv), str(risk_csv)]

    msg = f"已写入 {out_path}（{len(out_obj.get('cases', []))} 条用例，{len(out_obj.get('suites', []))} 个套件）"
    if csv_written:
        msg += f"；CSV：{', '.join(csv_written)}"
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
