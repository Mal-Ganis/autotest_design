#!/usr/bin/env python3
"""
S1 — 需求摄入（FR 1.0）
读入原始 CSV / 纯文本 / S0 JSON，写出统一的 01_ingested.json。
不调用 NLP；结构化由 structure.py 完成。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def ingest_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV 无表头")
        fields = [h.strip() for h in reader.fieldnames]
        id_key = _pick_column(
            fields, ("req_id", "ID", "id", "ReqID", "RequirementID")
        )
        desc_key = _pick_column(
            fields,
            ("description", "Description", "desc", "text", "Text", "需求描述"),
        )
        if not id_key or not desc_key:
            raise ValueError(
                "CSV 需包含 ID 列（如 req_id/ID）与描述列（如 description/Text）"
            )
        type_key = _pick_column(fields, ("type", "Type"))
        pri_key = _pick_column(fields, ("priority", "Priority"))
        for row in reader:
            rid = (row.get(id_key) or "").strip()
            text = (row.get(desc_key) or "").strip()
            if not rid and not text:
                continue
            if not rid:
                rid = _fallback_id(len(rows))
            extra: dict[str, Any] = {}
            if type_key and row.get(type_key):
                extra["type"] = row[type_key].strip()
            if pri_key and row.get(pri_key):
                extra["priority"] = row[pri_key].strip()
            rows.append(
                {
                    "req_id": rid,
                    "raw_text": text,
                    "source": "csv",
                    **({"extra": extra} if extra else {}),
                }
            )
    return rows


def _pick_column(candidates: list[str], names: tuple[str, ...]) -> str | None:
    lower = {c.lower(): c for c in candidates}
    for n in names:
        if n in candidates:
            return n
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def _fallback_id(index: int) -> str:
    return f"REQ-{index + 1:04d}"


def ingest_text_lines(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if len(blocks) <= 1:
        blocks = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(blocks):
        out.append(
            {
                "req_id": _fallback_id(i),
                "raw_text": raw,
                "source": "text",
            }
        )
    return out


def ingest_stdin_single() -> list[dict[str, Any]]:
    raw = sys.stdin.read().strip()
    if not raw:
        return []
    return [
        {
            "req_id": "REQ-STDIN-001",
            "raw_text": raw,
            "source": "stdin",
        }
    ]


def ingest_json_s0(data: dict[str, Any]) -> list[dict[str, Any]]:
    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        raise ValueError("JSON 缺少 requirements 数组")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(reqs):
        if not isinstance(item, dict):
            continue
        rid = str(item.get("req_id") or _fallback_id(i)).strip()
        raw_text = str(item.get("raw_text") or "").strip()
        source = str(item.get("source") or "text").strip().lower()
        if source not in ("csv", "text", "stdin"):
            source = "text"
        row: dict[str, Any] = {
            "req_id": rid,
            "raw_text": raw_text,
            "source": source,
        }
        extra = item.get("extra")
        if isinstance(extra, dict) and extra:
            row["extra"] = extra
        out.append(row)
    return out


def normalize_requirements(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        rid = str(it.get("req_id") or _fallback_id(i)).strip()
        if rid in seen:
            rid = f"{rid}-dup-{i}"
        seen.add(rid)
        entry = {
            "req_id": rid,
            "raw_text": str(it.get("raw_text") or "").strip(),
            "source": str(it.get("source") or "text"),
        }
        if "extra" in it and isinstance(it["extra"], dict):
            entry["extra"] = it["extra"]
        out.append(entry)
    return out


def build_output(
    requirements: list[dict[str, Any]], source_files: list[str]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "pipeline_stage": "01_ingested",
        "ingested_at": now,
        "requirements": requirements,
    }
    if source_files:
        payload["source_files"] = source_files
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="S1 摄入：CSV / 文本 / S0 JSON → 01_ingested.json（FR 1.0）"
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        metavar="PATH",
        help="输入文件路径；使用 - 表示从标准输入读入单条需求文本",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        metavar="PATH",
        required=True,
        help="输出 01_ingested.json 路径",
    )
    parser.add_argument(
        "--format",
        choices=("auto", "csv", "text", "json"),
        default="auto",
        help="输入格式；auto 根据扩展名推断（.json/.csv/其他为文本）",
    )
    args = parser.parse_args()

    if not args.in_path:
        parser.print_help()
        eprint("错误：必须指定 --in（文件路径或 -）。")
        return 1

    in_path = args.in_path
    source_files: list[str] = []
    requirements: list[dict[str, Any]] = []

    try:
        if in_path == "-":
            requirements = ingest_stdin_single()
            source_files.append("<stdin>")
        else:
            path = Path(in_path)
            if not path.is_file():
                eprint(f"错误：找不到输入文件：{path}")
                return 1
            source_files.append(str(path))
            fmt = args.format
            if fmt == "auto":
                suf = path.suffix.lower()
                if suf == ".csv":
                    fmt = "csv"
                elif suf == ".json":
                    fmt = "json"
                else:
                    fmt = "text"

            if fmt == "csv":
                requirements = ingest_csv(path)
            elif fmt == "json":
                data = load_json(path)
                requirements = ingest_json_s0(data)
            elif fmt == "text":
                requirements = ingest_text_lines(path)
            else:
                eprint("内部错误：未知格式")
                return 1

        requirements = normalize_requirements(requirements)
        if not requirements:
            eprint("错误：未解析到任何需求条目。")
            return 1

        out_obj = build_output(requirements, source_files)
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"已写入 {out_path}（{len(requirements)} 条需求）")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as ex:
        eprint(f"错误：{ex}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
