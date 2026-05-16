#!/usr/bin/env python3
"""
AutoTestDesign — Web 前端服务
提供：需求导入（FR 1.0）、流水线执行、产物查看/下载、S8 审查保存、单独导出 S9。
"""

from __future__ import annotations

import json
import locale
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
if not (ROOT / "scripts" / "ingest.py").is_file():
    ROOT = Path.cwd()
WORK = ROOT / "data" / "work"
MOCK = ROOT / "data" / "mock"
TARGET_REQ = ROOT / "target-login-app" / "requirements" / "00_input_raw.json"
TARGET_REQ_CSV = ROOT / "target-login-app" / "requirements" / "requirements.csv"
INGEST_OUT = WORK / "01_ingested.json"
STATIC = APP_DIR / "static"
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

_SAFE_FILE = re.compile(r"^[a-zA-Z0-9_.-]{1,120}$")
VALID_PIPELINE_STARTS = frozenset({
    "ingest", "structure", "risk_prioritize", "coverage_items",
    "strategies_and_prompts", "blackbox_generate", "traceability_and_analysis",
    "interactive_review", "export_artifacts",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _under_data(p: Path) -> bool:
    try:
        p = p.resolve()
    except OSError:
        return False
    for base in (WORK.resolve(), MOCK.resolve()):
        try:
            p.relative_to(base)
            return True
        except ValueError:
            continue
    return False


def _safe_artifact_name(name: str) -> bool:
    if not name or not _SAFE_FILE.match(name):
        return False
    if name.startswith("."):
        return False
    low = name.lower()
    if not (low.endswith(".json") or low.endswith(".csv") or low.endswith(".txt")):
        return False
    return True


def _subprocess_env() -> dict[str, str]:
    """子进程统一 UTF-8 输出，避免 Web 捕获日志在 Windows 下乱码（GBK/UTF-8 不一致）。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _decode_subprocess_bytes(data: bytes | None) -> str:
    if not data:
        return ""
    try:
        utf8_strict = data.decode("utf-8")
        if "\ufffd" not in utf8_strict:
            return utf8_strict
    except UnicodeDecodeError:
        pass
    utf8_replace = data.decode("utf-8", errors="replace")
    best, best_bad = utf8_replace, utf8_replace.count("\ufffd")
    for enc in ("gbk", "cp936", locale.getpreferredencoding(False) or ""):
        if not enc or enc.lower() in ("utf-8", "utf8"):
            continue
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        bad = text.count("\ufffd")
        if bad < best_bad:
            best, best_bad = text, bad
    return best


def _run_subprocess_logged(
    cmd: list[str],
    *,
    timeout: float | None = None,
) -> tuple[int, str]:
    r = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        env=_subprocess_env(),
        timeout=timeout,
    )
    log = _decode_subprocess_bytes(r.stdout) + _decode_subprocess_bytes(r.stderr)
    return r.returncode, log


def _find_upload_input() -> Path | None:
    for stem in ("web_upload_input", "ingest_upload"):
        for suf in (".json", ".csv", ".txt"):
            p = WORK / f"{stem}{suf}"
            if p.is_file():
                return p
    return None


def _run_ingest(in_path: Path, *, fmt: str = "auto") -> tuple[int, str]:
    """调用 ingest.py，写出 01_ingested.json。返回 (exit_code, log_text)。"""
    script = ROOT / "scripts" / "ingest.py"
    if not script.is_file():
        return 1, f"错误：找不到 {script}"
    WORK.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(script),
        "--in",
        str(in_path.resolve()),
        "--out",
        str(INGEST_OUT.resolve()),
        "--format",
        fmt,
    ]
    return _run_subprocess_logged(cmd)


def _ingest_summary() -> dict[str, Any] | None:
    if not INGEST_OUT.is_file():
        return None
    try:
        with INGEST_OUT.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    reqs = data.get("requirements") or []
    preview = []
    for r in reqs[:12]:
        if isinstance(r, dict):
            preview.append({
                "req_id": r.get("req_id"),
                "raw_text": (r.get("raw_text") or "")[:120],
                "source": r.get("source"),
            })
    return {
        "path": str(INGEST_OUT),
        "count": len(reqs) if isinstance(reqs, list) else 0,
        "ingested_at": data.get("ingested_at"),
        "source_files": data.get("source_files"),
        "preview": preview,
    }


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/assets")

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    def _run_launcher(
        job_id: str,
        start_from: str,
        export_csv: bool,
        interactive_review: bool,
        input_abs: str | None,
        use_ai: bool,
        use_mock: bool,
    ) -> None:
        cmd = [
            sys.executable,
            str(ROOT / "launcher.py"),
            "--start-from",
            start_from,
        ]
        if export_csv:
            cmd.append("--export-csv")
        if interactive_review:
            cmd.append("--interactive-review")
        if input_abs:
            cmd.extend(["--input", input_abs])
        if use_ai:
            cmd.append("--use-ai")
        if use_mock:
            cmd.append("--use-mock")
        with JOBS_LOCK:
            JOBS[job_id]["running"] = True
            JOBS[job_id]["log"] = ""
        try:
            code, log = _run_subprocess_logged(cmd, timeout=600)
            with JOBS_LOCK:
                JOBS[job_id]["log"] = log
                JOBS[job_id]["exit_code"] = code
                JOBS[job_id]["running"] = False
        except subprocess.TimeoutExpired:
            with JOBS_LOCK:
                JOBS[job_id]["log"] = "执行超时（>600s）"
                JOBS[job_id]["exit_code"] = -1
                JOBS[job_id]["running"] = False
        except Exception as ex:
            with JOBS_LOCK:
                JOBS[job_id]["log"] = str(ex)
                JOBS[job_id]["exit_code"] = 1
                JOBS[job_id]["running"] = False

    @app.post("/api/pipeline/run")
    def api_pipeline_run():
        body = request.get_json(silent=True) or {}
        start_from = str(body.get("start_from") or "ingest").strip()
        if start_from not in VALID_PIPELINE_STARTS:
            return jsonify({"ok": False, "error": f"无效 start_from：{start_from}"}), 400
        export_csv = bool(body.get("export_csv"))
        use_ai = bool(body.get("use_ai"))
        interactive_review = bool(body.get("interactive_review"))
        use_upload = bool(body.get("use_uploaded_input"))
        use_mock = bool(body.get("use_mock"))
        if interactive_review:
            return jsonify({
                "ok": False,
                "error": "Web 环境无法使用交互式 S8。请取消「交互式 S8」或改用命令行 launcher --interactive-review。",
            }), 400

        input_abs: str | None = None
        if use_upload:
            p = _find_upload_input()
            if p is None:
                return jsonify({"ok": False, "error": "请先上传需求文件（.json / .csv / .txt），或取消「使用上传文件」"}), 400
            input_abs = str(p.resolve())

        job_id = uuid.uuid4().hex[:12]
        with JOBS_LOCK:
            JOBS[job_id] = {"running": True, "log": "", "exit_code": None}
        t = threading.Thread(
            target=_run_launcher,
            args=(job_id, start_from, export_csv, interactive_review, input_abs, use_ai, use_mock),
            daemon=True,
        )
        t.start()
        return jsonify({"ok": True, "job_id": job_id})

    @app.get("/api/pipeline/job/<job_id>")
    def api_pipeline_job(job_id: str):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "未知任务"}), 404
        return jsonify({
            "ok": True,
            "running": job.get("running", False),
            "log": job.get("log", ""),
            "exit_code": job.get("exit_code"),
        })

    @app.post("/api/export/run")
    def api_export_run():
        """仅 S9：需已有 08_reviewed.json"""
        p08 = WORK / "08_reviewed.json"
        if not p08.is_file():
            return jsonify({"ok": False, "error": "缺少 data/work/08_reviewed.json，请先跑流水线或审查保存"}), 400
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "export_artifacts.py"),
            "--in",
            str(p08),
            "--out",
            str(WORK / "09_export_cases.json"),
            "--csv-dir",
            str(WORK),
        ]
        try:
            code, log = _run_subprocess_logged(cmd, timeout=120)
            return jsonify({
                "ok": code == 0,
                "exit_code": code,
                "log": log,
            })
        except Exception as ex:
            return jsonify({"ok": False, "error": str(ex)}), 500

    @app.get("/api/artifacts/list")
    def api_artifacts_list():
        WORK.mkdir(parents=True, exist_ok=True)
        names: list[str] = []
        for p in sorted(WORK.iterdir()):
            if p.is_file() and _safe_artifact_name(p.name):
                names.append(p.name)
        return jsonify({"ok": True, "files": names})

    @app.get("/api/artifact")
    def api_artifact():
        name = (request.args.get("name") or "").strip()
        if not _safe_artifact_name(name):
            return jsonify({"ok": False, "error": "非法文件名"}), 400
        path = (WORK / name).resolve()
        if not _under_data(path) or not path.is_file():
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        if name.lower().endswith(".json"):
            try:
                with path.open(encoding="utf-8") as f:
                    data = json.load(f)
                return jsonify({"ok": True, "name": name, "data": data})
            except (OSError, json.JSONDecodeError) as ex:
                return jsonify({"ok": False, "error": str(ex)}), 400
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as ex:
            return jsonify({"ok": False, "error": str(ex)}), 400
        return jsonify({"ok": True, "name": name, "text": text})

    @app.get("/api/download")
    def api_download():
        name = (request.args.get("name") or "").strip()
        if not _safe_artifact_name(name):
            return jsonify({"ok": False, "error": "非法文件名"}), 400
        path = (WORK / name).resolve()
        if not _under_data(path) or not path.is_file():
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        return send_from_directory(
            str(WORK),
            name,
            as_attachment=True,
            download_name=name,
        )

    @app.get("/api/ingest/options")
    def api_ingest_options():
        """列出 FR 1.0 可选来源（供「需求导入」页）。"""
        opts = []
        if TARGET_REQ.is_file():
            opts.append({
                "id": "target_json",
                "label": "目标应用需求（JSON）",
                "path": str(TARGET_REQ),
                "format": "json",
            })
        if TARGET_REQ_CSV.is_file():
            opts.append({
                "id": "target_csv",
                "label": "目标应用需求（CSV）",
                "path": str(TARGET_REQ_CSV),
                "format": "csv",
            })
        if (MOCK / "00_input_raw.json").is_file():
            opts.append({
                "id": "mock_json",
                "label": "开发样例 mock（JSON，仅联调）",
                "path": str(MOCK / "00_input_raw.json"),
                "format": "json",
            })
        up = _find_upload_input()
        if up:
            ext = up.suffix.lower().lstrip(".")
            opts.append({
                "id": "upload",
                "label": f"已上传文件（{up.name}）",
                "path": str(up),
                "format": ext if ext in ("json", "csv", "text") else "auto",
            })
        opts.append({"id": "paste", "label": "粘贴纯文本（多行或空行分隔）", "format": "text"})
        return jsonify({
            "ok": True,
            "output": str(INGEST_OUT),
            "options": opts,
            "has_01": INGEST_OUT.is_file(),
            "summary": _ingest_summary(),
        })

    @app.post("/api/ingest/run")
    def api_ingest_run():
        """执行 S1 ingest.py（JSON body：target | mock | paste | upload）。"""
        body = request.get_json(silent=True) or {}
        source = str(body.get("source") or "target").strip().lower()
        WORK.mkdir(parents=True, exist_ok=True)
        in_path: Path | None = None
        fmt = "auto"

        if source == "target":
            use_csv = bool(body.get("use_csv"))
            in_path = TARGET_REQ_CSV if use_csv and TARGET_REQ_CSV.is_file() else TARGET_REQ
            fmt = "csv" if use_csv else "json"
        elif source == "mock":
            in_path = MOCK / "00_input_raw.json"
            fmt = "json"
        elif source == "paste":
            text = str(body.get("text") or "")
            if not text.strip():
                return jsonify({"ok": False, "error": "粘贴内容为空"}), 400
            in_path = WORK / "ingest_paste.txt"
            in_path.write_text(text, encoding="utf-8")
            fmt = "text"
        elif source == "upload":
            in_path = _find_upload_input()
            if in_path is None:
                return jsonify({
                    "ok": False,
                    "error": "请先在「需求导入」上传文件，或改用其他来源",
                }), 400
            ext = in_path.suffix.lower()
            if ext == ".csv":
                fmt = "csv"
            elif ext == ".json":
                fmt = "json"
            else:
                fmt = "text"
        else:
            return jsonify({"ok": False, "error": f"未知 source：{source}"}), 400

        if in_path is None or not in_path.is_file():
            return jsonify({"ok": False, "error": f"找不到输入：{in_path}"}), 400

        code, log = _run_ingest(in_path, fmt=fmt)
        summary = _ingest_summary()
        return jsonify({
            "ok": code == 0,
            "exit_code": code,
            "log": log,
            "input_path": str(in_path),
            "output_path": str(INGEST_OUT),
            "summary": summary,
        })

    @app.post("/api/ingest/run-file")
    def api_ingest_run_file():
        """上传并立即执行 S1（multipart：file 字段）。"""
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "缺少 file"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"ok": False, "error": "空文件名"}), 400
        WORK.mkdir(parents=True, exist_ok=True)
        fn = Path(f.filename)
        ext = fn.suffix.lower()
        if ext not in (".json", ".csv", ".txt"):
            ext = ".txt"
        dest = WORK / f"ingest_upload{ext}"
        try:
            f.save(str(dest))
        except OSError as ex:
            return jsonify({"ok": False, "error": str(ex)}), 500
        fmt = "auto"
        if ext == ".csv":
            fmt = "csv"
        elif ext == ".json":
            fmt = "json"
        else:
            fmt = "text"
        code, log = _run_ingest(dest, fmt=fmt)
        summary = _ingest_summary()
        return jsonify({
            "ok": code == 0,
            "exit_code": code,
            "log": log,
            "input_path": str(dest),
            "output_path": str(INGEST_OUT),
            "summary": summary,
        })

    @app.post("/api/upload")
    def api_upload():
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "缺少 file 字段"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"ok": False, "error": "空文件名"}), 400
        WORK.mkdir(parents=True, exist_ok=True)
        fn = Path(f.filename)
        ext = fn.suffix.lower()
        if ext not in (".json", ".csv", ".txt"):
            ext = ".json"
        for old in WORK.glob("web_upload_input.*"):
            if old.is_file():
                try:
                    old.unlink()
                except OSError:
                    pass
        saved = f"web_upload_input{ext}"
        dest = WORK / saved
        try:
            f.save(str(dest))
        except OSError as ex:
            return jsonify({"ok": False, "error": str(ex)}), 500
        return jsonify({"ok": True, "path": str(dest), "saved_as": saved})

    @app.get("/api/review/load")
    def api_review_load():
        src = (request.args.get("source") or "07").strip().lower()
        mapping = {
            "07": WORK / "07_traceability.json",
            "08": WORK / "08_reviewed.json",
            "mock07": MOCK / "07_traceability.json",
            "mock08": MOCK / "08_reviewed.json",
        }
        path = mapping.get(src)
        if path is None:
            rel = (request.args.get("path") or "").strip().replace("\\", "/")
            if not rel or ".." in rel:
                return jsonify({"ok": False, "error": "无效 path"}), 400
            cand = (ROOT / "data" / rel).resolve()
            if not _under_data(cand):
                return jsonify({"ok": False, "error": "path 必须在 data/work 或 data/mock 下"}), 400
            path = cand
        if not path.is_file():
            return jsonify({"ok": False, "error": f"文件不存在：{path}"}), 404
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as ex:
            return jsonify({"ok": False, "error": str(ex)}), 400
        return jsonify({"ok": True, "path": str(path), "data": data})

    @app.post("/api/review/save")
    def api_review_save():
        body = request.get_json(silent=True) or {}
        doc = body.get("document")
        if not isinstance(doc, dict):
            return jsonify({"ok": False, "error": "缺少 document 对象"}), 400
        out_rel = (body.get("out_path") or "work/08_reviewed.json").strip().replace("\\", "/")
        if ".." in out_rel or not out_rel.startswith(("work/", "mock/")):
            return jsonify({"ok": False, "error": "out_path 仅允许 work/… 或 mock/…"}), 400
        out_path = (ROOT / "data" / out_rel).resolve()
        if not _under_data(out_path):
            return jsonify({"ok": False, "error": "非法输出路径"}), 400

        edits = int(body.get("designer_edit_count") or 0)
        notes = str(body.get("review_notes") or "").strip()

        out_doc = json.loads(json.dumps(doc, ensure_ascii=False))
        out_doc["pipeline_stage"] = "08_reviewed"
        out_doc["reviewed_at"] = _utc_now()
        out_doc["designer_edit_count"] = edits
        out_doc["review_notes"] = notes

        records = out_doc.setdefault("improvement_records", [])
        if edits > 0:
            n = len(records) + 1
            records.append({
                "record_id": f"IMP-W{n:03d}",
                "at": _utc_now(),
                "author": "designer_web",
                "entity_type": "bulk",
                "entity_id": "web_app",
                "change_summary": f"Web 审查保存（{edits} 处修订）",
                "rationale": notes or "通过 AutoTestDesign Web 保存",
            })

        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(out_doc, f, ensure_ascii=False, indent=2)
                f.write("\n")
        except OSError as ex:
            return jsonify({"ok": False, "error": str(ex)}), 500
        return jsonify({"ok": True, "path": str(out_path), "designer_edit_count": edits})

    return app


app = create_app()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="AutoTestDesign Web 前端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--dev",
        action="store_true",
        help="使用 Flask 内置开发服务器（会打印 production WARNING，仅调试）",
    )
    args = parser.parse_args()
    if not STATIC.is_dir():
        print("错误：缺少 static 目录", file=sys.stderr)
        return 1
    url = f"http://{args.host}:{args.port}/"
    print(f"AutoTestDesign Web：{url}")
    if args.dev:
        app.run(host=args.host, port=args.port, debug=False)
        return 0
    try:
        from waitress import serve
    except ImportError:
        print(
            "未安装 waitress，回退到 Flask 开发服务器。"
            "建议：pip install waitress",
            file=sys.stderr,
        )
        app.run(host=args.host, port=args.port, debug=False)
        return 0
    serve(app, host=args.host, port=args.port, threads=4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
