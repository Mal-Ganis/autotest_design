#!/usr/bin/env python3
"""
S8 — 交互式审查（设计者参与修订）
读入 07_traceability.json，提供 CLI 菜单编辑用例/覆盖项等实体，写出 08_reviewed.json。
支持 --pass-through 供 launcher 非交互全流程使用。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_by_id(items: list[dict[str, Any]], id_key: str, entity_id: str) -> tuple[int, dict[str, Any] | None]:
    for i, item in enumerate(items):
        if isinstance(item, dict) and item.get(id_key) == entity_id:
            return i, item
    return -1, None


def _diff_text(before: str, after: str, label: str) -> list[str]:
    if before == after:
        return []
    return [f"  [{label}] 前: {before!r}", f"  [{label}] 后: {after!r}"]


def _collect_case_diff(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for field in ("title", "expected_result", "technique"):
        lines.extend(_diff_text(str(before.get(field, "")), str(after.get(field, "")), field))
    b_steps = before.get("steps") or []
    a_steps = after.get("steps") or []
    if b_steps != a_steps:
        lines.append(f"  [steps] 前: {b_steps!r}")
        lines.append(f"  [steps] 后: {a_steps!r}")
    b_data = before.get("test_data") or {}
    a_data = after.get("test_data") or {}
    if b_data != a_data:
        lines.append(f"  [test_data] 前: {b_data!r}")
        lines.append(f"  [test_data] 后: {a_data!r}")
    return lines


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{msg}{suffix}: ").strip()
    except EOFError:
        eprint("\n错误：输入已结束（非交互环境请使用 --pass-through）")
        raise SystemExit(1)
    return val if val else default


def _edit_test_case(tc: dict[str, Any]) -> dict[str, Any]:
    edited = copy.deepcopy(tc)
    print(f"\n编辑用例 {tc.get('case_id')} — 直接回车保留原值")
    edited["title"] = _prompt("标题 title", str(tc.get("title", "")))
    edited["expected_result"] = _prompt("预期结果 expected_result", str(tc.get("expected_result", "")))
    steps_raw = _prompt("步骤 steps（用 | 分隔）", " | ".join(tc.get("steps") or []))
    if steps_raw:
        edited["steps"] = [s.strip() for s in steps_raw.split("|") if s.strip()]
    return edited


def _edit_coverage_item(cov: dict[str, Any]) -> dict[str, Any]:
    edited = copy.deepcopy(cov)
    print(f"\n编辑覆盖项 {cov.get('coverage_id')} — 直接回车保留原值")
    edited["description"] = _prompt("描述 description", str(cov.get("description", "")))
    notes = _prompt("备注 notes", str(cov.get("notes", "")))
    if notes:
        edited["notes"] = notes
    return edited


def _append_improvement_record(
    records: list[dict[str, Any]],
    entity_type: str,
    entity_id: str,
    summary: str,
    rationale: str,
) -> None:
    n = len(records) + 1
    records.append({
        "record_id": f"IMP-{n:03d}",
        "at": _utc_now(),
        "author": "designer",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "change_summary": summary,
        "rationale": rationale,
    })


def interactive_session(data: dict[str, Any]) -> dict[str, Any]:
    working = copy.deepcopy(data)
    cases: list[dict[str, Any]] = working.setdefault("test_cases", [])
    covs: list[dict[str, Any]] = working.setdefault("coverage_items", [])
    records: list[dict[str, Any]] = working.setdefault("improvement_records", [])
    original_cases = copy.deepcopy(cases)
    original_covs = copy.deepcopy(covs)
    edit_count = 0

    print("=== AutoTestDesign 交互式审查 (S8) ===")
    print("可修订测试用例与覆盖项；保存时将显示变更 diff。\n")

    while True:
        print("菜单：")
        print("  1) 列出测试用例")
        print("  2) 编辑测试用例")
        print("  3) 列出覆盖项")
        print("  4) 编辑覆盖项描述")
        print("  5) 保存并退出")
        print("  6) 放弃修改并退出")
        choice = _prompt("请选择", "1")

        if choice == "1":
            for tc in cases:
                print(f"  {tc.get('case_id')}: {tc.get('title')} [{tc.get('technique')}]")
        elif choice == "2":
            cid = _prompt("输入 case_id（如 TC-001）")
            idx, tc = _find_by_id(cases, "case_id", cid)
            if tc is None:
                eprint(f"未找到用例：{cid}")
                continue
            updated = _edit_test_case(tc)
            diff_lines = _collect_case_diff(tc, updated)
            if diff_lines:
                print("\n--- 变更预览 ---")
                print("\n".join(diff_lines))
                confirm = _prompt("确认应用修改？(y/N)", "y")
                if confirm.lower() in ("y", "yes"):
                    cases[idx] = updated
                    edit_count += 1
                    _append_improvement_record(
                        records,
                        "test_case",
                        cid,
                        "设计者修订用例字段",
                        "; ".join(diff_lines),
                    )
                    print("已应用修改。")
            else:
                print("未检测到变更。")
        elif choice == "3":
            for cov in covs:
                print(f"  {cov.get('coverage_id')}: {cov.get('description', '')[:60]}…")
        elif choice == "4":
            cov_id = _prompt("输入 coverage_id（如 COV-001）")
            idx, cov = _find_by_id(covs, "coverage_id", cov_id)
            if cov is None:
                eprint(f"未找到覆盖项：{cov_id}")
                continue
            updated = _edit_coverage_item(cov)
            if updated.get("description") != cov.get("description") or updated.get("notes") != cov.get("notes"):
                print("\n--- 变更预览 ---")
                for label in ("description", "notes"):
                    for line in _diff_text(str(cov.get(label, "")), str(updated.get(label, "")), label):
                        print(line)
                confirm = _prompt("确认应用修改？(y/N)", "y")
                if confirm.lower() in ("y", "yes"):
                    covs[idx] = updated
                    edit_count += 1
                    _append_improvement_record(
                        records,
                        "coverage_item",
                        cov_id,
                        "设计者修订覆盖项描述",
                        f"description/notes 已更新",
                    )
                    print("已应用修改。")
            else:
                print("未检测到变更。")
        elif choice == "5":
            print("\n========== 保存前总 diff ==========")
            any_diff = False
            for oc, nc in zip(original_cases, cases):
                lines = _collect_case_diff(oc, nc)
                if lines:
                    any_diff = True
                    print(f"\n[{oc.get('case_id')}]")
                    print("\n".join(lines))
            for oc, nc in zip(original_covs, covs):
                if oc != nc:
                    any_diff = True
                    print(f"\n[{oc.get('coverage_id')}] 覆盖项已修改")
            if not any_diff:
                print("（无字段级变更）")
            working["pipeline_stage"] = "08_reviewed"
            working["reviewed_at"] = _utc_now()
            working["designer_edit_count"] = edit_count
            working["review_notes"] = _prompt("审查备注（可选）", working.get("review_notes", ""))
            return working
        elif choice == "6":
            eprint("已放弃修改，未写入文件。")
            raise SystemExit(0)
        else:
            eprint("无效选项，请重试。")


def reviewed_payload(data: dict[str, Any], pass_through: bool = False) -> dict[str, Any]:
    if pass_through:
        out = copy.deepcopy(data)
        out["pipeline_stage"] = "08_reviewed"
        out["reviewed_at"] = _utc_now()
        out["designer_edit_count"] = 0
        out.setdefault("review_notes", "launcher 自动透传，未进行人工修订")
        return out
    return interactive_session(data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S8 交互式审查：07_traceability.json → 08_reviewed.json"
    )
    parser.add_argument("--in", dest="in_path", metavar="PATH", required=True, help="输入 07_traceability.json")
    parser.add_argument("--out", dest="out_path", metavar="PATH", required=True, help="输出 08_reviewed.json")
    parser.add_argument(
        "--pass-through",
        action="store_true",
        help="非交互透传（供 launcher 全流程使用，不弹出菜单）",
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
        out_obj = reviewed_payload(loaded, pass_through=args.pass_through)
    except SystemExit as ex:
        return int(ex.code) if ex.code is not None else 0

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as ex:
        eprint(f"错误：无法写入：{ex}")
        return 1

    edits = out_obj.get("designer_edit_count", 0)
    print(f"已写入 {out_path}（设计者修订 {edits} 处）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
