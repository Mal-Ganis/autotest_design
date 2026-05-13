# AutoTestDesign JSON 契约（v1 — S0～S4）

> **冻结规则**：字段只增不删。破坏性变更须发变更日志，并由契约负责人同步 `data/mock/` 与本文档。  
> **S3～S4**：由 P2 维护（风险与覆盖项）。

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

## S3 — `03_with_risk.json`（`risk_prioritize.py` 输出）

在 S2 每条需求上**追加**风险评估字段（**FR 2.0**）。保留 S2 全部字段。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pipeline_stage` | string | 建议 | 固定：`03_with_risk` |
| `risk_assessed_at` | string | 建议 | ISO8601 UTC，如 `2026-05-11T12:00:00Z` |
| `requirements[].risk_score` | number | 是 | 0～100，分值越高表示风险越大 |
| `requirements[].test_priority` | string | 是 | `High` \| `Medium` \| `Low` |
| `requirements[].risk_rationale` | string[] | 建议 | 简短可解释因子列表（便于报告与审计） |

### 示例片段

```json
{
  "schema_version": "1.0",
  "pipeline_stage": "03_with_risk",
  "risk_assessed_at": "2026-05-11T12:00:00Z",
  "requirements": [
    {
      "req_id": "FR-LOGIN-001",
      "raw_text": "...",
      "risk_score": 41.0,
      "test_priority": "Medium",
      "risk_rationale": ["含 1 处数据范围/边界约束"]
    }
  ]
}
```

---

## S4 — `04_coverage_items.json`（`coverage_items.py` 输出）

在 S3 基础上增加顶层 **`coverage_items`** 数组（覆盖项识别，对应 Mainly 流程中的「Coverage Item Identification」可落盘形式）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pipeline_stage` | string | 建议 | 固定：`04_coverage_items` |
| `coverage_items_generated_at` | string | 建议 | ISO8601 UTC |
| `requirements` | array | 是 | 与 S3 相同条目（透传，便于单文件追溯） |
| `coverage_items` | array | 是 | 覆盖项列表 |
| `coverage_items[].coverage_id` | string | 是 | 稳定 ID，如 `COV-001` |
| `coverage_items[].description` | string | 是 | 人类可读的覆盖意图说明 |
| `coverage_items[].linked_req_ids` | string[] | 是 | 关联的需求 ID，至少一项 |
| `coverage_items[].focus` | string | 建议 | 粗分类，如 `data_range`、`condition_branch`、`expected_action`、`general_functional`、`risk_negative` |
| `coverage_items[].notes` | string | 否 | 附加说明 |

### 示例片段

```json
{
  "schema_version": "1.0",
  "pipeline_stage": "04_coverage_items",
  "coverage_items_generated_at": "2026-05-11T12:00:00Z",
  "requirements": [],
  "coverage_items": [
    {
      "coverage_id": "COV-001",
      "description": "验证「用户名」取值区间与边界（等价类划分 + 边界值分析），依据需求 FR-LOGIN-001",
      "linked_req_ids": ["FR-LOGIN-001"],
      "focus": "data_range",
      "notes": "范围线索：..."
    }
  ]
}
```

**下游（P3）**：读取 `04_coverage_items.json`，主要消费 `coverage_items` 与 `requirements` 中的 `req_id` / 风险字段，生成 `05_strategies.json`。
