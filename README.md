# AutoTestDesign 工具 — 使用说明（新手向）

本文件面向**刚接触命令行、Python 或本项目的同学**，尽量把每一步写清楚。若你已有经验，可直接看 **「4. 第一次跑通（复制粘贴版）」** 和 **「5. 目录与文件是干什么的」**。当前流水线已实现 **S1～S9 全流程**（P1：摄入与结构化；P2：风险与覆盖项；P3：策略分配与黑盒用例生成；P4：可追溯、交互审查、导出与启动器）。

**课程作业相关 Markdown**（风险报告、测试计划节选等）在 **`Document/`** 目录，见 **「10. 课程交付物与 Document 文档」**。

### 组内同步：工具侧已实现什么、如何「驱动整条程序」

| 分工 | 已实现内容 |
|------|------------|
| **P1** | `scripts/ingest.py`、`structure.py`；S0→S2；`data/mock/00～02` |
| **P2** | `risk_prioritize.py`、`coverage_items.py`；S3→S4；mock `03～04` |
| **P3** | `strategies_and_prompts.py`、`blackbox_generate.py`；S5→S6；mock `05～06` |
| **P4** | `traceability_and_analysis.py`、`interactive_review.py`、`export_artifacts.py`、`launcher.py`；**`web_app/`** 全链路 Web；**`tests_target/`**；S7→S9 与 mock `07～09` |
| **可选 LLM** | 根目录 `.env`（模板 **`.env.example`**）+ `launcher.py --use-ai` 或 Web 勾选「S2/S3 启用 LLM」；支持 **OpenAI 兼容** 与 **DeepSeek**（`DEEPSEEK_API_KEY`、`DEEPSEEK_API_URL`、`MODEL`）；**不传 `--use-ai` 时行为与原先纯规则一致** |

**三种驱动方式**（任选；契约一律见 `contracts/SCHEMA.md`）：

| 方式 | 适用 | 怎么做 |
|------|------|--------|
| **A. launcher** | 一键跑通、CI、交作业复现 | `python launcher.py --export-csv`；可加 `--use-ai`（S2/S3 融合 LLM，需 `.env`）；`--start-from <步骤名>` 从中部调试 |
| **B. Web** | 演示、**需求导入（S1）**、流水线、审查、浏览产物 | `pip install -r requirements.txt` 后：`python web_app/server.py`，浏览器 **http://127.0.0.1:8765/**；推荐流程见 [`Document/AutoTestDesign_运行与改动说明.md`](Document/AutoTestDesign_运行与改动说明.md) **§4 流程 B** |
| **C. 分步脚本** | 只调某一步 | 各脚本 `python scripts/<名>.py -h`；`--in` / `--out` 路径见本文 **§4** 与 SCHEMA |

更完整的**功能清单、全部使用流程（A～F）、Web API、演示顺序与排错**见：**[`Document/AutoTestDesign_运行与改动说明.md`](Document/AutoTestDesign_运行与改动说明.md)**。

---

## 1. 先搞清楚：这个仓库里有两样不同的东西

容易混淆，请先记住下面这句话：

| 名字                     | 是什么                                                                                            | 和作业的关系                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **AutoTestDesign 工具**  | 用 Python 写的「测试设计流水线」：读需求 → 写出一串 JSON 文件，供后面同学继续做风险、用例、导出等 | 这是你们**要开发/拼接**的「工具」                                                                  |
| **目标应用（被测系统）** | 本仓库里的 `target-login-app`：一个**示例网页登录系统**                                           | 这是**用来被测的软件**，不是工具本身；风险报告、测试计划写的是**它**，不是写 AutoTestDesign 的代码 |

**本 README 覆盖「AutoTestDesign 工具」完整流水线 S1～S9（含 P4 导出与 launcher）。**
**想启动那个登录网站做演示**时，请看子目录里的说明：[`target-login-app/README.md`](target-login-app/README.md)。

---

## 2. 开始之前：你需要本机已安装 Python

**Python** 是一种编程语言；我们写的 `scripts/ingest.py` 等需要用它执行。

### 2.1 怎么检查有没有 Python？

1. 打开**终端**（见下一小节）。
2. 输入下面命令后按回车：

```text
python --version
```

- 若显示 `Python 3.10` 或更高（如 3.11、3.12），**可以**继续跑根目录 `scripts/` 流水线。
- **`target-login-app`** 子项目 README 写明 **Python 3.9+**；若你本机为 3.9～3.10，请先以子项目 README 为准试跑目标应用。
- 若提示「不是内部或外部命令」或版本过低，请先从 [python.org](https://www.python.org/downloads/) 安装，**安装时勾选 “Add Python to PATH”**（把 Python 加入系统路径，否则命令行找不到）。

也可以试：

```text
py --version
```

在部分 Windows 电脑上，用 `py` 比 `python` 更稳；下面凡写 `python` 的地方，若失败可改成 `py`。

### 2.2 怎么打开终端？（Windows）

任选一种即可：

- **资源管理器**进入本项目的文件夹，在地址栏输入 `cmd` 或 `powershell` 后回车，会打开已定位到该目录的窗口。
- 或按 `Win + R`，输入 `cmd` 或 `powershell` 回车，再用 `cd` 进入项目目录（见下）。

**`cd` 是什么？** 就是「进入某个文件夹」。例如你的项目在 `d:\homework\软测\autotest_design`：

```powershell
cd /d d:\homework\软测\autotest_design
```

之后提示符前面会显示你当前所在目录。下面的命令**都要在「项目根目录」下执行**（即能看到 `scripts`、`data`、`contracts` 文件夹的那一层）。

---

## 3. 这个工具在做什么？（用生活里的比喻）

可以把 AutoTestDesign 想成一条**流水线**：

1. 你准备好「原始需求」描述（可以放在 JSON、CSV 或纯文本里）。
2. **S1** 程序 `ingest.py` 负责「把各种来源的东西读进来、整理成统一格式」，写出 **`01_ingested.json`**。
3. **S2** 程序 `structure.py` 在每条需求上**做简单解析**（例如从中文里抓「长度 3 到 20」「如果…则…」），写出 **`02_structured.json`**。
4. **S3** 程序 `risk_prioritize.py` 为每条需求计算 **`risk_score`**、**`test_priority`**（高/中/低），写出 **`03_with_risk.json`**（对应课程 FR 2.0）。
5. **S4** 程序 `coverage_items.py` 生成顶层 **`coverage_items[]`**（每条含 `coverage_id`、`description`、`linked_req_ids`），写出 **`04_coverage_items.json`**，供后续策略与用例设计接力。
6. **S5** 程序 `strategies_and_prompts.py` 为每个覆盖项分配 ISO 29119-4 黑盒技术（EP / BVA / DT），并生成提示要点，写出 **`05_strategies.json`**（对应课程 FR 3.0 前半）。
7. **S6** 程序 `blackbox_generate.py` 根据每条策略的技术类型自动生成具体测试用例（含步骤、测试数据、预期结果及全链路可追溯链接），写出 **`06_test_cases_draft.json`**（对应课程 FR 3.0 后半）。
8. **S7** 程序 `traceability_and_analysis.py` 构建用例↔覆盖项↔策略↔需求映射，并生成简要结果分析，写出 **`07_traceability.json`**（对应 FR 6.0 前半）。
9. **S8** 程序 `interactive_review.py` 提供 CLI 菜单供设计者修订用例/覆盖项，写出 **`08_reviewed.json`**（满足「设计者参与」要求）。
10. **S9** 程序 `export_artifacts.py` 导出最终 JSON（cases + suites + risk）及可选 CSV，写出 **`09_export_cases.json`**（对应 FR 6.0）。
11. **`launcher.py`** 一键按序调用 S1～S9，支持 `--start-from` 从中间步骤调试。

这些文件都是 **JSON 格式**（一种用花括号、方括号组织的文本，程序爱用，人类也能打开看）。
**你们组约好了每一步读什么、写什么**，写在 `contracts/SCHEMA.md` 里，这叫**契约**——后面 P2、P3、P4 会接着往更后面的文件里写，但**不能乱删**前面已经定好的字段名，否则大家程序对不上。

---

## 4. 第一次跑通（复制粘贴版）

**前提**：已经用上一节的方式进入项目根目录 `autotest_design`，且 `python --version` 正常。

### 4.1（可选）安装依赖

根目录的 `requirements.txt` 含 **pytest、requests**（`tests_target`）、**Flask + waitress**（`web_app`）、以及可选 **openai、python-dotenv**（`--use-ai`）。**仅跑 S1～S6 脚本**可不安装第三方库；要跑 Web 或 pytest 请执行：

```powershell
pip install -r requirements.txt
```

若提示权限或环境混乱，可让组长统一用 `venv` 虚拟环境（略；需要时可查学校实验文档）。

### 4.2 跑 S1：从 Mock 原始需求生成 `01_ingested.json`

**测目标应用**时，S1 默认读 **`target-login-app/requirements/00_input_raw.json`**（与 `services.py` 一致的真实需求，共 8 条）：

```powershell
python scripts/ingest.py --in target-login-app/requirements/00_input_raw.json --out data/work/01_ingested.json
```

或一键：`python launcher.py --export-csv`（无需再指 mock）。

`data/mock/00_input_raw.json` 仅为 **P1 离线样例**（3 条旧需求）；若误用请加 `--use-mock` 或勿勾选 Web 上的 mock 选项。

**各参数意思：**

- `--in`：输入文件路径。这里用仓库里自带的 S0 样例。
- `--out`：输出写到哪里。`data/work/` 是本地运行结果目录，**第一次若不存在，程序会自动创建**（若你本机禁止写盘会报错）。

成功时，终端会有一行类似「已写入 … 条需求」；若失败，会显示中文错误，且**退出码为 1**（表示没成功）。

### 4.3 跑 S2：从 `01` 生成 `02_structured.json`

```powershell
python scripts/structure.py --in data/work/01_ingested.json --out data/work/02_structured.json
```

成功后，用记事本或 VS Code 打开 `data/work/02_structured.json`，你能看到每条需求下面多了 `input_fields`、`data_ranges` 等字段。

### 4.4 检查 JSON 是否「格式正确」

（可选）用 Python 自带的工具美化打印，若报错说明文件坏了：

```powershell
python -m json.tool data/work/02_structured.json
```

能刷出一大段缩进好的内容，一般就没问题。

### 4.5 跑 S3：从 `02` 生成 `03_with_risk.json`（P2 / FR 2.0）

**输入**：`02_structured.json`（可用上一步 `data/work/02_structured.json`，或仓库自带的 `data/mock/02_structured.json`）。

```powershell
python scripts/risk_prioritize.py --in data/work/02_structured.json --out data/work/03_with_risk.json
```

成功后终端会提示「已写入 … 条需求已标注风险与优先级」。打开输出文件可看到每条需求多了 `risk_score`、`test_priority`、`risk_rationale`。

**只想验收 P2、跳过 S1/S2 时**，可直接用 Mock：

```powershell
python scripts/risk_prioritize.py --in data/mock/02_structured.json --out data/work/03_with_risk.json
```

### 4.6 跑 S4：从 `03` 生成 `04_coverage_items.json`（P2）

**输入**：`03_with_risk.json`。

```powershell
python scripts/coverage_items.py --in data/work/03_with_risk.json --out data/work/04_coverage_items.json
```

输出里除 **`requirements`**（与 03 一致，便于单文件追溯）外，还有顶层 **`coverage_items`** 数组，供 P3 编写策略与黑盒生成脚本消费。

### 4.7 一键跑完全流程（推荐）

在项目根目录执行：

```powershell
python launcher.py --export-csv
# 已在根目录配置 .env 中的 OPENAI_API_KEY 时，可对 S2/S3 启用 LLM 融合：
python launcher.py --export-csv --use-ai
```

成功后在 `data/work/` 得到 `09_export_cases.json` 及 CSV。演示「设计者交互修订」时：

```powershell
python launcher.py --start-from traceability_and_analysis --interactive-review
```

从中间步骤调试示例：

```powershell
python launcher.py --start-from risk_prioritize
```

### 4.8 分步跑 S1～S6（可选）

按顺序执行 **4.2 → 4.3 → 4.5 → 4.6 → 4.9 → 4.10**，或使用下面等价的一条龙（仍在项目根目录）：

```powershell
python scripts/ingest.py --in target-login-app/requirements/00_input_raw.json --out data/work/01_ingested.json
python scripts/structure.py --in data/work/01_ingested.json --out data/work/02_structured.json
python scripts/risk_prioritize.py --in data/work/02_structured.json --out data/work/03_with_risk.json
python scripts/coverage_items.py --in data/work/03_with_risk.json --out data/work/04_coverage_items.json
python scripts/strategies_and_prompts.py --in data/work/04_coverage_items.json --out data/work/05_strategies.json
python scripts/blackbox_generate.py --in data/work/05_strategies.json --out data/work/06_test_cases_draft.json
```

若提示找不到目录，可先手动创建：`mkdir data\work`（CMD）或 `mkdir data/work`（PowerShell）。

### 4.9 跑 S5：从 `04` 生成 `05_strategies.json`（P3 / FR 3.0 前半）

**输入**：`04_coverage_items.json`。

```powershell
python scripts/strategies_and_prompts.py --in data/work/04_coverage_items.json --out data/work/05_strategies.json
```

成功后终端提示「已写入 … 条策略；技术分布：EP=…, BVA=…, DT=…」。打开输出文件可看到顶层 `strategies` 数组，每条含 `technique`（EP / BVA / DT）、`prompt_notes` 与可追溯链接。

**只想验收 P3、跳过 S1～S4 时**，可直接用 Mock：

```powershell
python scripts/strategies_and_prompts.py --in data/mock/04_coverage_items.json --out data/work/05_strategies.json
```

### 4.10 跑 S6：从 `05` 生成 `06_test_cases_draft.json`（P3 / FR 3.0 后半）

**输入**：`05_strategies.json`。

```powershell
python scripts/blackbox_generate.py --in data/work/05_strategies.json --out data/work/06_test_cases_draft.json
```

输出包含 **`test_cases`** 数组，每条用例含 `case_id`、`title`、`technique`、`steps`、`test_data`、`expected_result` 及全链路可追溯 `links`（req / coverage / strategy）。

**CMD 与 PowerShell**：下文命令以 **PowerShell** 为主（路径用 `/`）。若在 **命令提示符（cmd.exe）** 中运行，请把路径中的 `/` 写成 `\`（如 `data\work\01_ingested.json`），多条命令可**逐行分别执行**，或在同一行用 **`&&`** 连接（**不要用** PowerShell 专属的 `New-Item`、`$LASTEXITCODE`）。

### 4.11 跑 S7～S9（P4）

**S7 可追溯与结果分析：**

```powershell
python scripts/traceability_and_analysis.py --in data/work/06_test_cases_draft.json --out data/work/07_traceability.json
```

**S8 交互式审查**（演示时进入菜单修改用例；自动化全流程用 `--pass-through`）：

```powershell
python scripts/interactive_review.py --in data/work/07_traceability.json --out data/work/08_reviewed.json
```

**S9 导出：**

```powershell
python scripts/export_artifacts.py --in data/work/08_reviewed.json --out data/work/09_export_cases.json --csv-dir data/work
```

**不接上游时**可直接用 Mock：`data/mock/06_test_cases_draft.json` 作为 S7 输入。

### 4.11b AutoTestDesign Web 前端（需求导入 + 流水线 + 审查 + 产物）

安装依赖并启动（默认 **8765**，使用 **waitress**，无 Flask 开发服务器 WARNING）：

```powershell
pip install -r requirements.txt
python web_app/server.py
```

浏览器打开 **http://127.0.0.1:8765/** 。五个页签：

| 页签 | 作用 |
|------|------|
| **需求导入** | 单独跑 **S1**（FR 1.0）：目标应用 JSON/CSV、mock、粘贴文本、上传文件；预览 `01_ingested` 摘要；可一键跳到「从 S2 跑流水线」 |
| **流水线** | 异步跑 `launcher.py`；可选起点（建议 S1 已在「需求导入」做完后选 **structure**）；勾选 CSV / mock / 上传作 S1 / **S2·S3 LLM** |
| **产物浏览** | 查看、下载 `data/work` 下 JSON、CSV |
| **审查（S8）** | 加载 07/08，改用例、覆盖项、策略，保存 `08_reviewed.json` |
| **说明** | 简要步骤 |

**推荐 Web 流程（复制照做）**：

1. 「需求导入」→ 选「目标应用需求（JSON）」→ **执行 S1** → 看摘要条数。  
2. **S1 完成后从 S2 跑流水线**（自动切到「流水线」且起点为 `structure`）。  
3. **启动流水线** → 等日志完成。  
4. 「产物浏览」看 `09_export_cases.json`；若要改字 →「审查」保存 08 →「流水线」**仅运行 S9 导出**。  

Web **不支持**交互式 CLI 版 S8（请用 `python launcher.py --interactive-review`）。

```powershell
python web_app/server.py --port 9000
python web_app/server.py --dev
```

`--dev` 使用 Flask 内置服务器（会出现 *development server* 提示，仅本地调试）。

**命令行等价**：`python launcher.py --export-csv`（全流程）；分步与 Mock 见 [`Document/AutoTestDesign_运行与改动说明.md`](Document/AutoTestDesign_运行与改动说明.md) **§4 流程 A～F**。

### 4.12 目标应用自动化测试（tests_target）

先安装依赖：`pip install -r requirements.txt`。启动目标应用后执行：

```powershell
cd target-login-app
python app.py
```

另开终端，在项目根目录：

```powershell
python -m pytest tests_target/ -v
```

测试会读取 `data/work/09_export_cases.json`（或 `data/mock/09_export_cases.json`），对登录 API 做至少一条自动化验收。

---

## 5. 目录与文件是干什么的

```
autotest_design/                 ← 项目根（你运行命令时要站在这里）
├── README.md                    ← 本说明（你正在读）
├── launcher.py                  ← 一键串联 S1～S9
├── requirements.txt             ← Python 依赖（pytest、requests 等）
├── contracts/
│   └── SCHEMA.md                ← **全员必读**：每一步 JSON 里该有哪些字段
├── scripts/
│   ├── ingest.py                ← S1：多源需求 → 01_ingested.json
│   ├── structure.py             ← S2：01 → 02_structured.json
│   ├── risk_prioritize.py       ← S3：02 → 03_with_risk.json（风险与优先级）
│   ├── coverage_items.py        ← S4：03 → 04_coverage_items.json（覆盖项）
│   ├── strategies_and_prompts.py ← S5：04 → 05_strategies.json（策略分配）
│   ├── blackbox_generate.py     ← S6：05 → 06_test_cases_draft.json（黑盒用例）
│   ├── traceability_and_analysis.py ← S7：06 → 07_traceability.json
│   ├── interactive_review.py    ← S8：07 → 08_reviewed.json（交互审查）
│   └── export_artifacts.py      ← S9：08 → 09_export_cases.json（导出）
├── web_app/                     ← Web：需求导入(S1) + 流水线 + 审查 + 产物
│   ├── server.py
│   └── static/（index.html、app.js、style.css）
├── .env.example                 ← LLM 配置模板（复制为 .env，勿提交 .env）
├── tests_target/                ← 消费 09 对 target-login-app 的自动化测试
│   ├── conftest.py
│   └── test_login_from_export.py
├── Document/                    ← 分工说明、风险分析报告、测试计划初稿等（提交前多导出 PDF）
├── data/
│   ├── mock/                    ← **样例数据**（可提交到 Git，给全组对齐用）
│   │   ├── 00_input_raw.json … 06_test_cases_draft.json
│   │   ├── 07_traceability.json
│   │   ├── 08_reviewed.json
│   │   └── 09_export_cases.json
│   └── work/                    ← 你本机跑出来的结果（通常不提交，见 .gitignore）
└── target-login-app/            ← **目标应用**（被测的登录网站，不是工具核心）
    ├── README.md
    └── requirements/
        ├── 00_input_raw.json    ← launcher / Web 默认 S1 输入（8 条 FR-TGT-*）
        └── requirements.csv     ← 同上内容的 CSV 演示
```

- **`data/mock/`**：像「标准答卷例题」，格式固定，给别人不接上游也能开发。
- **`data/work/`**：像「你今晚做作业的草稿纸」，路径可能被 `.gitignore` 忽略，换电脑可能没有，需要自己再跑一遍命令生成。

---

## 6. 脚本详解（给要写代码或联调的同学）

### 6.1 `ingest.py`（对应课程 FR 1.0：多源导入）

**输入可以是：**

| 情况             | 怎么做                                                                                                                                                                                                                            |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 本仓库的 S0 JSON | `--in` 指向 `00_input_raw.json` 即可；`--format` 可省略，扩展名 `.json` 会自动当 JSON。                                                                                                                                           |
| CSV 表格         | 文件需 **UTF-8** 编码。表头里要有 **ID 一列**、**描述一列**（列名支持如 `req_id`、`ID`、`description`、`Text` 等常见写法，程序里写了模糊匹配）。示例：`data/mock/sample_requirements.csv`。若识别不对，可加 `--format csv` 强制。 |
| 纯文本 `.txt`    | 默认按「空行」分成多条需求；若没有空行，则**一行一条**。每条会自动编号 `REQ-0001` 这种。                                                                                                                                          |
| 标准输入         | `--in -` 表示从键盘管道读**一整段**当一条需求（适合演示）。                                                                                                                                                                       |

**输出：** 始终是统一的 **`01_ingested.json`** 结构，字段含义见 `contracts/SCHEMA.md` 的 **S1**。

**常见错误：**

- 忘记写 `--in` 或 `--out` → 会打印帮助并退出码 1。
- CSV 不是 UTF-8（例如 Excel 直接另存为 ANSI）→ 中文乱码或解析失败；请用 Excel「另存为 CSV UTF-8」或 VS Code 换编码为 UTF-8。

### 6.2 `structure.py`（对应课程 FR 1.1：需求结构化）

**输入：** 必须是 **`01_ingested.json`**（或格式与它一致的文件）。

**输出：** **`02_structured.json`**，在每条需求上增加：

- `input_fields`：识别到的输入名（如用户名、密码）
- `data_ranges`：数值/长度范围（程序用正则抓常见中文句式）
- `conditions` / `expected_actions`：简单「如果…则…」或关键词（规则很浅，**不可能覆盖所有自然语言**；作业上允许「规则 + 人工后续修改」）

**注意：** 这里没有装 spaCy 等大模型库，**目的是轻量、可离线、组里人人能跑**。后续若要接 AI，可在保留 JSON 契约的前提下换实现。

### 6.3 `risk_prioritize.py`（对应课程 FR 2.0：风险与优先级）

**输入：** **`02_structured.json`**（字段含义见 `contracts/SCHEMA.md` 的 **S2**）。

**输出：** **`03_with_risk.json`**（契约见 **S3**）。在每条需求上**追加**：

- `risk_score`：0～100 的数值；
- `test_priority`：`High` / `Medium` / `Low`；
- `risk_rationale`：字符串数组，简要说明评分依据（便于风险报告与复查）。

实现为**可解释的启发式规则**（关键词、条件/动作数量、数据范围、`extra.priority` 等），**不调用外部大模型 API**，便于离线验收。若 CSV 等来源将某条标为 **High**，脚本会将分值抬到至少满足 **High** 档，避免与业务标注冲突。

### 6.4 `coverage_items.py`（覆盖项识别，Mainly 流程落盘）

**输入：** **`03_with_risk.json`**。

**输出：** **`04_coverage_items.json`**（契约见 **S4**）。保留 **`requirements`**，并新增 **`coverage_items`**：

- 依据 `data_ranges`、`conditions`、`expected_actions` 生成可解释的覆盖意图；
- 结构化信息较少时增加兜底覆盖项；`test_priority == High` 时增补高风险/负面场景类条目；
- 每项含 `coverage_id`、`description`、`linked_req_ids`（至少一条需求 ID），可选 `focus`、`notes`。

**下游：** P3 从 **`04_coverage_items.json`** 继续生成 **`05_strategies.json`** 与 **`06_test_cases_draft.json`**。

### 6.5 `strategies_and_prompts.py`（对应课程 FR 3.0 前半：策略分配）

**输入：** **`04_coverage_items.json`**（字段含义见 `contracts/SCHEMA.md` 的 **S4**）。

**输出：** **`05_strategies.json`**（契约见 **S5**）。为每个覆盖项依据 `focus` 类型分配 ISO 29119-4 黑盒技术，映射规则：

| `focus`              | 分配技术 |
| -------------------- | -------- |
| `data_range`         | EP, BVA  |
| `condition_branch`   | DT       |
| `expected_action`    | EP       |
| `general_functional` | EP       |
| `risk_negative`      | BVA, DT  |

每条策略含 `strategy_id`、`technique`、`linked_coverage_ids`、`linked_req_ids`、`risk_priority`（取关联需求中最高优先级）、`prompt_notes`（技术特定的生成提示要点）。

### 6.6 `blackbox_generate.py`（对应课程 FR 3.0 后半：黑盒用例生成）

**输入：** **`05_strategies.json`**。

**输出：** **`06_test_cases_draft.json`**（契约见 **S6**）。根据策略的 `technique` 调用对应生成器：

| 技术    | 生成逻辑                                                                        |
| ------- | ------------------------------------------------------------------------------- |
| **EP**  | 有效类（区间中值）+ 无效类（上溢/下溢/空输入）；动作类覆盖项生成触发/不触发用例 |
| **BVA** | 对每个数据范围生成 min±1、max±1 共 6 个边界点用例                               |
| **DT**  | 基于条件与动作的布尔组合生成 2^n 条决策规则                                     |

每条用例含 `case_id`、`title`、`technique`、`steps`、`test_data`、`expected_result`，以及全链路可追溯 `links`（req / coverage / strategy）。

**下游：** P4 从 **`06_test_cases_draft.json`** 继续做可追溯分析、交互审查与导出。

### 6.7 `traceability_and_analysis.py`（S7：可追溯与结果分析）

**输入：** **`06_test_cases_draft.json`**。

**输出：** **`07_traceability.json`**（契约见 **S7**）。构建 `traceability.mappings`（用例↔策略↔覆盖项↔需求）、`analysis`（技术分布、缺口、建议）及 `improvement_records`。

### 6.8 `interactive_review.py`（S8：交互式审查）

**输入：** **`07_traceability.json`**。

**输出：** **`08_reviewed.json`**。CLI 菜单支持修订测试用例（title、steps、expected_result）与覆盖项描述；保存前显示 diff。`launcher` 默认 `--pass-through` 透传；演示时用 `python launcher.py --interactive-review` 或单独运行本脚本。

### 6.9 `export_artifacts.py`（S9：导出，FR 6.0）

**输入：** **`08_reviewed.json`**。

**输出：** **`09_export_cases.json`**，含 `suites`、`cases`、`risk`；可选 `--csv-dir` 写出 `09_export_cases.csv` 与 `09_export_risk.csv`。

### 6.10 `launcher.py`（全流程启动器）

依次 subprocess 调用 S1～S9；`--start-from <步骤名>` 从中部调试；`--export-csv` 同时导出 CSV；任一步失败 exit(1)。

**下游：** `tests_target/` 读取 **`09_export_cases.json`** 对目标应用执行自动化测试。

---

## 7. 给组里其他同学看的「接力说明」（极简）

- **P2（已实现）**：脚本 **`risk_prioritize.py`**、**`coverage_items.py`**；契约 **`SCHEMA.md`** 已包含 **S3～S4**；**`data/mock/`** 内提供 **`03_with_risk.json`、`04_coverage_items.json`** 供不接上游时开发。课程文档见 **`Document/RISK_ANALYSIS_REPORT .md`**（目标应用风险分析）与 **`Document/测试计划_范围测试项风险套件_初稿.md`**；分工全文见 **`Document/详细分工方案.txt`**。
- **P3（已实现）**：脚本 **`strategies_and_prompts.py`**、**`blackbox_generate.py`**；契约 **`SCHEMA.md`** 已包含 **S5～S6**；**`data/mock/`** 内提供 **`05_strategies.json`、`06_test_cases_draft.json`** 供不接上游时开发。课程文档见 **`Document/详细测试设计与执行文档.md`**（黑盒技术、用例设计与覆盖说明）。
- **P4（已实现）**：脚本 **`traceability_and_analysis.py`**、**`interactive_review.py`**、**`export_artifacts.py`**、**`launcher.py`**；**`web_app/`** 整条流水线 Web 前端；**`tests_target/`** 自动化测试；契约 **S7～S9**；**`data/mock/`** 提供 **`07`～`09`** 样例。

更正式的分工与时间轴见仓库内 **`Document/详细分工方案.txt`**。

---

## 8. 常见问题（FAQ）

**问：为什么我双击 `ingest.py` 一闪而过？**
答：脚本需要在终端里带参数运行；双击往往没有参数，程序就只能退出。请按第 4 节在命令行里执行。

**问：`python` 和 `py` 用哪个？**
答：都可以，只要有一个能对应到你安装的 Python 3.10+。

**问：提示找不到 `data\work`？**
答：一般会自动创建；若在无写权限目录运行会失败，请把项目放在你有权限的磁盘目录再试。

**问：`02` 里解析结果太笨，正常吗？**
答：正常。课程强调的是**可追溯、可修改的流程**；后面还有交互式审查、人工改 JSON。P1 先把「文件格式」和「能跑通」立住。

**问：我只想跑那个登录网站给客户演示？**
答：请看 [`target-login-app/README.md`](target-login-app/README.md)，与本工具流水线是两条线，别混在一份作业描述里写错对象。

**问：怎么自检 P2 是否跑通？**
答：用 **`data/mock/02_structured.json`** 依次执行 **4.5、4.6**，再用 `python -m json.tool data/work/03_with_risk.json`（及 `04`）检查格式；确认每条需求都有 `risk_score`/`test_priority`，且 `04` 中 **`coverage_items`** 每项都有 **`linked_req_ids`**。故意把 `--in` 指向不存在的文件时，脚本应打印错误且 **退出码为 1**。

**问：怎么自检 P3 是否跑通？**
答：用 **`data/mock/04_coverage_items.json`** 依次执行 **4.8、4.9**，再用 `python -m json.tool data/work/05_strategies.json`（及 `06`）检查格式；确认 `05` 中每条策略都有 `technique`（EP/BVA/DT）和 `linked_coverage_ids`，`06` 中每条用例都有 `case_id`、`steps`、`expected_result` 及完整 `links`（req + coverage + strategy）。

**问：怎么自检 P4 是否跑通？**
答：执行 `python launcher.py --export-csv`，检查 `data/work/09_export_cases.json` 含 `cases`、`suites`、`risk`；或启动 `python web_app/server.py` 在「流水线」跑通并在「产物」看到 09。`python -m pytest tests_target/ -v` 至少 2 项通过（目标应用未启动时 API 测试会 skip）。
---

## 9. 还想深入了解？

- **字段级约定**：打开 [`contracts/SCHEMA.md`](contracts/SCHEMA.md)。
- **作业截止与评分**：见课程下发的 PDF / `Document` 里整理的任务说明。
- **命令记不住**：随时执行
  `python scripts/ingest.py -h`
  `python scripts/structure.py -h`
  `python scripts/risk_prioritize.py -h`
  `python scripts/coverage_items.py -h`
  `python scripts/strategies_and_prompts.py -h`
  `python scripts/blackbox_generate.py -h`
  `python scripts/traceability_and_analysis.py -h`
  `python scripts/interactive_review.py -h`
  `python scripts/export_artifacts.py -h`
  `python launcher.py -h`
  会打印官方参数说明（与本文一致）。

如有新人加入团队，把本文 **第 1～4 节** 发给他即可最快上手。

---

## 10. 课程交付物与 Document 文档

作业（*Assignment 2*）要求：**风险分析报告**、**测试计划**、**详细测试设计与执行文档** 等描述的是 **目标应用**（`target-login-app`），**不是** AutoTestDesign 工具本身。以下文件在仓库 **`Document/`** 中，便于组内协作；**提交给助教时通常需 PDF**（请自行从 Word / WPS / Markdown 导出并加封面：组号、姓名、学号）。

| 文件                                                                                           | 用途                                                                                                                        |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [`Document/AutoTestDesign_运行与改动说明.md`](Document/AutoTestDesign_运行与改动说明.md) | **工具链**：已实现功能总览、**全部使用流程（A～F）**、Web 页签与 API、launcher 参数、演示顺序与排错 |
| [`Document/详细分工方案.txt`](Document/详细分工方案.txt)                                       | 四人接力分工与验收要点                                                                                                      |
| [`Document/RISK_ANALYSIS_REPORT .md`](Document/RISK_ANALYSIS_REPORT%20.md)                     | **目标应用**风险分析报告（与 `target-login-app` 及接口行为对齐；注意文件名中含空格）                                        |
| [`Document/DETAILED_TEST_DESIGN.md`](Document/DETAILED_TEST_DESIGN.md)                         | **目标应用**详细测试设计与执行文档：黑盒技术（EP / BVA / DT）、用例设计与覆盖说明                                           |
| [`Document/测试计划_范围测试项风险套件_初稿.md`](Document/测试计划_范围测试项风险套件_初稿.md) | 测试计划中 **范围、测试项、风险相关套件设计** 初稿（完整测试计划还需进度表、组织图、框架选型、成本估算等，见作业 PDF §1.2） |
| 其他 `Document/*.txt`                                                                          | 课程/组内整理的备忘与需求摘录，以文件内说明为准                                                                             |

**与工具链的关系**：可用 `scripts/` 产出的 `03_with_risk.json`、`04_coverage_items.json` 支撑 FR 2.0 与测试优先级描述；`05_strategies.json`、`06_test_cases_draft.json` 支撑 FR 3.0 黑盒技术分配与用例设计；详细用例与执行文档由全组按作业「Mainly」段落继续补充。
