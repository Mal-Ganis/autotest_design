#!/usr/bin/env python3
"""
S2 — 需求结构化（FR 1.1）
读入 01_ingested.json，基于规则/正则抽取 input_fields、data_ranges、conditions、expected_actions。
可选 `--use-ai`：在配置 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY` 时用兼容 API 补充/合并结构化结果（见 `llm_optional.py`）。
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


# --- 规则：长度 / 范围（字段优先匹配「XX长度」形式，避免吞掉「必须在」） ---
RE_LEN_CN = re.compile(
    r"(?P<field>[\u4e00-\u9fff]{1,8})长度(?:必须在|为|在|必须)?"
    r"(?P<a>\d+)\s*(?:到|至|-|~)\s*(?P<b>\d+)\s*(?:个)?(?:字符|位|字节)?",
    re.UNICODE,
)
RE_LEN_SUFFIX = re.compile(
    r"(?P<a>\d+)\s*(?:到|至|-|~)\s*(?P<b>\d+)\s*(?:个)?(?:字符|位)",
    re.UNICODE,
)
RE_IF_THEN = re.compile(
    r"(?:如果|若)(?P<cond>.{2,80}?)(?:则|那么|,|，)(?P<act>.{2,80}?)(?:[。.]|$)",
    re.UNICODE,
)


def extract_fields(text: str) -> dict[str, Any]:
    input_fields: list[dict[str, Any]] = []
    data_ranges: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    expected_actions: list[dict[str, Any]] = []

    # 用户名、密码等显式名词（简单窗口）
    for m in re.finditer(r"(用户名|密码|邮箱|手机号|验证码|会话|账户)", text):
        name = m.group(1)
        if not any(f.get("name") == name for f in input_fields):
            input_fields.append({"name": name, "kind": "string", "notes": ""})

    # 长度范围（先抽中文「字段长度」再抽裸数字区间，去重同 min/max/field）
    seen_rng: set[tuple[Any, ...]] = set()
    for rx in (RE_LEN_CN, RE_LEN_SUFFIX):
        for m in rx.finditer(text):
            field_raw = m.groupdict().get("field") or _infer_field_near(text, m.start())
            field = (field_raw or "unknown").strip()
            a = int(m.group("a"))
            b = int(m.group("b"))
            lo, hi = (a, b) if a <= b else (b, a)
            key = (field, lo, hi, "chars")
            if key in seen_rng:
                continue
            seen_rng.add(key)
            data_ranges.append(
                {
                    "field": field,
                    "min": lo,
                    "max": hi,
                    "unit": "chars",
                    "closed": True,
                    "raw_span": m.group(0),
                }
            )
            if field != "unknown" and not any(
                f.get("name") == field for f in input_fields
            ):
                input_fields.append({"name": field, "kind": "string", "notes": ""})

    # 如果…则…
    for m in RE_IF_THEN.finditer(text):
        cond = m.group("cond").strip()
        act = m.group("act").strip()
        conditions.append({"expr": cond, "trace": "regex:if-then"})
        expected_actions.append({"action": act, "trace": "regex:if-then"})

    # 安全 / 锁定关键词
    if re.search(r"锁定|封禁|冻结", text):
        expected_actions.append(
            {"action": "限制登录或锁定账户", "trace": "keyword:锁定"}
        )
    if re.search(r"密码错误|登录失败", text):
        conditions.append({"expr": "登录失败或密码错误次数超过阈值", "trace": "keyword:登录"})

    # 去重（粗）
    input_fields = _dedupe_dicts(input_fields, key=lambda x: x.get("name"))
    data_ranges = _dedupe_dicts(
        data_ranges, key=lambda x: (x.get("field"), x.get("min"), x.get("max"))
    )

    return {
        "input_fields": input_fields,
        "data_ranges": data_ranges,
        "conditions": conditions,
        "expected_actions": expected_actions,
    }


def _infer_field_near(text: str, pos: int) -> str:
    window = text[max(0, pos - 12) : pos + 1]
    for name in ("用户名", "密码", "邮箱", "手机"):
        if name in window:
            return name
    return "unknown"


def _dedupe_dicts(items: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        k = key(it)
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def structure_requirement(req: dict[str, Any], *, use_ai: bool = False) -> dict[str, Any]:
    raw = str(req.get("raw_text") or "")
    parsed = extract_fields(raw)
    if use_ai:
        try:
            from llm_optional import ai_extract_structure, merge_structure, openai_configured

            if openai_configured():
                ai = ai_extract_structure(raw)
                parsed = merge_structure(parsed, ai)
            else:
                print("提示：已指定 --use-ai 但未配置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，仍仅使用规则。", file=sys.stderr)
        except ImportError as ex:
            print(f"提示：无法加载 LLM 模块（{ex}），请 pip install openai python-dotenv", file=sys.stderr)
    out = {
        "req_id": req.get("req_id"),
        "raw_text": req.get("raw_text"),
        "source": req.get("source"),
        **parsed,
    }
    if "extra" in req:
        out["extra"] = req["extra"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S2 结构化：01_ingested.json → 02_structured.json（FR 1.1）"
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        metavar="PATH",
        required=True,
        help="输入 01_ingested.json",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        metavar="PATH",
        required=True,
        help="输出 02_structured.json",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="启用大模型 API 补充结构化字段（需 .env：OPENAI_API_KEY 或 DEEPSEEK_API_KEY）",
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

    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        eprint("错误：输入缺少 requirements 数组。")
        return 1

    structured = [structure_requirement(r, use_ai=args.use_ai) for r in reqs if isinstance(r, dict)]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    out_obj: dict[str, Any] = {
        "schema_version": data.get("schema_version", "1.0"),
        "pipeline_stage": "02_structured",
        "structured_at": now,
        "requirements": structured,
    }
    # 保留溯源
    if data.get("source_files"):
        out_obj["source_files"] = data["source_files"]

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as ex:
        eprint(f"错误：无法写入：{ex}")
        return 1

    print(f"已写入 {out_path}（{len(structured)} 条需求）{'（已请求 --use-ai）' if args.use_ai else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
