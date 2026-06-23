(function () {
  "use strict";

  // ---- category-adaptive detail fields. [profileKey, label] ----
  var FIELDS = {
    "Jobs":                       [["role", "Role / Title"], ["field", "Field / Industry"], ["location", "Location"]],
    "Internships":                [["role", "Role / Title"], ["field", "Field / Industry"], ["location", "Location"]],
    "Graduate school":            [["field", "Field of study"], ["role", "Degree level"], ["location", "Location"]],
    "Fellowships / Scholarships": [["field", "Focus area"], ["location", "Location"]],
    "Gap year programs":          [["field", "Type of program"], ["location", "Location / Region"]],
    "Travel / Volunteer":         [["field", "Cause / Focus"], ["location", "Location / Region"]]
  };

  // ---- model backends ----
  var PRESETS = [
    { id: "anthropic",  label: "Claude (Anthropic)",        provider: "anthropic" },
    { id: "openai",     label: "OpenAI",                    provider: "openai", base: "" },
    { id: "ollama",     label: "Ollama (local)",            provider: "openai", base: "http://localhost:11434/v1", model: "llama3.1", local: true },
    { id: "lmstudio",   label: "LM Studio (local)",         provider: "openai", base: "http://localhost:1234/v1", local: true },
    { id: "openrouter", label: "OpenRouter",                provider: "openai", base: "https://openrouter.ai/api/v1" },
    { id: "custom",     label: "Custom (OpenAI-compatible)", provider: "openai", base: "", custom: true }
  ];
  var HINTS = {
    anthropic:  "claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5",
    openai:     "gpt-4o-mini, gpt-4o",
    ollama:     "llama3.1, qwen2.5, glm4, mistral",
    lmstudio:   "the model id loaded in LM Studio",
    openrouter: "openai/gpt-4o-mini, z-ai/glm-4.6, anthropic/claude-3.5-sonnet",
    custom:     "model id your endpoint expects"
  };
  var LS_KEY = "opp.backend";

  var els = {
    box: document.getElementById("backend-box"),
    current: document.getElementById("backend-current"),
    preset: document.getElementById("preset"),
    extra: document.getElementById("backend-extra"),
    form: document.getElementById("finder"),
    cat: document.getElementById("cat"),
    row: document.getElementById("detail-row"),
    doc: document.getElementById("doc"),
    docText: document.getElementById("doc-text"),
    submit: document.getElementById("submit"),
    results: document.getElementById("results")
  };

  var serverCfg = { provider: "none", model: "", base_url: "", has_key: false,
                    defaults: { anthropic: "", openai: "" } };

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function presetById(id) {
    for (var i = 0; i < PRESETS.length; i++) if (PRESETS[i].id === id) return PRESETS[i];
    return PRESETS[0];
  }
  function presetForCfg(cfg) {
    if (cfg.provider === "anthropic") return "anthropic";
    if (cfg.provider === "openai") {
      var b = (cfg.base_url || "").toLowerCase();
      if (b.indexOf("11434") >= 0) return "ollama";
      if (b.indexOf("1234") >= 0) return "lmstudio";
      if (b.indexOf("openrouter") >= 0) return "openrouter";
      if (!b) return "openai";
      return "custom";
    }
    return "anthropic";
  }

  // ---- backend picker ----
  function renderBackend() {
    var p = presetById(els.preset.value);
    els.current.textContent = p.label;

    var defModel = p.model || (p.provider === "anthropic" ? serverCfg.defaults.anthropic
                                                          : serverCfg.defaults.openai);
    if (presetForCfg(serverCfg) === p.id && serverCfg.model) defModel = serverCfg.model;

    var html = "";
    html += '<div class="field"><label class="label" for="m-model">Model</label>' +
            '<input id="m-model" type="text" value="' + escapeHtml(defModel) +
            '" placeholder="' + escapeHtml(HINTS[p.id] || "") + '" /></div>';
    if (p.custom || p.local) {
      html += '<div class="field"><label class="label" for="m-base">Base URL</label>' +
              '<input id="m-base" type="text" value="' + escapeHtml(p.base || "") +
              '" placeholder="https://your-endpoint/v1" /></div>';
    }
    if (!p.local) {
      var usingServer = (presetForCfg(serverCfg) === p.id && serverCfg.has_key);
      html += '<div class="field"><label class="label" for="m-key">API key</label>' +
              '<input id="m-key" type="password" placeholder="' +
              (usingServer ? "using server key (leave blank)" : "sk-…") + '" /></div>';
    } else {
      html += '<p class="hint">Local server — no API key needed.</p>';
    }
    els.extra.innerHTML = html;
  }

  function readBackend() {
    var p = presetById(els.preset.value);
    var model = (document.getElementById("m-model") || {}).value || "";
    var baseEl = document.getElementById("m-base");
    var keyEl = document.getElementById("m-key");
    var base = baseEl ? baseEl.value : (p.base || "");
    return {
      provider: p.provider,
      model: model.trim(),
      base_url: (base || "").trim(),
      api_key: keyEl ? keyEl.value : ""
    };
  }

  function saveBackend() {
    var b = readBackend();
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({ preset: els.preset.value, model: b.model, base_url: b.base_url }));
    } catch (e) { /* ignore */ }
  }

  function initBackend() {
    els.preset.innerHTML = PRESETS.map(function (p) {
      return '<option value="' + p.id + '">' + escapeHtml(p.label) + "</option>";
    }).join("");

    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(LS_KEY) || "null"); } catch (e) {}
    els.preset.value = (saved && saved.preset) || presetForCfg(serverCfg);
    renderBackend();
    if (saved) {
      var m = document.getElementById("m-model"); if (m && saved.model) m.value = saved.model;
      var b = document.getElementById("m-base"); if (b && saved.base_url) b.value = saved.base_url;
    }
    // open the picker if nothing is configured yet
    if (!serverCfg.has_key && presetForCfg(serverCfg) === "anthropic" && serverCfg.provider === "none") {
      els.box.open = true;
    }
    els.preset.addEventListener("change", function () { renderBackend(); });
    els.extra.addEventListener("input", saveBackend);
  }

  fetch("/api/config")
    .then(function (r) { return r.json(); })
    .then(function (cfg) { serverCfg = cfg; })
    .catch(function () {})
    .finally(initBackend);

  // ---- category fields ----
  function renderFields() {
    var defs = FIELDS[els.cat.value] || FIELDS["Jobs"];
    els.row.style.gridTemplateColumns = "repeat(" + defs.length + ", 1fr)";
    els.row.innerHTML = defs.map(function (d) {
      var key = d[0], label = d[1], id = "f-" + key;
      return '<div><label class="label" for="' + id + '">' + label +
             '</label><input id="' + id + '" data-key="' + key + '" type="text" /></div>';
    }).join("");
  }
  els.cat.addEventListener("change", renderFields);
  renderFields();

  els.doc.addEventListener("change", function () {
    if (els.doc.files && els.doc.files.length) {
      els.docText.innerHTML = "<strong>" + escapeHtml(els.doc.files[0].name) + "</strong> attached.";
    }
  });

  // ---- results ----
  function renderResults(data) {
    var cards = data.cards || [];
    var html = '<hr class="divider" />';
    if (!cards.length) {
      html += '<p class="note">No matches found. Try adding more detail to your background or goals.</p>';
      els.results.innerHTML = html;
      return;
    }
    html += '<div class="sec-label">' + cards.length + " opportunit" + (cards.length === 1 ? "y" : "ies") +
            (data.mode ? " &middot; " + escapeHtml(data.mode) : "") + "</div>";
    html += '<h2 class="matches-h">Your matches</h2>';
    html += cards.map(function (c) {
      var why = c.why_match
        ? '<p class="why"><strong>Why this fits:</strong> ' + escapeHtml(c.why_match) + "</p>"
        : "";
      return '<article class="card">' +
        '<h3><a href="' + escapeHtml(c.url) + '" target="_blank" rel="noopener">' + escapeHtml(c.title) + "</a></h3>" +
        '<p class="src">' + escapeHtml(c.url) + "</p>" +
        '<p class="summary">' + escapeHtml(c.summary || "") + "</p>" + why +
        "</article>";
    }).join("");
    els.results.innerHTML = html;
  }

  els.form.addEventListener("submit", function (e) {
    e.preventDefault();
    var fd = new FormData();
    fd.append("category", els.cat.value);
    els.row.querySelectorAll("input[data-key]").forEach(function (inp) {
      if (inp.value.trim()) fd.append(inp.dataset.key, inp.value.trim());
    });
    fd.append("background", document.getElementById("bg").value);
    fd.append("goals", document.getElementById("goals").value);
    if (els.doc.files && els.doc.files.length) fd.append("doc", els.doc.files[0]);

    var b = readBackend();
    fd.append("provider", b.provider);
    fd.append("model", b.model);
    fd.append("base_url", b.base_url);
    if (b.api_key) fd.append("api_key", b.api_key);
    saveBackend();

    els.submit.disabled = true;
    els.submit.textContent = "Searching…";
    els.results.innerHTML = '<hr class="divider" /><p class="note">Finding and ranking matches…</p>';

    fetch("/api/find", { method: "POST", body: fd })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j && res.j.error ? res.j.error : "Something went wrong.");
        renderResults(res.j);
      })
      .catch(function (err) {
        els.results.innerHTML = '<hr class="divider" /><p class="note">' + escapeHtml(err.message) + "</p>";
      })
      .finally(function () {
        els.submit.disabled = false;
        els.submit.textContent = "Find opportunities";
      });
  });
})();
