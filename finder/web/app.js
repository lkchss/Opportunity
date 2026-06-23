(function () {
  "use strict";

  // Category-adaptive detail fields. Each entry: [profileKey, label].
  // "Role / title" only appears where it makes sense.
  var FIELDS = {
    "Jobs":                       [["role", "Role / Title"], ["field", "Field / Industry"], ["location", "Location"]],
    "Internships":                [["role", "Role / Title"], ["field", "Field / Industry"], ["location", "Location"]],
    "Graduate school":            [["field", "Field of study"], ["role", "Degree level"], ["location", "Location"]],
    "Fellowships / Scholarships": [["field", "Focus area"], ["location", "Location"]],
    "Gap year programs":          [["field", "Type of program"], ["location", "Location / Region"]],
    "Travel / Volunteer":         [["field", "Cause / Focus"], ["location", "Location / Region"]]
  };

  var form = document.getElementById("finder");
  var cat = document.getElementById("cat");
  var row = document.getElementById("detail-row");
  var docInput = document.getElementById("doc");
  var docText = document.getElementById("doc-text");
  var submit = document.getElementById("submit");
  var results = document.getElementById("results");

  function renderFields() {
    var defs = FIELDS[cat.value] || FIELDS["Jobs"];
    row.style.gridTemplateColumns = "repeat(" + defs.length + ", 1fr)";
    row.innerHTML = defs.map(function (d) {
      var key = d[0], label = d[1], id = "f-" + key;
      return '<div><label class="label" for="' + id + '">' + label +
             '</label><input id="' + id + '" data-key="' + key + '" type="text" /></div>';
    }).join("");
  }
  cat.addEventListener("change", renderFields);
  renderFields();

  docInput.addEventListener("change", function () {
    if (docInput.files && docInput.files.length) {
      docText.innerHTML = "<strong>" + escapeHtml(docInput.files[0].name) + "</strong> attached.";
    }
  });

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function renderResults(data) {
    var cards = data.cards || [];
    var html = '<hr class="divider" />';
    if (!cards.length) {
      html += '<p class="note">No matches found. Try adding more detail to your background or goals.</p>';
      results.innerHTML = html;
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
    results.innerHTML = html;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var fd = new FormData();
    fd.append("category", cat.value);
    row.querySelectorAll("input[data-key]").forEach(function (inp) {
      if (inp.value.trim()) fd.append(inp.dataset.key, inp.value.trim());
    });
    fd.append("background", document.getElementById("bg").value);
    fd.append("goals", document.getElementById("goals").value);
    if (docInput.files && docInput.files.length) fd.append("doc", docInput.files[0]);

    submit.disabled = true;
    submit.textContent = "Searching…";
    results.innerHTML = '<hr class="divider" /><p class="note">Searching the web and ranking matches…</p>';

    fetch("/api/find", { method: "POST", body: fd })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j && res.j.error ? res.j.error : "Something went wrong.");
        renderResults(res.j);
      })
      .catch(function (err) {
        results.innerHTML = '<hr class="divider" /><p class="note">' + escapeHtml(err.message) + "</p>";
      })
      .finally(function () {
        submit.disabled = false;
        submit.textContent = "Find opportunities";
      });
  });
})();
