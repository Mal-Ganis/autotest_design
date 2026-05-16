#!/usr/bin/env python3
"""
AutoTestDesign 流水线启动器 — 按顺序调用 S1～S9。
支持 --start-from 从中间步骤调试；任一步失败则 exit(1)。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if not (ROOT / "scripts" / "ingest.py").is_file():
    ROOT = Path.cwd()
SCRIPTS = ROOT / "scripts"
WORK = ROOT / "data" / "work"
MOCK = ROOT / "data" / "mock"
TARGET_REQ = ROOT / "target-login-app" / "requirements" / "00_input_raw.json"


def default_s0_input(*, use_mock: bool = False) -> Path:
    """作业默认：被测系统 target-login-app 的需求；仅开发接力时用 mock。"""
    if use_mock:
        return MOCK / "00_input_raw.json"
    if TARGET_REQ.is_file():
        return TARGET_REQ
    return MOCK / "00_input_raw.json"


STEPS: list[dict[str, str]] = [
  {
    "key": "ingest",
    "script": "ingest.py",
    "in": str(default_s0_input()),
    "out": str(WORK / "01_ingested.json"),
  },
  {
    "key": "structure",
    "script": "structure.py",
    "in": str(WORK / "01_ingested.json"),
    "out": str(WORK / "02_structured.json"),
  },
  {
    "key": "risk_prioritize",
    "script": "risk_prioritize.py",
    "in": str(WORK / "02_structured.json"),
    "out": str(WORK / "03_with_risk.json"),
  },
  {
    "key": "coverage_items",
    "script": "coverage_items.py",
    "in": str(WORK / "03_with_risk.json"),
    "out": str(WORK / "04_coverage_items.json"),
  },
  {
    "key": "strategies_and_prompts",
    "script": "strategies_and_prompts.py",
    "in": str(WORK / "04_coverage_items.json"),
    "out": str(WORK / "05_strategies.json"),
  },
  {
    "key": "blackbox_generate",
    "script": "blackbox_generate.py",
    "in": str(WORK / "05_strategies.json"),
    "out": str(WORK / "06_test_cases_draft.json"),
  },
  {
    "key": "traceability_and_analysis",
    "script": "traceability_and_analysis.py",
    "in": str(WORK / "06_test_cases_draft.json"),
    "out": str(WORK / "07_traceability.json"),
  },
  {
    "key": "interactive_review",
    "script": "interactive_review.py",
    "in": str(WORK / "07_traceability.json"),
    "out": str(WORK / "08_reviewed.json"),
  },
  {
    "key": "export_artifacts",
    "script": "export_artifacts.py",
    "in": str(WORK / "08_reviewed.json"),
    "out": str(WORK / "09_export_cases.json"),
  },
]

STEP_KEYS = [s["key"] for s in STEPS]
STEP_ALIASES = {k: k for k in STEP_KEYS}
STEP_ALIASES.update({
    "s1": "ingest", "s2": "structure", "s3": "risk_prioritize",
    "s4": "coverage_items", "s5": "strategies_and_prompts", "s6": "blackbox_generate",
    "s7": "traceability_and_analysis", "s8": "interactive_review", "s9": "export_artifacts",
})


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def resolve_start(key: str) -> str:
    k = key.strip().lower()
    if k in STEP_ALIASES:
        return STEP_ALIASES[k]
    if k in STEP_KEYS:
        return k
    raise ValueError(f"未知步骤：{key}；可选：{', '.join(STEP_KEYS)}")


def run_step(
    step: dict[str, str],
    *,
    raw_input: str | None,
    pass_through: bool,
    export_csv: bool,
    use_ai: bool,
    use_mock_s0: bool,
) -> int:
    script_path = SCRIPTS / step["script"]
    if not script_path.is_file():
        eprint(f"错误：找不到脚本 {script_path}")
        return 1

    in_path = step["in"]
    if step["key"] == "ingest":
        if raw_input:
            in_path = raw_input
        else:
            in_path = str(default_s0_input(use_mock=use_mock_s0))

    out_path = step["out"]
    cmd = [sys.executable, str(script_path), "--in", in_path, "--out", out_path]

    if step["key"] == "interactive_review" and pass_through:
        cmd.append("--pass-through")
    if step["key"] == "export_artifacts" and export_csv:
        cmd.extend(["--csv-dir", str(WORK)])
    if use_ai and step["key"] in ("structure", "risk_prioritize"):
        cmd.append("--use-ai")

    print(f"\n>>> [{step['key']}] {step['script']}")
    print(f"    输入: {in_path}")
    print(f"    输出: {out_path}")

    result = subprocess.run(cmd, cwd=str(ROOT), env=_child_env())
    if result.returncode != 0:
        eprint(f"错误：步骤 {step['key']} 失败，退出码 {result.returncode}")
        return result.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AutoTestDesign 流水线启动器（S1～S9）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "步骤名：\n  "
            + ", ".join(STEP_KEYS)
            + "\n\n示例：\n"
            "  python launcher.py\n"
            "  python launcher.py --start-from risk_prioritize\n"
            "  python launcher.py --export-csv\n"
            "  python launcher.py --export-csv --use-ai\n"
            "  python launcher.py --use-mock   # 仅用 data/mock 样例（非目标应用需求）\n"
        ),
    )
    parser.add_argument(
        "--start-from",
        metavar="STEP",
        default="ingest",
        help="从指定步骤开始（默认 ingest，即全流程）",
    )
    parser.add_argument(
        "--input",
        metavar="PATH",
        default=None,
        help="S1 ingest 的原始输入（默认 target-login-app/requirements/00_input_raw.json）",
    )
    parser.add_argument(
        "--use-mock",
        action="store_true",
        help="S1 使用 data/mock/00_input_raw.json（仅 P1/P2 离线开发，不测目标应用时用）",
    )
    parser.add_argument(
        "--pass-through",
        action="store_true",
        default=True,
        help="S8 非交互透传（默认开启，供自动化全流程）",
    )
    parser.add_argument(
        "--interactive-review",
        action="store_true",
        help="S8 进入交互菜单（覆盖 --pass-through）",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="S9 同时导出 CSV 到 data/work/",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="S2/S3 对 structure 与 risk_prioritize 传入 --use-ai（需 .env 中 OPENAI_API_KEY）",
    )
    args = parser.parse_args()

    try:
        start_key = resolve_start(args.start_from)
    except ValueError as ex:
        eprint(f"错误：{ex}")
        return 1

    if start_key not in STEP_KEYS:
        eprint(f"错误：无效起始步骤 {start_key}")
        return 1

    start_idx = STEP_KEYS.index(start_key)
    WORK.mkdir(parents=True, exist_ok=True)

    pass_through = args.pass_through and not args.interactive_review

    print(f"AutoTestDesign 流水线：从 [{start_key}] 执行至 [export_artifacts]")
    if args.use_mock:
        print(f"S1 使用 mock 样例：{MOCK / '00_input_raw.json'}")
    else:
        print(f"S1 默认需求（目标应用）：{default_s0_input()}")
    if args.input:
        print(f"S1 自定义输入覆盖：{args.input}")

    if args.use_ai:
        print("已启用 --use-ai：S2 structure 与 S3 risk_prioritize 将尝试调用 OpenAI 兼容 API（与规则融合）")

    for step in STEPS[start_idx:]:
        code = run_step(
            step,
            raw_input=args.input,
            pass_through=pass_through,
            export_csv=args.export_csv,
            use_ai=args.use_ai,
            use_mock_s0=args.use_mock,
        )
        if code != 0:
            return code

    print("\n=== 流水线完成 ===")
    print(f"最终产物：{WORK / '09_export_cases.json'}")
    if args.export_csv:
        print(f"CSV：{WORK / '09_export_cases.csv'}、{WORK / '09_export_risk.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
