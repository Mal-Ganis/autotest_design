# AutoTestDesign JSON 契约（v1 — S0～S2）

> **冻结规则**：字段只增不删。破坏性变更须发变更日志，并由 P1 同步 `data/mock/` 与本文档。  
> **下游**：P2 在本文档基础上扩展 S3～S4（`risk_score`、`test_priority`、`coverage_items` 等）。

## 通用约定

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 契约版本，当前 `"1.0"` |
| `pipeline_stage` | string | 可选；标识产物阶段，如 `00_raw`、`01_ingested`、`02_structured` |

所有 JSON 文件均为 **UTF-8** 编码。

---

## S0 — `data/mock/00_input_raw.json`（人工 / Mock 原始输入）

流水线起点。可由人工编写，也可由组内工具生成。

```json
{
  "schema_version": "1.0",
  "pipeline_stage": "00_raw",
  "document_id": "optional-string",
  "requirements": [
    {
      "req_id": "REQ-001",
      "raw_text": "单条需求的完整原文",
      "source": "csv",
      "extra": { "priority": "High", "type": "functional" }
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `requirements` | array | 是 | 需求条目列表 |
| `requirements[].req_id` | string | 是 | 稳定 ID，贯穿全链路 |
| `requirements[].raw_text` | string | 是 | 未结构化原文 |
| `requirements[].source` | string | 是 | 取值：`csv` \| `text` \| `stdin` |
| `requirements[].extra` | object | 否 | CSV 附加列等键值 |

---

## S1 — `01_ingested.json`（`ingest.py` 输出）

在 S0 基础上统一字段、校验 UTF-8、合并 CSV 列等，**不改变语义**，不解析 NLP。

| 字段 | 说明 |
|------|------|
| `pipeline_stage` | 固定建议：`01_ingested` |
| `ingested_at` | string，ISO8601 可选 |
| `requirements[]` | 与 S0 条目一一对应；每条至少含 `req_id`、`raw_text`、`source` |

可选全局字段：

| 字段 | 说明 |
|------|------|
| `source_files` | string[]，记录曾合并的文件名 |

---

## S2 — `02_structured.json`（`structure.py` 输出）

在 S1 每条需求上增加结构化字段（**FR 1.1**）。

```json
{
  "schema_version": "1.0",
  "pipeline_stage": "02_structured",
  "structured_at": "2026-05-11T12:00:00",
  "requirements": [
    {
      "req_id": "REQ-001",
      "raw_text": "...",
      "source": "text",
      "input_fields": [
        { "name": "用户名", "kind": "string", "notes": "" }
      ],
      "data_ranges": [
        {
          "field": "用户名",
          "min": 3,
          "max": 20,
          "unit": "chars",
          "closed": true,
          "raw_span": "3到20个字符"
        }
      ],
      "conditions": [
        { "expr": "密码错误次数 > 5", "trace": "keyword:密码" }
      ],
      "expected_actions": [
        { "action": "锁定账户", "trace": "keyword:锁定" }
      ]
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `input_fields` | array | 输入域/数据项；`kind` 如 `string|number|boolean|unknown` |
| `data_ranges` | array | 数值/长度范围；`unit` 如 `chars|count|seconds` |
| `conditions` | array | 条件（自然语言或简化表达式） |
| `expected_actions` | array | 预期系统动作/输出 |

**说明**：`trace` 用于标注规则命中依据，便于调试；下游可忽略。

---

## P2 起扩展占位（勿删 S2 字段）

P2 将在 `02` 之后生成 `03_with_risk.json` 等，在每条 `requirements[]` 上**追加**例如：

- `risk_score`（number）
- `test_priority`（`High` \| `Medium` \| `Low`）

具体见 P2 提交的 SCHEMA 增补节。
