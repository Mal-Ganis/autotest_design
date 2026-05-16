#!/usr/bin/env python3
"""
S3 — 风险分析与测试优先级（FR 2.0）
读入 02_structured.json，为每条需求追加 risk_score、test_priority 及简要依据。
采用可解释的启发式规则（关键词、条件/动作数量、业务敏感度）。可选 `--use-ai`：在配置
`OPENAI_API_KEY` 时与 OpenAI 兼容 API 融合评估（见 `scripts/llm_optional.py`）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


# 高风险语义（安全、账户、会话）
_RE_SECURITY = re.compile(
    r"密码|锁定|封禁|冻结|会话|超时|验证码|暴力|登录失败|权限|令牌|token",
    re.IGNORECASE,
)


def _clamp_score(x: float) -> float:
    return max(0.0, min(100.0, round(x, 1)))


def assess_requirement(req: dict[str, Any]) -> tuple[float, str, list[str]]:
    """返回 (risk_score, test_priority, rationale_lines)。"""
    raw = str(req.get("raw_text") or "")
    factors: list[str] = []
    score = 25.0  # 基线

    if _RE_SECURITY.search(raw):
        score += 28.0
        factors.append("文本含安全/账户/会话相关语义")

    conds = req.get("conditions") or []
    acts = req.get("expected_actions") or []
    if isinstance(conds, list) and len(conds) >= 1:
        score += min(18.0, 6.0 * len(conds))
        factors.append(f"识别到 {len(conds)} 条条件分支")
    if isinstance(acts, list) and len(acts) >= 1:
        score += min(14.0, 5.0 * len(acts))
        factors.append(f"识别到 {len(acts)} 条预期动作")

    ranges = req.get("data_ranges") or []
    if isinstance(ranges, list):
        score += min(12.0, 4.0 * len(ranges))
        if ranges:
            factors.append(f"含 {len(ranges)} 处数据范围/边界约束")

    fields = req.get("input_fields") or []
    if isinstance(fields, list) and len(fields) >= 3:
        score += 6.0
        factors.append("输入域较多，组合场景复杂")

    extra = req.get("extra") if isinstance(req.get("extra"), dict) else {}
    pri_extra = str(extra.get("priority", "")).strip().lower()
    if pri_extra in ("high", "高", "h"):
        score += 15.0
        factors.append("来源标注为高优先级需求")

    # 纯格式类短需求略降权（避免与复杂规则同分）
    if len(raw) < 40 and not conds and not _RE_SECURITY.search(raw):
        score -= 6.0
        factors.append("描述较短且无分支，风险略下调")

    score = _clamp_score(score)

    # 来源明确标注「高优先级」时，与作业/test_priority 对齐（不低于 High 档）
    if pri_extra in ("high", "高", "h"):
        score = _clamp_score(max(score, 72.0))

    if score >= 70.0:
        tp = "High"
    elif score >= 40.0:
        tp = "Medium"
    else:
        tp = "Low"

    rationale = factors if factors else ["默认基线评估"]
    return score, tp, rationale


def prioritize_payload(data: dict[str, Any], *, use_ai: bool = False) -> dict[str, Any]:
    reqs_in = data.get("requirements")
    if not isinstance(reqs_in, list):
        raise ValueError("输入缺少 requirements 数组")

    llm = None
    if use_ai:
        try:
            from llm_optional import ai_assess_risk, blend_risk, openai_configured

            if openai_configured():
                llm = (ai_assess_risk, blend_risk)
            else:
                eprint("提示：已指定 --use-ai 但未配置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，仍仅使用规则引擎。")
        except ImportError as ex:
            eprint(f"提示：无法加载 LLM 模块（{ex}），请 pip install openai python-dotenv")

    out_reqs: list[dict[str, Any]] = []
    for r in reqs_in:
        if not isinstance(r, dict):
            continue
        score, tp, rationale = assess_requirement(r)
        if llm is not None:
            ai_assess_risk_fn, blend_risk_fn = llm
            hint = f"规则引擎：risk_score={score}, test_priority={tp}, rationale={rationale}"
            ai = ai_assess_risk_fn(str(r.get("raw_text") or ""), hint)
            score, tp, rationale = blend_risk_fn(score, tp, rationale, ai)
        item = {**r}
        item["risk_score"] = score
        item["test_priority"] = tp
        item["risk_rationale"] = rationale
        out_reqs.append(item)

    now = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    )

    out: dict[str, Any] = {
        "schema_version": data.get("schema_version", "1.0"),
        "pipeline_stage": "03_with_risk",
        "risk_assessed_at": now,
        "requirements": out_reqs,
    }
    if data.get("source_files"):
        out["source_files"] = data["source_files"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S3 风险与优先级：02_structured.json → 03_with_risk.json（FR 2.0）"
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        metavar="PATH",
        required=True,
        help="输入 02_structured.json",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        metavar="PATH",
        required=True,
        help="输出 03_with_risk.json",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="启用大模型 API 与规则结果融合（需 .env：OPENAI_API_KEY 或 DEEPSEEK_API_KEY）",
    )
    args = parser.parse_args()

    in_path = Path(args.in_path)
    if not in_path.is_file():
        eprint(f"错误：找不到输入文件：{in_path}")
        return 1

    try:
        with in_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        eprint(f"错误：无法读取 JSON：{ex}")
        return 1

    try:
        out_obj = prioritize_payload(data, use_ai=args.use_ai)
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

    n = len(out_obj.get("requirements") or [])
    suffix = "（已请求 --use-ai）" if args.use_ai else ""
    print(f"已写入 {out_path}（{n} 条需求已标注风险与优先级）{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
