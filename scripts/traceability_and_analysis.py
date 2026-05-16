#!/usr/bin/env python3
"""
S7 — 可追溯性与结果分析（FR 6.0 前半 / Mainly 后段）
读入 06_test_cases_draft.json，构建「用例 ↔ 覆盖项 ↔ 策略 ↔ 需求」映射，
并生成简要结果分析与改进建议记录。
"""

from __future__ import annotations

import argparse
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


def _build_req_index(requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["req_id"]: r for r in requirements if isinstance(r, dict) and r.get("req_id")}


def _build_cov_index(coverage_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {c["coverage_id"]: c for c in coverage_items if isinstance(c, dict) and c.get("coverage_id")}


def _build_strat_index(strategies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {s["strategy_id"]: s for s in strategies if isinstance(s, dict) and s.get("strategy_id")}


def build_traceability(
    test_cases: list[dict[str, Any]],
    req_idx: dict[str, dict[str, Any]],
    cov_idx: dict[str, dict[str, Any]],
    strat_idx: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    mappings: list[dict[str, Any]] = []
    req_to_cases: dict[str, list[str]] = defaultdict(list)
    cov_to_cases: dict[str, list[str]] = defaultdict(list)
    strat_to_cases: dict[str, list[str]] = defaultdict(list)

    for tc in test_cases:
        if not isinstance(tc, dict) or not tc.get("case_id"):
            continue
        cid = tc["case_id"]
        links = tc.get("links") or {}
        req_ids = list(links.get("req") or [])
        cov_ids = list(links.get("coverage") or [])
        sid = links.get("strategy") or ""

        for rid in req_ids:
            req_to_cases[rid].append(cid)
        for cov_id in cov_ids:
            cov_to_cases[cov_id].append(cid)
        if sid:
            strat_to_cases[sid].append(cid)

        mappings.append({
            "case_id": cid,
            "title": tc.get("title", ""),
            "technique": tc.get("technique", ""),
            "strategy_id": sid,
            "coverage_ids": cov_ids,
            "req_ids": req_ids,
            "strategy_technique": (strat_idx.get(sid) or {}).get("technique"),
        })

    uncovered_reqs = [rid for rid in req_idx if rid not in req_to_cases]
    uncovered_covs = [cid for cid in cov_idx if cid not in cov_to_cases]
    uncovered_strats = [sid for sid in strat_idx if sid not in strat_to_cases]

    return {
        "mappings": mappings,
        "req_to_cases": {k: sorted(set(v)) for k, v in sorted(req_to_cases.items())},
        "coverage_to_cases": {k: sorted(set(v)) for k, v in sorted(cov_to_cases.items())},
        "strategy_to_cases": {k: sorted(set(v)) for k, v in sorted(strat_to_cases.items())},
        "uncovered": {
            "requirements": uncovered_reqs,
            "coverage_items": uncovered_covs,
            "strategies": uncovered_strats,
        },
    }


def build_analysis(
    test_cases: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
    coverage_items: list[dict[str, Any]],
    strategies: list[dict[str, Any]],
    traceability: dict[str, Any],
) -> dict[str, Any]:
    technique_counts: dict[str, int] = defaultdict(int)
    for tc in test_cases:
        if isinstance(tc, dict) and tc.get("technique"):
            technique_counts[tc["technique"]] += 1

    priority_counts: dict[str, int] = defaultdict(int)
    for req in requirements:
        if isinstance(req, dict):
            priority_counts[req.get("test_priority", "Unknown")] += 1

    high_reqs = [
        r["req_id"] for r in requirements
        if isinstance(r, dict) and r.get("test_priority") == "High"
    ]
    high_cases = [
        tc["case_id"] for tc in test_cases
        if isinstance(tc, dict)
        and any(rid in high_reqs for rid in (tc.get("links") or {}).get("req") or [])
    ]

    gaps: list[str] = []
    unc = traceability.get("uncovered") or {}
    if unc.get("requirements"):
        gaps.append(f"{len(unc['requirements'])} 条需求尚无对应用例：{', '.join(unc['requirements'])}")
    if unc.get("coverage_items"):
        gaps.append(f"{len(unc['coverage_items'])} 个覆盖项未被用例覆盖：{', '.join(unc['coverage_items'])}")
    if unc.get("strategies"):
        gaps.append(f"{len(unc['strategies'])} 条策略未产出用例：{', '.join(unc['strategies'])}")

    empty_expected = [
        tc["case_id"] for tc in test_cases
        if isinstance(tc, dict) and not str(tc.get("expected_result") or "").strip()
    ]
    if empty_expected:
        gaps.append(f"{len(empty_expected)} 条用例缺少预期结果，需人工审查或接入预言模块")

    recommendations: list[str] = []
    if gaps:
        recommendations.append("优先在交互审查阶段补全缺失覆盖与预期结果")
    if high_reqs and len(high_cases) < len(high_reqs):
        recommendations.append("为 High 优先级需求补充负面场景与边界用例")
    if len(strategies) > 0 and len(test_cases) / len(strategies) < 2:
        recommendations.append("部分策略仅用例偏少，可检查 EP/BVA/DT 生成规则是否过窄")
    if not recommendations:
        recommendations.append("追溯链完整，可进入交互审查与导出阶段")

    return {
        "summary": (
            f"共 {len(test_cases)} 条用例，覆盖 {len(coverage_items)} 个覆盖项、"
            f"{len(strategies)} 条策略、{len(requirements)} 条需求；"
            f"技术分布：{dict(technique_counts)}"
        ),
        "technique_coverage": dict(technique_counts),
        "priority_distribution": dict(priority_counts),
        "high_priority": {
            "req_ids": high_reqs,
            "linked_case_ids": high_cases,
            "case_count": len(high_cases),
        },
        "gaps": gaps,
        "recommendations": recommendations,
    }


def build_improvement_records(
    analysis: dict[str, Any],
    traceability: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    gaps = analysis.get("gaps") or []
    if gaps:
        records.append({
            "record_id": "IMP-001",
            "at": _utc_now(),
            "author": "traceability_and_analysis.py",
            "entity_type": "pipeline",
            "entity_id": "S7",
            "change_summary": "自动识别覆盖缺口与待补全预期结果",
            "rationale": "; ".join(gaps),
        })

    unc = traceability.get("uncovered") or {}
    if unc.get("coverage_items"):
        records.append({
            "record_id": "IMP-002",
            "at": _utc_now(),
            "author": "traceability_and_analysis.py",
            "entity_type": "coverage_items",
            "entity_id": ",".join(unc["coverage_items"]),
            "change_summary": "建议在交互审查中新增或关联用例",
            "rationale": "覆盖项未映射到任何测试用例",
        })
    return records


def traceability_payload(data: dict[str, Any]) -> dict[str, Any]:
    reqs = data.get("requirements") or []
    covs = data.get("coverage_items") or []
    strats = data.get("strategies") or []
    cases = data.get("test_cases") or []

    if not isinstance(cases, list):
        raise ValueError("test_cases 必须为数组")

    req_idx = _build_req_index(reqs)
    cov_idx = _build_cov_index(covs)
    strat_idx = _build_strat_index(strats)

    trace = build_traceability(cases, req_idx, cov_idx, strat_idx)
    analysis = build_analysis(cases, reqs, covs, strats, trace)
    improvements = build_improvement_records(analysis, trace)

    out: dict[str, Any] = {
        "schema_version": data.get("schema_version", "1.0"),
        "pipeline_stage": "07_traceability",
        "traceability_analyzed_at": _utc_now(),
        "requirements": reqs,
        "coverage_items": covs,
        "strategies": strats,
        "test_cases": cases,
        "traceability": trace,
        "analysis": analysis,
        "improvement_records": improvements,
    }
    for key in ("technique_summary", "total_cases", "test_cases_generated_at", "source_files"):
        if key in data:
            out[key] = data[key]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S7 可追溯与结果分析：06_test_cases_draft.json → 07_traceability.json（FR 6.0）"
    )
    parser.add_argument("--in", dest="in_path", metavar="PATH", required=True, help="输入 06_test_cases_draft.json")
    parser.add_argument("--out", dest="out_path", metavar="PATH", required=True, help="输出 07_traceability.json")
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

    try:
        out_obj = traceability_payload(loaded)
    except ValueError as ex:
        eprint(f"错误：{ex}")
        return 1

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as ex:
        eprint(f"错误：无法写入：{ex}")
        return 1

    nm = len(out_obj.get("traceability", {}).get("mappings", []))
    gaps = len(out_obj.get("analysis", {}).get("gaps", []))
    print(f"已写入 {out_path}（{nm} 条追溯映射；识别 {gaps} 项待改进点）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
