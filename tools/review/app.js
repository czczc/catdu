const sheetSelect = document.getElementById("sheet-select");
const flaggedOnly = document.getElementById("flagged-only");
const counts = document.getElementById("counts");
const cellsEl = document.getElementById("cells");
const applyBtn = document.getElementById("apply-btn");
const applyOutput = document.getElementById("apply-output");
const tpl = document.getElementById("cell-template");

let currentSheet = null;
let currentData = null;

async function loadSheets() {
  const sheets = await fetch("/api/sheets").then((r) => r.json());
  sheetSelect.innerHTML = "";
  for (const s of sheets) {
    const opt = document.createElement("option");
    opt.value = s.stem;
    opt.textContent = `${s.stem}  (${s.cells_flagged}/${s.cells_total} flagged)`;
    sheetSelect.appendChild(opt);
  }
  if (sheets.length) {
    sheetSelect.value = sheets[0].stem;
    await loadSheet(sheets[0].stem);
  }
}

async function loadSheet(stem) {
  currentSheet = stem;
  applyOutput.hidden = true;
  applyOutput.textContent = "";
  currentData = await fetch(`/api/sheets/${stem}`).then((r) => r.json());
  render();
}

function isFlagged(cell) {
  return (
    (cell.confidence ?? 1) < 0.7 ||
    !cell.wiki_url ||
    (cell.english_slug || "").startsWith("unknown-")
  );
}

function flagsFor(cell) {
  const out = [];
  if ((cell.confidence ?? 1) < 0.7) out.push(`low conf ${cell.confidence ?? 0}`);
  if (!cell.wiki_url) out.push("no wiki");
  if ((cell.english_slug || "").startsWith("unknown-")) out.push("unknown");
  return out;
}

function render() {
  cellsEl.innerHTML = "";
  let shown = 0;
  let flagged = 0;
  for (const cell of currentData.cells) {
    const f = isFlagged(cell);
    if (f) flagged += 1;
    if (flaggedOnly.checked && !f) continue;
    cellsEl.appendChild(renderCell(cell, f));
    shown += 1;
  }
  counts.textContent = `showing ${shown} / ${currentData.cells.length} (${flagged} flagged)`;
}

function renderCell(cell, flagged) {
  const node = tpl.content.cloneNode(true);
  const art = node.querySelector("article");
  art.dataset.cell = cell.cell_number;
  if (flagged) art.classList.add("flagged");

  art.querySelector(".num").textContent = `Cell ${cell.cell_number}`;
  const flagsEl = art.querySelector(".flags");
  for (const f of flagsFor(cell)) {
    const s = document.createElement("span");
    s.className = "flag";
    s.textContent = f;
    flagsEl.appendChild(s);
  }

  art.querySelector(".composite").src = cell.composite_url;
  const logoImg = art.querySelector(".logo");
  if (cell.logo_url) {
    logoImg.src = cell.logo_url + `?t=${Date.now()}`;
    logoImg.onerror = () => {
      logoImg.removeAttribute("src");
    };
  }

  const inputs = {};
  for (const inp of art.querySelectorAll("[data-field]")) {
    const k = inp.dataset.field;
    inputs[k] = inp;
    inp.value = cell[k] ?? "";
    inp.addEventListener("input", () => art.classList.add("dirty"));
  }
  art
    .querySelector(".save")
    .removeAttribute("disabled");

  // Iconography editor
  const chipsEl = art.querySelector(".chips");
  const iconState = [...(cell.iconography || [])];
  function renderChips() {
    chipsEl.innerHTML = "";
    iconState.forEach((ic, i) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = ic;
      const x = document.createElement("button");
      x.type = "button";
      x.textContent = "×";
      x.addEventListener("click", () => {
        iconState.splice(i, 1);
        renderChips();
        art.classList.add("dirty");
      });
      chip.appendChild(x);
      chipsEl.appendChild(chip);
    });
  }
  renderChips();
  const addInput = art.querySelector(".icon-add");
  addInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const v = addInput.value.trim();
      if (v) {
        iconState.push(v);
        renderChips();
        art.classList.add("dirty");
      }
      addInput.value = "";
    }
  });

  art.querySelector(".save").addEventListener("click", async () => {
    const payload = {
      chinese_name: inputs.chinese_name.value || null,
      english_name: inputs.english_name.value || null,
      english_slug: inputs.english_slug.value || null,
      wiki_url: inputs.wiki_url.value || null,
      iconography: iconState,
      summary: inputs.summary.value.trim() || null,
      confidence: parseFloat(inputs.confidence.value) || 0,
    };
    const r = await fetch(
      `/api/sheets/${currentSheet}/cells/${cell.cell_number}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    if (!r.ok) {
      alert(`Save failed: ${await r.text()}`);
      return;
    }
    // Update local state and re-render the card to refresh flags.
    Object.assign(cell, payload);
    art.classList.remove("dirty");
    flagsEl.innerHTML = "";
    for (const f of flagsFor(cell)) {
      const s = document.createElement("span");
      s.className = "flag";
      s.textContent = f;
      flagsEl.appendChild(s);
    }
    art.classList.toggle("flagged", isFlagged(cell));
  });

  art.querySelector(".delete").addEventListener("click", async () => {
    if (
      !confirm(
        `Delete cell ${cell.cell_number} (${cell.english_name})? This also marks it as skipped in annotations.json.`,
      )
    )
      return;
    const r = await fetch(
      `/api/sheets/${currentSheet}/cells/${cell.cell_number}`,
      { method: "DELETE" },
    );
    if (!r.ok) {
      alert(`Delete failed: ${await r.text()}`);
      return;
    }
    currentData.cells = currentData.cells.filter(
      (c) => c.cell_number !== cell.cell_number,
    );
    render();
  });

  return node;
}

applyBtn.addEventListener("click", async () => {
  if (!currentSheet) return;
  applyBtn.disabled = true;
  applyBtn.textContent = "Applying…";
  applyOutput.hidden = false;
  applyOutput.textContent = "Running finalize_annotations.py…\n";
  try {
    const r = await fetch(`/api/sheets/${currentSheet}/apply`, {
      method: "POST",
    });
    const j = await r.json();
    applyOutput.textContent =
      (j.gc_removed?.length
        ? `Removed stale logos: ${j.gc_removed.join(", ")}\n\n`
        : "") +
      `--- stdout ---\n${j.stdout}\n` +
      `--- stderr ---\n${j.stderr}\n` +
      `exit ${j.returncode}`;
    // Reload sheet to refresh logo URLs (cache-bust).
    await loadSheet(currentSheet);
  } catch (e) {
    applyOutput.textContent = `Error: ${e}`;
  } finally {
    applyBtn.disabled = false;
    applyBtn.textContent = "Apply → DB";
  }
});

sheetSelect.addEventListener("change", () => loadSheet(sheetSelect.value));
flaggedOnly.addEventListener("change", render);

loadSheets();
