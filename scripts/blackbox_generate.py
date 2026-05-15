#!/usr/bin/env python3
"""
S6 — 黑盒测试用例生成（FR 3.0 后半）
读入 05_strategies.json，根据每条策略的 technique（EP / BVA / DT）自动生成
具体测试用例（含 steps、test_data、expected_result 及可追溯链接）。
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


def _cid(idx: int) -> str:
    return f"TC-{idx:03d}"


def _build_req_index(requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for r in requirements:
        if isinstance(r, dict) and r.get("req_id"):
            idx[r["req_id"]] = r
    return idx


def _build_cov_index(coverage_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for c in coverage_items:
        if isinstance(c, dict) and c.get("coverage_id"):
            idx[c["coverage_id"]] = c
    return idx


def _gen_ep_cases(
    strategy: dict[str, Any],
    req_idx: dict[str, dict[str, Any]],
    cov_idx: dict[str, dict[str, Any]],
    counter: list[int],
) -> list[dict[str, Any]]:
    """等价类划分：为每个关联范围生成有效类 + 无效类用例。"""
    cases: list[dict[str, Any]] = []
    sid = strategy["strategy_id"]
    linked_reqs = strategy.get("linked_req_ids") or []
    linked_covs = strategy.get("linked_coverage_ids") or []

    ranges: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for rid in linked_reqs:
        req = req_idx.get(rid, {})
        ranges.extend(req.get("data_ranges") or [])
        conditions.extend(req.get("conditions") or [])
        actions.extend(req.get("expected_actions") or [])

    cov_focus = ""
    for cid in linked_covs:
        cov = cov_idx.get(cid, {})
        cov_focus = cov.get("focus") or cov_focus

    if ranges:
        for rng in ranges:
            field = rng.get("field", "字段")
            lo = rng.get("min")
            hi = rng.get("max")
            unit = rng.get("unit", "")

            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
                mid = lo + (hi - lo) // 2 if isinstance(lo, int) else (lo + hi) / 2

                counter[0] += 1
                cases.append({
                    "case_id": _cid(counter[0]),
                    "title": f"EP-有效类：{field} 在有效区间内（{mid} {unit}）",
                    "technique": "EP",
                    "steps": [
                        f"输入 {field} = {mid}",
                        "提交请求",
                        "验证系统接受该输入并正常处理",
                    ],
                    "test_data": {field: mid},
                    "expected_result": f"系统接受 {field}={mid}，处理成功",
                    "links": {
                        "req": linked_reqs,
                        "coverage": linked_covs,
                        "strategy": sid,
                    },
                })

                counter[0] += 1
                below = lo - 1 if isinstance(lo, int) else lo - 0.1
                cases.append({
                    "case_id": _cid(counter[0]),
                    "title": f"EP-无效类（下溢）：{field} < 最小值（{below} {unit}）",
                    "technique": "EP",
                    "steps": [
                        f"输入 {field} = {below}",
                        "提交请求",
                        "验证系统拒绝该输入并给出错误提示",
                    ],
                    "test_data": {field: below},
                    "expected_result": f"系统拒绝 {field}={below}，提示输入不合法",
                    "links": {
                        "req": linked_reqs,
                        "coverage": linked_covs,
                        "strategy": sid,
                    },
                })

                counter[0] += 1
                above = hi + 1 if isinstance(hi, int) else hi + 0.1
                cases.append({
                    "case_id": _cid(counter[0]),
                    "title": f"EP-无效类（上溢）：{field} > 最大值（{above} {unit}）",
                    "technique": "EP",
                    "steps": [
                        f"输入 {field} = {above}",
                        "提交请求",
                        "验证系统拒绝该输入并给出错误提示",
                    ],
                    "test_data": {field: above},
                    "expected_result": f"系统拒绝 {field}={above}，提示输入不合法",
                    "links": {
                        "req": linked_reqs,
                        "coverage": linked_covs,
                        "strategy": sid,
                    },
                })

                counter[0] += 1
                cases.append({
                    "case_id": _cid(counter[0]),
                    "title": f"EP-无效类（空输入）：{field} 为空",
                    "technique": "EP",
                    "steps": [
                        f"不输入 {field}（留空）",
                        "提交请求",
                        "验证系统拒绝并提示必填",
                    ],
                    "test_data": {field: ""},
                    "expected_result": f"系统拒绝空 {field}，提示必填字段",
                    "links": {
                        "req": linked_reqs,
                        "coverage": linked_covs,
                        "strategy": sid,
                    },
                })
            else:
                counter[0] += 1
                cases.append({
                    "case_id": _cid(counter[0]),
                    "title": f"EP-通用：{field} 有效与无效等价类",
                    "technique": "EP",
                    "steps": [
                        f"分别输入 {field} 的有效值和无效值",
                        "提交请求",
                        "对比预期结果",
                    ],
                    "test_data": {field: "有效代表值 / 无效代表值"},
                    "expected_result": "有效值被接受，无效值被拒绝",
                    "links": {
                        "req": linked_reqs,
                        "coverage": linked_covs,
                        "strategy": sid,
                    },
                })

    elif cov_focus == "expected_action" and actions:
        for act_item in actions:
            act = act_item.get("action", "动作")
            counter[0] += 1
            cases.append({
                "case_id": _cid(counter[0]),
                "title": f"EP-动作验证：{act}（正常触发）",
                "technique": "EP",
                "steps": [
                    "构造满足触发条件的有效输入",
                    "执行操作",
                    f"验证动作「{act}」被正确执行",
                ],
                "test_data": {"trigger_condition": "满足"},
                "expected_result": f"动作「{act}」成功触发",
                "links": {
                    "req": linked_reqs,
                    "coverage": linked_covs,
                    "strategy": sid,
                },
            })
            counter[0] += 1
            cases.append({
                "case_id": _cid(counter[0]),
                "title": f"EP-动作验证：{act}（条件不满足时不触发）",
                "technique": "EP",
                "steps": [
                    "构造不满足触发条件的输入",
                    "执行操作",
                    f"验证动作「{act}」未被执行",
                ],
                "test_data": {"trigger_condition": "不满足"},
                "expected_result": f"动作「{act}」未触发，系统正常继续",
                "links": {
                    "req": linked_reqs,
                    "coverage": linked_covs,
                    "strategy": sid,
                },
            })

    else:
        counter[0] += 1
        cases.append({
            "case_id": _cid(counter[0]),
            "title": "EP-通用功能验证：有效输入",
            "technique": "EP",
            "steps": [
                "使用有效的典型输入执行功能",
                "验证系统输出符合预期",
            ],
            "test_data": {"input": "有效代表值"},
            "expected_result": "系统正常处理，结果符合需求",
            "links": {
                "req": linked_reqs,
                "coverage": linked_covs,
                "strategy": sid,
            },
        })
        counter[0] += 1
        cases.append({
            "case_id": _cid(counter[0]),
            "title": "EP-通用功能验证：无效输入",
            "technique": "EP",
            "steps": [
                "使用无效/异常输入执行功能",
                "验证系统给出适当错误处理",
            ],
            "test_data": {"input": "无效代表值"},
            "expected_result": "系统拒绝无效输入并给出明确提示",
            "links": {
                "req": linked_reqs,
                "coverage": linked_covs,
                "strategy": sid,
            },
        })

    return cases


def _gen_bva_cases(
    strategy: dict[str, Any],
    req_idx: dict[str, dict[str, Any]],
    _cov_idx: dict[str, dict[str, Any]],
    counter: list[int],
) -> list[dict[str, Any]]:
    """边界值分析：对每个数据范围生成 min±1, max±1 用例。"""
    cases: list[dict[str, Any]] = []
    sid = strategy["strategy_id"]
    linked_reqs = strategy.get("linked_req_ids") or []
    linked_covs = strategy.get("linked_coverage_ids") or []

    ranges: list[dict[str, Any]] = []
    for rid in linked_reqs:
        req = req_idx.get(rid, {})
        ranges.extend(req.get("data_ranges") or [])

    if ranges:
        for rng in ranges:
            field = rng.get("field", "字段")
            lo = rng.get("min")
            hi = rng.get("max")
            unit = rng.get("unit", "")

            if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float))):
                continue

            boundary_points = []
            if isinstance(lo, int) and isinstance(hi, int):
                boundary_points = [
                    (lo - 1, False, f"下边界-1 ({lo-1} {unit})"),
                    (lo,     True,  f"下边界 ({lo} {unit})"),
                    (lo + 1, True,  f"下边界+1 ({lo+1} {unit})"),
                    (hi - 1, True,  f"上边界-1 ({hi-1} {unit})"),
                    (hi,     True,  f"上边界 ({hi} {unit})"),
                    (hi + 1, False, f"上边界+1 ({hi+1} {unit})"),
                ]
            else:
                delta = 0.1
                boundary_points = [
                    (lo - delta, False, f"下边界-δ ({lo-delta} {unit})"),
                    (lo,         True,  f"下边界 ({lo} {unit})"),
                    (hi,         True,  f"上边界 ({hi} {unit})"),
                    (hi + delta, False, f"上边界+δ ({hi+delta} {unit})"),
                ]

            for val, is_valid, label in boundary_points:
                counter[0] += 1
                if is_valid:
                    cases.append({
                        "case_id": _cid(counter[0]),
                        "title": f"BVA-有效边界：{field} = {label}",
                        "technique": "BVA",
                        "steps": [
                            f"输入 {field} = {val}",
                            "提交请求",
                            "验证系统接受该边界值",
                        ],
                        "test_data": {field: val},
                        "expected_result": f"系统接受 {field}={val}，处理成功",
                        "links": {
                            "req": linked_reqs,
                            "coverage": linked_covs,
                            "strategy": sid,
                        },
                    })
                else:
                    cases.append({
                        "case_id": _cid(counter[0]),
                        "title": f"BVA-无效边界：{field} = {label}",
                        "technique": "BVA",
                        "steps": [
                            f"输入 {field} = {val}",
                            "提交请求",
                            "验证系统拒绝该越界值",
                        ],
                        "test_data": {field: val},
                        "expected_result": f"系统拒绝 {field}={val}，提示输入超出范围",
                        "links": {
                            "req": linked_reqs,
                            "coverage": linked_covs,
                            "strategy": sid,
                        },
                    })
    else:
        counter[0] += 1
        cases.append({
            "case_id": _cid(counter[0]),
            "title": "BVA-通用：关键输入的边界值探测",
            "technique": "BVA",
            "steps": [
                "识别关键数值型输入的上下界",
                "分别输入边界值及边界±1",
                "验证系统对边界内外值的处理",
            ],
            "test_data": {"boundary": "上下界 ±1"},
            "expected_result": "边界内值被接受，边界外值被拒绝",
            "links": {
                "req": linked_reqs,
                "coverage": linked_covs,
                "strategy": sid,
            },
        })

    return cases


def _gen_dt_cases(
    strategy: dict[str, Any],
    req_idx: dict[str, dict[str, Any]],
    _cov_idx: dict[str, dict[str, Any]],
    counter: list[int],
) -> list[dict[str, Any]]:
    """决策表：基于条件与动作的组合生成规则行。"""
    cases: list[dict[str, Any]] = []
    sid = strategy["strategy_id"]
    linked_reqs = strategy.get("linked_req_ids") or []
    linked_covs = strategy.get("linked_coverage_ids") or []

    conditions: list[str] = []
    actions: list[str] = []
    for rid in linked_reqs:
        req = req_idx.get(rid, {})
        for c in req.get("conditions") or []:
            if isinstance(c, dict) and c.get("expr"):
                conditions.append(c["expr"])
        for a in req.get("expected_actions") or []:
            if isinstance(a, dict) and a.get("action"):
                actions.append(a["action"])

    if not conditions:
        conditions = ["前置条件成立"]
    if not actions:
        actions = ["系统执行预期动作"]

    n_conds = len(conditions)
    n_combos = 1 << n_conds

    for combo_idx in range(n_combos):
        cond_values: dict[str, bool] = {}
        desc_parts: list[str] = []
        for ci, cond in enumerate(conditions):
            val = bool(combo_idx & (1 << ci))
            cond_values[cond] = val
            desc_parts.append(f"{'✓' if val else '✗'} {cond}")

        all_true = all(cond_values.values())
        if all_true:
            expected = "；".join(actions)
        else:
            false_conds = [c for c, v in cond_values.items() if not v]
            expected = f"条件未全部满足（{'、'.join(false_conds)}），动作不触发或走替代分支"

        counter[0] += 1
        cases.append({
            "case_id": _cid(counter[0]),
            "title": f"DT-规则{combo_idx + 1}：{'、'.join(desc_parts)}",
            "technique": "DT",
            "steps": [
                f"设置条件组合：{'; '.join(desc_parts)}",
                "执行操作",
                "验证系统按决策表规则响应",
            ],
            "test_data": {"conditions": cond_values},
            "expected_result": expected,
            "links": {
                "req": linked_reqs,
                "coverage": linked_covs,
                "strategy": sid,
            },
        })

    return cases


_GENERATORS = {
    "EP": _gen_ep_cases,
    "BVA": _gen_bva_cases,
    "DT": _gen_dt_cases,
}


def build_test_cases(
    strategies: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
    coverage_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    req_idx = _build_req_index(requirements)
    cov_idx = _build_cov_index(coverage_items)
    counter = [0]
    all_cases: list[dict[str, Any]] = []

    for strat in strategies:
        if not isinstance(strat, dict):
            continue
        tech = strat.get("technique") or ""
        gen = _GENERATORS.get(tech)
        if gen:
            all_cases.extend(gen(strat, req_idx, cov_idx, counter))
        else:
            counter[0] += 1
            all_cases.append({
                "case_id": _cid(counter[0]),
                "title": f"{tech}-通用：基于策略 {strat.get('strategy_id', '')} 生成",
                "technique": tech,
                "steps": ["按策略提示执行测试"],
                "test_data": {},
                "expected_result": "待填充",
                "links": {
                    "req": strat.get("linked_req_ids") or [],
                    "coverage": strat.get("linked_coverage_ids") or [],
                    "strategy": strat.get("strategy_id", ""),
                },
            })

    return all_cases


def testcases_payload(data: dict[str, Any]) -> dict[str, Any]:
    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        raise ValueError("输入缺少 requirements 数组")
    covs = data.get("coverage_items")
    if not isinstance(covs, list):
        raise ValueError("输入缺少 coverage_items 数组")
    strats = data.get("strategies")
    if not isinstance(strats, list):
        raise ValueError("输入缺少 strategies 数组")

    test_cases = build_test_cases(strats, reqs, covs)
    now = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    technique_counts: dict[str, int] = {}
    for tc in test_cases:
        t = tc.get("technique", "unknown")
        technique_counts[t] = technique_counts.get(t, 0) + 1

    out: dict[str, Any] = {
        "schema_version": data.get("schema_version", "1.0"),
        "pipeline_stage": "06_test_cases_draft",
        "test_cases_generated_at": now,
        "technique_summary": technique_counts,
        "total_cases": len(test_cases),
        "requirements": reqs,
        "coverage_items": covs,
        "strategies": strats,
        "test_cases": test_cases,
    }
    if data.get("source_files"):
        out["source_files"] = data["source_files"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S6 黑盒用例生成：05_strategies.json → 06_test_cases_draft.json（FR 3.0）"
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        metavar="PATH",
        required=True,
        help="输入 05_strategies.json",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        metavar="PATH",
        required=True,
        help="输出 06_test_cases_draft.json",
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
        out_obj = testcases_payload(loaded)
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

    nc = out_obj.get("total_cases", 0)
    summary = out_obj.get("technique_summary", {})
    tech_info = ", ".join(f"{k}={v}" for k, v in summary.items())
    print(f"已写入 {out_path}（{nc} 条用例；技术分布：{tech_info}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
