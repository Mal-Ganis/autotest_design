#!/usr/bin/env python3
"""
S5 — 策略与提示生成（FR 3.0 前半）
读入 04_coverage_items.json，为每个覆盖项分配至少一种 ISO 29119-4 黑盒技术
（EP / BVA / DT），并生成提示要点，供下游 blackbox_generate.py 消费。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def _sid(idx: int) -> str:
    return f"STR-{idx:03d}"


# coverage_item.focus → 推荐黑盒技术列表
_FOCUS_TECHNIQUES: dict[str, list[str]] = {
    "data_range":        ["EP", "BVA"],
    "condition_branch":  ["DT"],
    "expected_action":   ["EP"],
    "general_functional":["EP"],
    "risk_negative":     ["BVA", "DT"],
}


def _build_req_index(requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for r in requirements:
        if isinstance(r, dict) and r.get("req_id"):
            idx[r["req_id"]] = r
    return idx


def _prompt_notes_for(
    technique: str,
    cov: dict[str, Any],
    req_idx: dict[str, dict[str, Any]],
) -> str:
    """根据技术类型与覆盖项上下文生成提示说明。"""
    desc = cov.get("description") or ""
    focus = cov.get("focus") or ""
    linked = cov.get("linked_req_ids") or []

    ranges: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    raw_texts: list[str] = []
    for rid in linked:
        req = req_idx.get(rid, {})
        ranges.extend(req.get("data_ranges") or [])
        conditions.extend(req.get("conditions") or [])
        actions.extend(req.get("expected_actions") or [])
        if req.get("raw_text"):
            raw_texts.append(req["raw_text"])

    if technique == "EP":
        parts = []
        if focus == "data_range" and ranges:
            for rng in ranges:
                field = rng.get("field", "字段")
                lo = rng.get("min")
                hi = rng.get("max")
                unit = rng.get("unit", "")
                parts.append(
                    f"对「{field}」划分等价类：有效区间 [{lo}, {hi}] {unit}，"
                    f"无效区间 <{lo} 和 >{hi}；另需考虑空输入与特殊字符"
                )
        elif focus == "expected_action" and actions:
            for a in actions:
                parts.append(f"验证动作「{a.get('action', '')}」在正常/异常输入下的触发情况")
        else:
            parts.append(f"对覆盖项进行等价类划分：有效与无效输入各取代表值")
        if raw_texts:
            parts.append(f"需求原文参考：{'；'.join(raw_texts[:2])}")
        return "；".join(parts)

    if technique == "BVA":
        parts = []
        if ranges:
            for rng in ranges:
                field = rng.get("field", "字段")
                lo = rng.get("min")
                hi = rng.get("max")
                unit = rng.get("unit", "")
                closed = rng.get("closed", True)
                if closed:
                    parts.append(
                        f"「{field}」边界值：{lo-1}, {lo}, {lo+1}, {hi-1}, {hi}, {hi+1} ({unit})"
                        if isinstance(lo, (int, float)) and isinstance(hi, (int, float))
                        else f"「{field}」边界值测试"
                    )
                else:
                    parts.append(f"「{field}」开区间边界值测试")
        else:
            parts.append("对关键数值型输入进行边界值分析（含上下边界 ±1）")
        if focus == "risk_negative":
            parts.append("重点关注异常/极端边界以覆盖高风险负面场景")
        return "；".join(parts)

    if technique == "DT":
        parts = []
        if conditions:
            cond_exprs = [c.get("expr", "条件") for c in conditions]
            act_descs = [a.get("action", "动作") for a in actions]
            parts.append(f"条件桩：{'、'.join(cond_exprs)}")
            if act_descs:
                parts.append(f"动作桩：{'、'.join(act_descs)}")
            parts.append("列举所有条件组合（True/False），标注各组合下的预期动作")
        else:
            parts.append("基于需求中的条件与动作构建决策表，列举组合并标注预期结果")
        if focus == "risk_negative":
            parts.append("补充非法组合与异常条件的决策行")
        return "；".join(parts)

    return f"应用 {technique} 技术对覆盖项 {cov.get('coverage_id', '')} 生成测试用例"


def build_strategies(
    coverage_items: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    req_idx = _build_req_index(requirements)
    strategies: list[dict[str, Any]] = []
    n = 0

    for cov in coverage_items:
        if not isinstance(cov, dict):
            continue
        cid = cov.get("coverage_id") or ""
        focus = cov.get("focus") or "general_functional"
        techniques = _FOCUS_TECHNIQUES.get(focus, ["EP"])

        linked_reqs = cov.get("linked_req_ids") or []
        max_pri = "Low"
        for rid in linked_reqs:
            req = req_idx.get(rid, {})
            pri = req.get("test_priority", "Low")
            if pri == "High":
                max_pri = "High"
            elif pri == "Medium" and max_pri != "High":
                max_pri = "Medium"

        for tech in techniques:
            n += 1
            strategies.append({
                "strategy_id": _sid(n),
                "technique": tech,
                "linked_coverage_ids": [cid],
                "linked_req_ids": linked_reqs,
                "risk_priority": max_pri,
                "prompt_notes": _prompt_notes_for(tech, cov, req_idx),
            })

    return strategies


def strategies_payload(data: dict[str, Any]) -> dict[str, Any]:
    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        raise ValueError("输入缺少 requirements 数组")
    covs = data.get("coverage_items")
    if not isinstance(covs, list):
        raise ValueError("输入缺少 coverage_items 数组")

    strategies = build_strategies(covs, reqs)
    now = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    technique_counts: dict[str, int] = {}
    for s in strategies:
        t = s["technique"]
        technique_counts[t] = technique_counts.get(t, 0) + 1

    out: dict[str, Any] = {
        "schema_version": data.get("schema_version", "1.0"),
        "pipeline_stage": "05_strategies",
        "strategies_generated_at": now,
        "technique_summary": technique_counts,
        "requirements": reqs,
        "coverage_items": covs,
        "strategies": strategies,
    }
    if data.get("source_files"):
        out["source_files"] = data["source_files"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S5 策略与提示：04_coverage_items.json → 05_strategies.json（FR 3.0）"
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        metavar="PATH",
        required=True,
        help="输入 04_coverage_items.json",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        metavar="PATH",
        required=True,
        help="输出 05_strategies.json",
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

    try:
        out_obj = strategies_payload(loaded)
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

    ns = len(out_obj.get("strategies") or [])
    summary = out_obj.get("technique_summary", {})
    tech_info = ", ".join(f"{k}={v}" for k, v in summary.items())
    print(f"已写入 {out_path}（{ns} 条策略；技术分布：{tech_info}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
