#!/usr/bin/env python3
"""
S4 — 覆盖项识别（Mainly 前半的可落盘版本）
读入 03_with_risk.json，生成顶层 coverage_items[]（coverage_id、description、linked_req_ids），
并透传 requirements，供下游策略与用例生成使用。
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


def _nid(prefix: str, idx: int) -> str:
    return f"{prefix}-{idx:03d}"


def build_coverage_items(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """基于结构化字段与风险信息生成可解释的覆盖项。"""
    items: list[dict[str, Any]] = []
    n = 0

    for req in requirements:
        if not isinstance(req, dict):
            continue
        rid = str(req.get("req_id") or "")
        if not rid:
            continue

        raw = str(req.get("raw_text") or "")[:200]
        pri = str(req.get("test_priority") or "")
        score = req.get("risk_score")

        # 数据范围 → 等价类 / 边界值覆盖
        for rng in req.get("data_ranges") or []:
            if not isinstance(rng, dict):
                continue
            field = str(rng.get("field") or "字段")
            n += 1
            items.append(
                {
                    "coverage_id": _nid("COV", n),
                    "description": (
                        f"验证「{field}」取值区间与边界（等价类划分 + 边界值分析），"
                        f"依据需求 {rid}"
                    ),
                    "linked_req_ids": [rid],
                    "focus": "data_range",
                    "notes": f"范围线索：{rng.get('raw_span') or rng}",
                }
            )

        # 条件分支 → 决策表 / 流程分支
        for i, c in enumerate(req.get("conditions") or []):
            if not isinstance(c, dict):
                continue
            expr = str(c.get("expr") or "条件")
            n += 1
            items.append(
                {
                    "coverage_id": _nid("COV", n),
                    "description": (
                        f"覆盖条件分支：当 {expr} 时系统行为（决策表/场景），需求 {rid}"
                    ),
                    "linked_req_ids": [rid],
                    "focus": "condition_branch",
                    "notes": f"条件索引 {i + 1}",
                }
            )

        # 预期动作 → 状态/副作用验证
        for i, a in enumerate(req.get("expected_actions") or []):
            if not isinstance(a, dict):
                continue
            act = str(a.get("action") or "动作")
            n += 1
            items.append(
                {
                    "coverage_id": _nid("COV", n),
                    "description": (
                        f"验证预期动作是否发生：{act}（需求 {rid}）"
                    ),
                    "linked_req_ids": [rid],
                    "focus": "expected_action",
                    "notes": f"动作索引 {i + 1}",
                }
            )

        # 若结构化未抽出细节，仍依据 risk 补一条总览覆盖项，避免遗漏
        has_detail = bool(
            (req.get("data_ranges") or [])
            or (req.get("conditions") or [])
            or (req.get("expected_actions") or [])
        )
        if not has_detail:
            n += 1
            items.append(
                {
                    "coverage_id": _nid("COV", n),
                    "description": (
                        f"对需求 {rid} 进行整体功能验证（摘要：{raw}…）"
                    ),
                    "linked_req_ids": [rid],
                    "focus": "general_functional",
                    "notes": "结构化细节较少时的兜底覆盖项",
                }
            )

        # 高风险需求增补「回归/负面路径」覆盖提示（仍链接同一 req）
        if pri == "High":
            n += 1
            items.append(
                {
                    "coverage_id": _nid("COV", n),
                    "description": (
                        f"高风险需求 {rid}：补充异常输入与安全相关负面场景（优先级 {pri}"
                        + (
                            f"，risk_score={score}" if score is not None else ""
                        )
                        + "）"
                    ),
                    "linked_req_ids": [rid],
                    "focus": "risk_negative",
                    "notes": "由 test_priority=High 触发",
                }
            )

    return items


def coverage_payload(data: dict[str, Any]) -> dict[str, Any]:
    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        raise ValueError("输入缺少 requirements 数组")

    coverage_items = build_coverage_items(reqs)
    now = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    )

    out: dict[str, Any] = {
        "schema_version": data.get("schema_version", "1.0"),
        "pipeline_stage": "04_coverage_items",
        "coverage_items_generated_at": now,
        "requirements": reqs,
        "coverage_items": coverage_items,
    }
    if data.get("source_files"):
        out["source_files"] = data["source_files"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S4 覆盖项：03_with_risk.json → 04_coverage_items.json"
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        metavar="PATH",
        required=True,
        help="输入 03_with_risk.json",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        metavar="PATH",
        required=True,
        help="输出 04_coverage_items.json",
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
        out_obj = coverage_payload(loaded)
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

    nc = len(out_obj.get("coverage_items") or [])
    print(f"已写入 {out_path}（{nc} 条覆盖项）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
