(function () {
  const STEPS = [
    { id: "ingest", label: "S1 ingest" },
    { id: "structure", label: "S2 structure" },
    { id: "risk_prioritize", label: "S3 risk_prioritize" },
    { id: "coverage_items", label: "S4 coverage_items" },
    { id: "strategies_and_prompts", label: "S5 strategies" },
    { id: "blackbox_generate", label: "S6 blackbox_generate" },
    { id: "traceability_and_analysis", label: "S7 traceability" },
    { id: "interactive_review", label: "S8 interactive_review" },
    { id: "export_artifacts", label: "S9 export" },
  ];

  const $ = (id) => document.getElementById(id);

  function toast(msg, ok) {
    const el = $("toast");
    el.textContent = msg;
    el.className = "show " + (ok ? "ok" : "err");
    clearTimeout(el._t);
    el._t = setTimeout(() => {
      el.className = "";
    }, 4500);
  }

  /* ----- tabs ----- */
  document.querySelectorAll("nav.tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll("nav.tabs button").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll("section.tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $("tab-" + tab).classList.add("active");
      if (tab === "ingest") refreshIngestSummary();
    });
  });

  function selectedIngestSource() {
    const r = document.querySelector('input[name="ingestSource"]:checked');
    return r ? r.value : "target";
  }

  function updateIngestPasteVisibility() {
    const show = selectedIngestSource() === "paste";
    $("ingestPasteRow").style.display = show ? "block" : "none";
  }

  document.querySelectorAll('input[name="ingestSource"]').forEach((el) => {
    el.addEventListener("change", updateIngestPasteVisibility);
  });
  updateIngestPasteVisibility();

  function renderIngestSummary(summary) {
    const box = $("ingestSummaryBox");
    if (!summary) {
      box.innerHTML = "尚无 <code>01_ingested.json</code>，请先执行 S1。";
      box.className = "summary-box hint";
      return;
    }
    let html =
      "<p><strong>" +
      summary.count +
      "</strong> 条需求 · " +
      (summary.ingested_at || "") +
      "</p>";
    if (summary.source_files && summary.source_files.length) {
      html += "<p class=\"hint\">来源：" + summary.source_files.join(", ") + "</p>";
    }
    if (summary.preview && summary.preview.length) {
      html += "<table><thead><tr><th>req_id</th><th>raw_text</th><th>source</th></tr></thead><tbody>";
      summary.preview.forEach((row) => {
        html +=
          "<tr><td>" +
          (row.req_id || "") +
          "</td><td>" +
          escapeHtml(row.raw_text || "") +
          "</td><td>" +
          (row.source || "") +
          "</td></tr>";
      });
      html += "</tbody></table>";
      if (summary.count > summary.preview.length) {
        html += "<p class=\"hint\">仅显示前 " + summary.preview.length + " 条</p>";
      }
    }
    box.innerHTML = html;
    box.className = "summary-box";
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function refreshIngestSummary() {
    const r = await fetch("/api/ingest/options");
    const j = await r.json();
    if (j.ok && j.summary) renderIngestSummary(j.summary);
    else if (j.ok && !j.has_01) renderIngestSummary(null);
  }

  $("btnRefreshIngestSummary").onclick = refreshIngestSummary;

  $("btnRunIngest").onclick = async () => {
    const src = selectedIngestSource();
    let body = {};
    if (src === "target" || src === "target_csv") {
      body = { source: "target", use_csv: src === "target_csv" };
    } else if (src === "mock") {
      body = { source: "mock" };
    } else if (src === "paste") {
      body = { source: "paste", text: $("ingestPaste").value };
    } else if (src === "upload") {
      body = { source: "upload" };
    }
    $("ingest-log").textContent = "执行中…";
    const r = await fetch("/api/ingest/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    $("ingest-log").textContent = j.log || j.error || "";
    if (j.summary) renderIngestSummary(j.summary);
    toast(j.ok ? "S1 完成，共 " + (j.summary && j.summary.count) + " 条" : j.error || "S1 失败", j.ok);
  };

  $("btnIngestUploadRun").onclick = async () => {
    const f = $("ingestFile").files[0];
    if (!f) {
      toast("请选择文件", false);
      return;
    }
    const fd = new FormData();
    fd.append("file", f);
    $("ingest-log").textContent = "上传并执行 S1…";
    const r = await fetch("/api/ingest/run-file", { method: "POST", body: fd });
    const j = await r.json();
    $("ingest-log").textContent = j.log || j.error || "";
    if (j.summary) renderIngestSummary(j.summary);
    toast(j.ok ? "S1 完成" : j.error || "失败", j.ok);
  };

  $("btnGoPipelineS2").onclick = () => {
    $("startFrom").value = "structure";
    document.querySelector('nav.tabs button[data-tab="pipeline"]').click();
    toast("已切换到流水线，起点为 S2 structure", true);
  };

  refreshIngestSummary();

  const sel = $("startFrom");
  STEPS.forEach((s) => {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = s.label + " → … → S9";
    sel.appendChild(o);
  });

  /* ----- pipeline ----- */
  let pollTimer = null;

  $("btnRunPipeline").onclick = async () => {
    $("pipeline-log").textContent = "启动中…";
    const r = await fetch("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
        start_from: $("startFrom").value,
        export_csv: $("chkExportCsv").checked,
        use_uploaded_input: $("chkUseUpload").checked,
        use_mock: $("chkUseMock").checked,
        use_ai: $("chkUseAi").checked,
        interactive_review: false,
      }),
    });
    const j = await r.json();
    if (!j.ok) {
      $("pipeline-log").textContent = j.error || "请求失败";
      toast(j.error || "失败", false);
      return;
    }
    const jobId = j.job_id;
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      const pr = await fetch("/api/pipeline/job/" + jobId);
      const pj = await pr.json();
      if (!pj.ok) return;
      $("pipeline-log").textContent = pj.log || (pj.running ? "运行中…" : "");
      if (!pj.running) {
        clearInterval(pollTimer);
        pollTimer = null;
        const ok = pj.exit_code === 0;
        toast(ok ? "流水线完成" : "退出码 " + pj.exit_code, ok);
      }
    }, 400);
  };

  $("btnExportOnly").onclick = async () => {
    $("pipeline-log").textContent = "正在运行 export_artifacts…";
    const r = await fetch("/api/export/run", { method: "POST" });
    const j = await r.json();
    $("pipeline-log").textContent = j.log || j.error || "";
    toast(j.ok ? "S9 导出完成" : j.error || "导出失败", !!j.ok);
  };

  /* ----- artifacts ----- */
  let currentArtifactName = "";

  async function refreshArtifacts() {
    const r = await fetch("/api/artifacts/list");
    const j = await r.json();
    const s = $("artifactSelect");
    s.innerHTML = "";
    if (!j.ok) {
      toast(j.error || "列表失败", false);
      return;
    }
    j.files.forEach((name) => {
      const o = document.createElement("option");
      o.value = name;
      o.textContent = name;
      s.appendChild(o);
    });
    toast("已刷新 " + j.files.length + " 个文件", true);
  }

  $("btnRefreshArtifacts").onclick = refreshArtifacts;

  $("btnLoadArtifact").onclick = async () => {
    const name = $("artifactSelect").value;
    if (!name) {
      toast("列表为空，先跑流水线或刷新", false);
      return;
    }
    currentArtifactName = name;
    const r = await fetch("/api/artifact?name=" + encodeURIComponent(name));
    const j = await r.json();
    const dl = $("btnDownloadArtifact");
    if (!j.ok) {
      $("artifact-json").textContent = j.error || "读取失败";
      dl.style.display = "none";
      return;
    }
    if (j.data !== undefined) {
      $("artifact-json").textContent = JSON.stringify(j.data, null, 2);
    } else {
      $("artifact-json").textContent = j.text || "";
    }
    dl.href = "/api/download?name=" + encodeURIComponent(name);
    dl.style.display = "inline-block";
  };

  /* ----- review ----- */
  let doc = null;
  let editCount = 0;

  function clone(o) {
    return JSON.parse(JSON.stringify(o));
  }

  function stepsToText(steps) {
    if (!Array.isArray(steps)) return "";
    return steps.join("\n");
  }

  function textToSteps(s) {
    if (!s.trim()) return [];
    if (s.includes("\n")) return s.split("\n").map((x) => x.trim()).filter(Boolean);
    return s.split("|").map((x) => x.trim()).filter(Boolean);
  }

  function fillCaseSelect() {
    const sel = $("caseSelect");
    sel.innerHTML = "";
    (doc.test_cases || []).forEach((c, i) => {
      const o = document.createElement("option");
      o.value = i;
      o.textContent = (c.case_id || i) + " — " + (c.title || "").slice(0, 40);
      sel.appendChild(o);
    });
  }

  function fillCovSelect() {
    const sel = $("covSelect");
    sel.innerHTML = "";
    (doc.coverage_items || []).forEach((c, i) => {
      const o = document.createElement("option");
      o.value = i;
      o.textContent = (c.coverage_id || i) + " — " + (c.description || "").slice(0, 36);
      sel.appendChild(o);
    });
  }

  function fillStratSelect() {
    const sel = $("stratSelect");
    sel.innerHTML = "";
    (doc.strategies || []).forEach((s, i) => {
      const o = document.createElement("option");
      o.value = i;
      o.textContent = (s.strategy_id || i) + " [" + (s.technique || "") + "]";
      sel.appendChild(o);
    });
  }

  function showCase() {
    const i = +$("caseSelect").value;
    const c = (doc.test_cases || [])[i];
    if (!c) return;
    $("caseTitle").value = c.title || "";
    $("caseTech").value = c.technique || "";
    $("caseSteps").value = stepsToText(c.steps);
    $("caseExpected").value = c.expected_result || "";
    $("caseDiff").style.display = "none";
  }

  function showCov() {
    const i = +$("covSelect").value;
    const c = (doc.coverage_items || [])[i];
    if (!c) return;
    $("covDesc").value = c.description || "";
    $("covNotes").value = c.notes || "";
  }

  function showStrat() {
    const i = +$("stratSelect").value;
    const s = (doc.strategies || [])[i];
    if (!s) return;
    $("stratTech").value = s.technique || "";
    $("stratPrompt").value = s.prompt_notes || "";
  }

  function diffCase(before, after) {
    const lines = [];
    if (before.title !== after.title) lines.push("title:\n  前: " + before.title + "\n  后: " + after.title);
    if (before.expected_result !== after.expected_result) {
      lines.push("expected_result:\n  前: " + before.expected_result + "\n  后: " + after.expected_result);
    }
    if (JSON.stringify(before.steps) !== JSON.stringify(after.steps)) {
      lines.push("steps:\n  前: " + JSON.stringify(before.steps) + "\n  后: " + JSON.stringify(after.steps));
    }
    return lines.join("\n\n") || "（无字段变化）";
  }

  $("btnReviewLoad").onclick = async () => {
    const src = $("reviewLoadSrc").value;
    const r = await fetch("/api/review/load?source=" + encodeURIComponent(src));
    const j = await r.json();
    if (!j.ok) {
      toast(j.error || "加载失败", false);
      return;
    }
    doc = j.data;
    editCount = 0;
    $("editCount").textContent = "0";
    fillCaseSelect();
    fillCovSelect();
    fillStratSelect();
    showCase();
    showCov();
    showStrat();
    $("reviewNotes").value = doc.review_notes || "";
    toast("已加载", true);
  };

  $("caseSelect").onchange = showCase;
  $("covSelect").onchange = showCov;
  $("stratSelect").onchange = showStrat;

  $("btnApplyCase").onclick = () => {
    const i = +$("caseSelect").value;
    const c = doc.test_cases[i];
    const before = clone(c);
    c.title = $("caseTitle").value;
    c.technique = $("caseTech").value;
    c.steps = textToSteps($("caseSteps").value);
    c.expected_result = $("caseExpected").value;
    editCount++;
    $("editCount").textContent = String(editCount);
    const d = $("caseDiff");
    d.style.display = "block";
    d.textContent = diffCase(before, c);
    $("caseSelect").options[i].textContent = (c.case_id || i) + " — " + (c.title || "").slice(0, 40);
    toast("用例已写入内存", true);
  };

  $("btnApplyCov").onclick = () => {
    const i = +$("covSelect").value;
    const c = doc.coverage_items[i];
    c.description = $("covDesc").value;
    c.notes = $("covNotes").value;
    editCount++;
    $("editCount").textContent = String(editCount);
    toast("覆盖项已写入内存", true);
  };

  $("btnApplyStrat").onclick = () => {
    const i = +$("stratSelect").value;
    doc.strategies[i].prompt_notes = $("stratPrompt").value;
    editCount++;
    $("editCount").textContent = String(editCount);
    toast("策略已写入内存", true);
  };

  $("btnReviewSave").onclick = async () => {
    if (!doc) {
      toast("请先加载", false);
      return;
    }
    const r = await fetch("/api/review/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document: doc,
        designer_edit_count: editCount,
        review_notes: $("reviewNotes").value.trim(),
        out_path: "work/08_reviewed.json",
      }),
    });
    const j = await r.json();
    toast(j.ok ? "已保存 " + j.path : j.error || "保存失败", j.ok);
  };
})();
