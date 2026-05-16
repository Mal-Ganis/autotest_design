"""
可选大模型增强（OpenAI **兼容** HTTP API）
- 从项目根目录加载 .env（不提交 .env；见 .env.example）
- 支持：OpenAI 官方 / Azure 等（OPENAI_*）；**DeepSeek**（DEEPSEEK_* + MODEL）
- 无密钥或未安装依赖时，各脚本仍走原有规则逻辑
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv_if_available() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass


def _get_llm_config() -> dict[str, Any] | None:
    """
    返回 {api_key, base_url?, model, provider}。
    优先级：OPENAI_API_KEY 已填 → 用 OpenAI 系变量；否则 DEEPSEEK_API_KEY → DeepSeek。
    """
    load_dotenv_if_available()
    oa = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if oa:
        base = (os.environ.get("OPENAI_BASE_URL") or "").strip() or None
        model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
        return {
            "api_key": oa,
            "base_url": base.rstrip("/") if base else None,
            "model": model,
            "provider": "openai_compatible",
        }
    ds = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if ds:
        base = (
            os.environ.get("DEEPSEEK_API_URL")
            or os.environ.get("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com/v1"
        )
        base = str(base).strip().rstrip("/")
        raw_model = (
            os.environ.get("MODEL")
            or os.environ.get("DEEPSEEK_MODEL")
            or "deepseek-v4-pro"
        ).strip()
        model = _normalize_model_id(raw_model, "deepseek")
        return {
            "api_key": ds,
            "base_url": base,
            "model": model,
            "provider": "deepseek",
        }
    return None


def _normalize_model_id(model: str, provider: str) -> str:
    """
    将 .env 中的 MODEL 转为 API 接受的 id。
    例如 OpenRouter 风格 deepseek/deepseek-v4-pro → deepseek-v4-pro（官方仅认后者）。
    """
    m = model.strip()
    if not m:
        return m
    if provider == "deepseek" and "/" in m:
        m = m.rsplit("/", 1)[-1].strip()
    return m


def openai_configured() -> bool:
    """是否已配置任一兼容接口（保留函数名供各脚本 import）。"""
    return _get_llm_config() is not None


def _client():
    from openai import OpenAI

    cfg = _get_llm_config()
    if not cfg:
        raise RuntimeError("未配置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY")
    kwargs: dict[str, Any] = {"api_key": cfg["api_key"]}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return OpenAI(**kwargs)


def model_name() -> str:
    cfg = _get_llm_config()
    if not cfg:
        return "gpt-4o-mini"
    provider = str(cfg.get("provider") or "")
    return _normalize_model_id(str(cfg["model"]), provider)


def _parse_json_response(raw: str) -> dict[str, Any] | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        try:
            out = json.loads(m.group(1).strip())
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def chat_json_object(system: str, user: str) -> dict[str, Any] | None:
    """调用 Chat Completions，解析为 JSON 对象。失败返回 None。"""
    if not _get_llm_config():
        return None
    try:
        client = _client()
    except RuntimeError:
        return None
    model = model_name()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_err: Exception | None = None
    for use_json_mode in (True, False):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
                "timeout": 120.0,
            }
            if use_json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            raw = (resp.choices[0].message.content or "").strip()
            parsed = _parse_json_response(raw)
            if parsed is not None:
                return parsed
        except Exception as ex:
            last_err = ex
            continue
    if last_err:
        print(f"[llm_optional] 调用失败，将回退规则结果：{last_err}", file=sys.stderr)
    return None


STRUCTURE_SYSTEM = """你是软件需求分析助手。只输出一个 JSON 对象，不要 markdown。
JSON 顶层键必须为：input_fields, data_ranges, conditions, expected_actions。
- input_fields: 数组，元素为 {"name": string, "kind": "string"|"number"|"boolean"|"unknown", "notes": string}
- data_ranges: 数组，元素为 {"field": string, "min": number, "max": number, "unit": "chars"|"count"|"seconds", "closed": true, "raw_span": string}
- conditions: 数组，元素为 {"expr": string, "trace": string}
- expected_actions: 数组，元素为 {"action": string, "trace": string}
若某类无信息，用空数组 []。使用中文。"""


def ai_extract_structure(raw_text: str) -> dict[str, Any] | None:
    user = f"请从下列需求原文中提取结构化信息：\n\n{raw_text}"
    data = chat_json_object(STRUCTURE_SYSTEM, user)
    if not isinstance(data, dict):
        return None
    out: dict[str, Any] = {}
    for key in ("input_fields", "data_ranges", "conditions", "expected_actions"):
        val = data.get(key)
        out[key] = val if isinstance(val, list) else []
    return out


RISK_SYSTEM = """你是软件测试风险评估助手。只输出一个 JSON 对象。
键：risk_score (0-100 的数字), test_priority ("High"|"Medium"|"Low"), risk_rationale (字符串数组，简短中文理由)。
依据需求文本中的安全、账户、会话、支付、合规等语义判断风险。"""


def ai_assess_risk(raw_text: str, rule_hint: str) -> dict[str, Any] | None:
    user = f"需求原文：\n{raw_text}\n\n已有规则引擎参考（可修正）：\n{rule_hint}\n\n请独立给出 JSON。"
    data = chat_json_object(RISK_SYSTEM, user)
    if not isinstance(data, dict):
        return None
    try:
        score = float(data.get("risk_score", 0))
        score = max(0.0, min(100.0, score))
    except (TypeError, ValueError):
        return None
    tp = str(data.get("test_priority") or "Medium")
    if tp not in ("High", "Medium", "Low"):
        tp = "Medium"
    rat = data.get("risk_rationale")
    if not isinstance(rat, list):
        rat = [str(rat)] if rat else []
    rat = [str(x) for x in rat if str(x).strip()]
    return {"risk_score": score, "test_priority": tp, "risk_rationale": rat}


def _priority_rank(p: str) -> int:
    return {"High": 3, "Medium": 2, "Low": 1}.get(p, 1)


def _rank_to_priority(r: int) -> str:
    return {3: "High", 2: "Medium", 1: "Low"}.get(r, "Low")


def merge_structure(rule: dict[str, Any], ai: dict[str, Any] | None) -> dict[str, Any]:
    """合并规则结果与 LLM 结果：列表做并集去重。"""
    if not ai:
        return dict(rule)
    out = dict(rule)

    def _field_key(f: dict[str, Any]) -> Any:
        return f.get("name")

    def _range_key(x: dict[str, Any]) -> Any:
        return (x.get("field"), x.get("min"), x.get("max"), x.get("unit"))

    def _cond_key(x: dict[str, Any]) -> Any:
        return x.get("expr")

    def _act_key(x: dict[str, Any]) -> Any:
        return x.get("action")

    def merge_lists(a: list, b: list, keyfn) -> list:
        seen: set[Any] = set()
        res: list = []
        for src in (a, b):
            for it in src:
                if not isinstance(it, dict):
                    continue
                k = keyfn(it)
                if k in seen:
                    continue
                seen.add(k)
                res.append(it)
        return res

    out["input_fields"] = merge_lists(
        list(rule.get("input_fields") or []),
        list(ai.get("input_fields") or []),
        _field_key,
    )
    out["data_ranges"] = merge_lists(
        list(rule.get("data_ranges") or []),
        list(ai.get("data_ranges") or []),
        _range_key,
    )
    out["conditions"] = merge_lists(
        list(rule.get("conditions") or []),
        list(ai.get("conditions") or []),
        _cond_key,
    )
    out["expected_actions"] = merge_lists(
        list(rule.get("expected_actions") or []),
        list(ai.get("expected_actions") or []),
        _act_key,
    )
    return out


def blend_risk(
    rule_score: float,
    rule_priority: str,
    rule_rationale: list[str],
    ai: dict[str, Any] | None,
    *,
    ai_weight: float = 0.45,
) -> tuple[float, str, list[str]]:
    """规则与 LLM 混合：分数加权；优先级取更保守（更高）的一档；理由合并去重。"""
    if not ai:
        return rule_score, rule_priority, list(rule_rationale)
    ai_score = float(ai["risk_score"])
    blended = (1.0 - ai_weight) * rule_score + ai_weight * ai_score
    blended = max(0.0, min(100.0, round(blended, 1)))
    rp = _priority_rank(rule_priority)
    ap = _priority_rank(str(ai.get("test_priority", "Medium")))
    final_p = _rank_to_priority(max(rp, ap))
    rats = list(rule_rationale)
    for line in ai.get("risk_rationale") or []:
        s = str(line).strip()
        if s and s not in rats:
            rats.append(s)
    tag = "（大模型 API 与规则引擎融合评估）"
    if not any(tag in x for x in rats):
        rats.append(tag)
    return blended, final_p, rats
