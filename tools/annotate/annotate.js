// Meowphosis Annotation Tool — v4
//
// Workflow:
//   1. Grid mode: drag the orange grid lines so each cell holds exactly one
//      logo. Use Rows/Cols + "Fit to image" to bootstrap.
//   2. Cat mode: click "Set cat template", then drag a rectangle inside any
//      cell over its cat illustration. The template is applied to every cell.
//      Drag any cell's box to move (interior) or resize (edges / corners) per
//      cell.
//   3. Text mode: same flow for the label region.
//   4. Optional: per-cell English override, skip toggle.
//   5. Export → JSON. Pipeline reads per-cell cat_bbox + text_bbox directly;
//      no auto-derive needed when both are present.

const STORAGE_KEY = "meowphosis.annotate.state.v4";
const DRAG_THRESHOLD_PX = 4;
const LINE_HIT_PX = 6;
const BBOX_HANDLE_PX = 8;
const MIN_LINE_GAP = 4;
const MIN_BBOX = 4;

const CELL_LINE_COLOR = "rgba(184, 92, 32, 0.55)";
const CELL_LINE_HOVER_COLOR = "rgba(184, 92, 32, 1.0)";
const CELL_LINE_FAINT = "rgba(184, 92, 32, 0.18)";
const SELECTED_OUTLINE = "rgba(58, 115, 216, 0.95)";
const CAT_COLOR = "rgba(42, 138, 63, 1)";
const CAT_COLOR_FAINT = "rgba(42, 138, 63, 0.35)";
const TEXT_COLOR = "rgba(196, 56, 56, 1)";
const TEXT_COLOR_FAINT = "rgba(196, 56, 56, 0.35)";
const SKIP_OVERLAY = "rgba(120, 120, 120, 0.45)";

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

const els = {
  sheetInput: document.getElementById("sheet-input"),
  topCat: document.getElementById("top-cat"),
  subCat: document.getElementById("sub-cat"),
  setNum: document.getElementById("set-num"),
  rows: document.getElementById("rows"),
  cols: document.getElementById("cols"),
  resetGrid: document.getElementById("reset-grid-btn"),
  modeRadios: document.querySelectorAll('input[name="mode"]'),
  setTemplate: document.getElementById("set-template-btn"),
  clearTemplate: document.getElementById("clear-template-btn"),
  templateInfo: document.getElementById("template-info"),
  modeLabel: document.getElementById("mode-label"),
  cellNum: document.getElementById("cell-num"),
  cellTotal: document.getElementById("cell-total"),
  prevCell: document.getElementById("prev-cell-btn"),
  nextCell: document.getElementById("next-cell-btn"),
  selectedInfo: document.getElementById("selected-info"),
  bboxInfo: document.getElementById("bbox-info"),
  englishOverride: document.getElementById("english-override"),
  skipCell: document.getElementById("skip-cell"),
  resetCellBbox: document.getElementById("reset-cell-bbox-btn"),
  exportBtn: document.getElementById("export-btn"),
  loadAnnotBtn: document.getElementById("load-annot-btn"),
  status: document.getElementById("status"),
};

/** Global state. Persisted to localStorage. */
const state = {
  sheetFilename: "",
  imageW: 0,
  imageH: 0,
  topCategory: "mythology",
  subCategory: "greek",
  setNumber: 1,
  rows: 12,
  cols: 6,
  xLines: [],
  yLines: [],
  // Templates: cell-relative {x, y, w, h} or null.
  catRegion: null,
  textRegion: null,
  // key = `r,c` → { cat_bbox?, text_bbox?, english_override?, skip? }
  // Bboxes are sheet coords [x1, y1, x2, y2]. Auto-instantiated when a
  // template is applied; per-cell drag tunes them individually.
  cells: {},
  selected: null,
  mode: "grid", // "grid" | "cat" | "text"
};

const volatile = {
  image: null,
  dragMode: null,
  // null | "line" | "template" | "bbox-move" | "bbox-edge" | "bbox-corner"
  dragStart: null,
  dragCurrent: null,
  draggedEnough: false,
  // line drag:
  lineKind: null,
  lineIndex: null,
  lineMin: 0,
  lineMax: 0,
  hoverLine: null,
  // template-set awaiting:
  awaitingTemplate: false,
  // bbox drag:
  bboxCellKey: null, // which cell's bbox is being dragged
  bboxKind: null, // "cat" | "text"
  bboxHandle: null, // "n"|"s"|"e"|"w"|"ne"|"nw"|"se"|"sw"|"move"
  bboxStartCoords: null, // initial bbox [x1,y1,x2,y2]
};

// ---------- Persistence ----------

function saveState() {
  const payload = {
    sheetFilename: state.sheetFilename,
    imageW: state.imageW,
    imageH: state.imageH,
    topCategory: els.topCat.value,
    subCategory: els.subCat.value,
    setNumber: Number(els.setNum.value),
    rows: state.rows,
    cols: state.cols,
    xLines: state.xLines,
    yLines: state.yLines,
    catRegion: state.catRegion,
    textRegion: state.textRegion,
    cells: state.cells,
    selected: state.selected,
    mode: state.mode,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;
  try {
    const data = JSON.parse(raw);
    Object.assign(state, data);
    els.topCat.value = data.topCategory || "mythology";
    els.subCat.value = data.subCategory || "greek";
    els.setNum.value = data.setNumber || 1;
    els.rows.value = data.rows || 12;
    els.cols.value = data.cols || 6;
    state.xLines = Array.isArray(data.xLines) ? data.xLines.slice() : [];
    state.yLines = Array.isArray(data.yLines) ? data.yLines.slice() : [];
    state.catRegion = data.catRegion || null;
    state.textRegion = data.textRegion || null;
    state.mode = data.mode || "grid";
    const radio = document.querySelector(`input[name="mode"][value="${state.mode}"]`);
    if (radio) radio.checked = true;
  } catch (e) {
    console.warn("Failed to load saved state:", e);
  }
}

// ---------- Image loading ----------

function loadSheet(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      volatile.image = img;
      state.sheetFilename = file.name;
      state.imageW = img.naturalWidth;
      state.imageH = img.naturalHeight;
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      if (state.xLines.length !== state.cols + 1 || state.yLines.length !== state.rows + 1) {
        resetGrid();
      }
      updateCellTotal();
      draw();
      setStatus(`Loaded ${file.name} (${img.naturalWidth}×${img.naturalHeight})`);
      saveState();
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function resetGrid() {
  state.xLines = evenLines(0, state.imageW || canvas.width, state.cols);
  state.yLines = evenLines(0, state.imageH || canvas.height, state.rows);
  draw();
  saveState();
}

function evenLines(lo, hi, count) {
  const out = [];
  for (let i = 0; i <= count; i++) out.push(lo + ((hi - lo) * i) / count);
  return out;
}

function resizeAxis(axis, newCount) {
  const lines = axis === "x" ? state.xLines : state.yLines;
  if (lines.length < 2) {
    const span = axis === "x" ? state.imageW : state.imageH;
    const out = evenLines(0, span || 0, newCount);
    if (axis === "x") state.xLines = out;
    else state.yLines = out;
    return;
  }
  const lo = lines[0];
  const hi = lines[lines.length - 1];
  const out = evenLines(lo, hi, newCount);
  if (axis === "x") state.xLines = out;
  else state.yLines = out;
}

// ---------- Coordinate helpers ----------

function clientToImage(event) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY,
  };
}

function imageScale() {
  const rect = canvas.getBoundingClientRect();
  return {
    sx: canvas.width / rect.width,
    sy: canvas.height / rect.height,
  };
}

function cellBounds(row, col) {
  return {
    x1: Math.round(state.xLines[col]),
    y1: Math.round(state.yLines[row]),
    x2: Math.round(state.xLines[col + 1]),
    y2: Math.round(state.yLines[row + 1]),
  };
}

function pointToCell(x, y) {
  if (!state.xLines.length || !state.yLines.length) return null;
  if (x < state.xLines[0] || x > state.xLines[state.cols]) return null;
  if (y < state.yLines[0] || y > state.yLines[state.rows]) return null;
  let col = state.cols - 1;
  for (let i = 0; i < state.cols; i++) {
    if (x >= state.xLines[i] && x < state.xLines[i + 1]) {
      col = i;
      break;
    }
  }
  let row = state.rows - 1;
  for (let i = 0; i < state.rows; i++) {
    if (y >= state.yLines[i] && y < state.yLines[i + 1]) {
      row = i;
      break;
    }
  }
  return { row, col };
}

function cellKey(row, col) {
  return `${row},${col}`;
}

function cellNumberFor(row, col) {
  return row * state.cols + col + 1;
}

function totalCells() {
  return state.rows * state.cols;
}

function hitTestLine(pt) {
  if (!state.xLines.length || !state.yLines.length) return null;
  const { sx, sy } = imageScale();
  const tx = LINE_HIT_PX * sx;
  const ty = LINE_HIT_PX * sy;
  let bestX = null;
  let bestXDist = tx;
  for (let i = 0; i < state.xLines.length; i++) {
    const d = Math.abs(pt.x - state.xLines[i]);
    if (d <= bestXDist) {
      bestXDist = d;
      bestX = i;
    }
  }
  let bestY = null;
  let bestYDist = ty;
  for (let i = 0; i < state.yLines.length; i++) {
    const d = Math.abs(pt.y - state.yLines[i]);
    if (d <= bestYDist) {
      bestYDist = d;
      bestY = i;
    }
  }
  if (bestX !== null && bestY !== null) {
    return bestXDist / tx <= bestYDist / ty
      ? { kind: "x", index: bestX }
      : { kind: "y", index: bestY };
  }
  if (bestX !== null) return { kind: "x", index: bestX };
  if (bestY !== null) return { kind: "y", index: bestY };
  return null;
}

function hitTestBbox(bbox, pt, threshold) {
  if (!bbox) return null;
  const [x1, y1, x2, y2] = bbox;
  if (pt.x < x1 - threshold || pt.x > x2 + threshold) return null;
  if (pt.y < y1 - threshold || pt.y > y2 + threshold) return null;
  const onLeft = Math.abs(pt.x - x1) <= threshold;
  const onRight = Math.abs(pt.x - x2) <= threshold;
  const onTop = Math.abs(pt.y - y1) <= threshold;
  const onBottom = Math.abs(pt.y - y2) <= threshold;
  if (onTop && onLeft) return "nw";
  if (onTop && onRight) return "ne";
  if (onBottom && onLeft) return "sw";
  if (onBottom && onRight) return "se";
  if (onTop) return "n";
  if (onBottom) return "s";
  if (onLeft) return "w";
  if (onRight) return "e";
  if (pt.x > x1 && pt.x < x2 && pt.y > y1 && pt.y < y2) return "move";
  return null;
}

function activeBboxKind() {
  if (state.mode === "cat") return "cat";
  if (state.mode === "text") return "text";
  return null;
}

function cellBbox(key, kind) {
  const c = state.cells[key];
  if (!c) return null;
  return kind === "cat" ? c.cat_bbox : c.text_bbox;
}

function setCellBbox(key, kind, bbox) {
  if (!state.cells[key]) state.cells[key] = {};
  if (kind === "cat") state.cells[key].cat_bbox = bbox;
  else state.cells[key].text_bbox = bbox;
}

// ---------- Templates ----------

function applyTemplate(kind, region) {
  // region: cell-relative {x, y, w, h}
  if (kind === "cat") state.catRegion = region;
  else state.textRegion = region;
  for (let r = 0; r < state.rows; r++) {
    for (let c = 0; c < state.cols; c++) {
      const b = cellBounds(r, c);
      const cw = b.x2 - b.x1;
      const ch = b.y2 - b.y1;
      const bbox = [
        Math.round(b.x1 + cw * region.x),
        Math.round(b.y1 + ch * region.y),
        Math.round(b.x1 + cw * (region.x + region.w)),
        Math.round(b.y1 + ch * (region.y + region.h)),
      ];
      setCellBbox(cellKey(r, c), kind, bbox);
    }
  }
}

function clearTemplate(kind) {
  if (kind === "cat") {
    state.catRegion = null;
    for (const c of Object.values(state.cells)) delete c.cat_bbox;
  } else {
    state.textRegion = null;
    for (const c of Object.values(state.cells)) delete c.text_bbox;
  }
}

function resetCellToTemplate(key, kind) {
  const region = kind === "cat" ? state.catRegion : state.textRegion;
  if (!region) return;
  const [r, c] = key.split(",").map(Number);
  const b = cellBounds(r, c);
  const cw = b.x2 - b.x1;
  const ch = b.y2 - b.y1;
  setCellBbox(key, kind, [
    Math.round(b.x1 + cw * region.x),
    Math.round(b.y1 + ch * region.y),
    Math.round(b.x1 + cw * (region.x + region.w)),
    Math.round(b.y1 + ch * (region.y + region.h)),
  ]);
}

// ---------- Drawing ----------

function draw() {
  if (!volatile.image) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }
  ctx.drawImage(volatile.image, 0, 0);

  if (state.xLines.length && state.yLines.length) {
    const x0 = state.xLines[0];
    const xN = state.xLines[state.cols];
    const y0 = state.yLines[0];
    const yN = state.yLines[state.rows];
    const lineMain = state.mode === "grid" ? CELL_LINE_COLOR : CELL_LINE_FAINT;
    const lineHover = state.mode === "grid" ? CELL_LINE_HOVER_COLOR : CELL_LINE_COLOR;

    for (let i = 0; i < state.xLines.length; i++) {
      const x = state.xLines[i];
      const isHover =
        state.mode === "grid" &&
        volatile.hoverLine &&
        volatile.hoverLine.kind === "x" &&
        volatile.hoverLine.index === i;
      const isDrag =
        volatile.dragMode === "line" && volatile.lineKind === "x" && volatile.lineIndex === i;
      ctx.strokeStyle = isHover || isDrag ? lineHover : lineMain;
      ctx.lineWidth = isDrag ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(x + 0.5, y0);
      ctx.lineTo(x + 0.5, yN);
      ctx.stroke();
    }
    for (let i = 0; i < state.yLines.length; i++) {
      const y = state.yLines[i];
      const isHover =
        state.mode === "grid" &&
        volatile.hoverLine &&
        volatile.hoverLine.kind === "y" &&
        volatile.hoverLine.index === i;
      const isDrag =
        volatile.dragMode === "line" && volatile.lineKind === "y" && volatile.lineIndex === i;
      ctx.strokeStyle = isHover || isDrag ? lineHover : lineMain;
      ctx.lineWidth = isDrag ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(x0, y + 0.5);
      ctx.lineTo(xN, y + 0.5);
      ctx.stroke();
    }
  }

  // Draw bboxes — only the active mode's bboxes are bright; opposite kind is hidden.
  const showCat = state.mode === "cat" || state.mode === "grid";
  const showText = state.mode === "text" || state.mode === "grid";
  for (let r = 0; r < state.rows; r++) {
    for (let c = 0; c < state.cols; c++) {
      const key = cellKey(r, c);
      const ann = state.cells[key];
      if (!ann) continue;
      const isSelected = state.selected && state.selected.row === r && state.selected.col === c;
      if (ann.skip) {
        const b = cellBounds(r, c);
        ctx.fillStyle = SKIP_OVERLAY;
        ctx.fillRect(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1);
      }
      if (ann.cat_bbox && showCat) {
        const color =
          state.mode === "cat"
            ? isSelected
              ? CAT_COLOR
              : CAT_COLOR_FAINT
            : CAT_COLOR_FAINT;
        drawBbox(ann.cat_bbox, color, isSelected && state.mode === "cat" ? 2 : 1);
        if (isSelected && state.mode === "cat") drawHandles(ann.cat_bbox, CAT_COLOR);
      }
      if (ann.text_bbox && showText) {
        const color =
          state.mode === "text"
            ? isSelected
              ? TEXT_COLOR
              : TEXT_COLOR_FAINT
            : TEXT_COLOR_FAINT;
        drawBbox(ann.text_bbox, color, isSelected && state.mode === "text" ? 2 : 1);
        if (isSelected && state.mode === "text") drawHandles(ann.text_bbox, TEXT_COLOR);
      }
    }
  }

  if (state.selected) {
    const b = cellBounds(state.selected.row, state.selected.col);
    ctx.strokeStyle = SELECTED_OUTLINE;
    ctx.lineWidth = 3;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(b.x1 + 1.5, b.y1 + 1.5, b.x2 - b.x1 - 3, b.y2 - b.y1 - 3);
    ctx.setLineDash([]);
  }

  if (
    volatile.dragMode === "template" &&
    volatile.draggedEnough &&
    volatile.dragStart &&
    volatile.dragCurrent
  ) {
    const r = normalizedRect(volatile.dragStart, volatile.dragCurrent);
    const color = state.mode === "cat" ? CAT_COLOR : TEXT_COLOR;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(r.x1, r.y1, r.x2 - r.x1, r.y2 - r.y1);
    ctx.restore();
  }
}

function drawBbox(bbox, color, width) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.strokeRect(bbox[0] + 0.5, bbox[1] + 0.5, bbox[2] - bbox[0], bbox[3] - bbox[1]);
}

function drawHandles(bbox, color) {
  const [x1, y1, x2, y2] = bbox;
  const { sx } = imageScale();
  const size = Math.max(4, BBOX_HANDLE_PX * sx * 0.6);
  ctx.fillStyle = "rgba(255,255,255,0.95)";
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  const corners = [
    [x1, y1],
    [x2, y1],
    [x1, y2],
    [x2, y2],
  ];
  for (const [x, y] of corners) {
    ctx.fillRect(x - size / 2, y - size / 2, size, size);
    ctx.strokeRect(x - size / 2 + 0.5, y - size / 2 + 0.5, size, size);
  }
}

function normalizedRect(a, b) {
  return {
    x1: Math.round(Math.min(a.x, b.x)),
    y1: Math.round(Math.min(a.y, b.y)),
    x2: Math.round(Math.max(a.x, b.x)),
    y2: Math.round(Math.max(a.y, b.y)),
  };
}

// ---------- Selection ----------

function selectCell(row, col) {
  if (row < 0 || row >= state.rows || col < 0 || col >= state.cols) return;
  state.selected = { row, col };
  updateCellInfo();
  updateDetailPanel();
  draw();
  saveState();
}

function nextCell(direction) {
  if (!state.selected) {
    selectCell(0, 0);
    return;
  }
  const num = cellNumberFor(state.selected.row, state.selected.col);
  const next = direction > 0 ? num + 1 : num - 1;
  const total = totalCells();
  if (next < 1 || next > total) return;
  const idx = next - 1;
  selectCell(Math.floor(idx / state.cols), idx % state.cols);
}

function updateCellTotal() {
  els.cellTotal.textContent = totalCells();
}

function updateCellInfo() {
  if (state.selected) {
    els.cellNum.textContent = cellNumberFor(state.selected.row, state.selected.col);
  } else {
    els.cellNum.textContent = "—";
  }
}

function updateDetailPanel() {
  if (!state.selected) {
    els.selectedInfo.textContent = "Click a grid cell on the image to select it.";
    els.bboxInfo.textContent = "";
    els.englishOverride.value = "";
    els.skipCell.checked = false;
    return;
  }
  const { row, col } = state.selected;
  const num = cellNumberFor(row, col);
  const b = cellBounds(row, col);
  els.selectedInfo.innerHTML = `Cell <strong>${num}</strong> (row ${row + 1}, col ${col + 1})<br/>Cell bounds: [${b.x1}, ${b.y1}, ${b.x2}, ${b.y2}]`;
  const ann = state.cells[cellKey(row, col)] || {};
  const lines = [];
  lines.push(`cat:  ${ann.cat_bbox ? "[" + ann.cat_bbox.join(", ") + "]" : "(not set)"}`);
  lines.push(`text: ${ann.text_bbox ? "[" + ann.text_bbox.join(", ") + "]" : "(not set)"}`);
  els.bboxInfo.textContent = lines.join("\n");
  els.englishOverride.value = ann.english_override || "";
  els.skipCell.checked = !!ann.skip;
}

function updateModeUi() {
  const mode = state.mode;
  els.modeLabel.textContent = mode === "cat" ? "cat" : mode === "text" ? "text" : "grid";
  if (mode === "grid") {
    els.setTemplate.disabled = true;
    els.clearTemplate.disabled = true;
    els.resetCellBbox.disabled = true;
    els.templateInfo.textContent = "Drag the orange grid lines to resize rows/columns.";
  } else {
    els.setTemplate.disabled = false;
    els.clearTemplate.disabled = false;
    els.resetCellBbox.disabled = false;
    const region = mode === "cat" ? state.catRegion : state.textRegion;
    if (region) {
      els.templateInfo.textContent = `${mode}_region: x=${region.x.toFixed(2)}, y=${region.y.toFixed(2)}, w=${region.w.toFixed(2)}, h=${region.h.toFixed(2)} — drag any cell's box to fine-tune.`;
    } else {
      els.templateInfo.textContent = `No ${mode} template yet. Click "Set template" then drag inside a cell.`;
    }
  }
}

function ensureCell() {
  if (!state.selected) return null;
  const key = cellKey(state.selected.row, state.selected.col);
  if (!state.cells[key]) state.cells[key] = {};
  return key;
}

function pruneCell(key) {
  const c = state.cells[key];
  if (!c) return;
  if (!c.cat_bbox && !c.text_bbox && !c.english_override && !c.skip) delete state.cells[key];
}

function toggleSkip(skip) {
  const key = ensureCell();
  if (!key) return;
  if (skip) state.cells[key].skip = true;
  else delete state.cells[key].skip;
  pruneCell(key);
  draw();
  saveState();
}

function cursorForHandle(handle) {
  switch (handle) {
    case "n":
    case "s":
      return "ns-resize";
    case "e":
    case "w":
      return "ew-resize";
    case "ne":
    case "sw":
      return "nesw-resize";
    case "nw":
    case "se":
      return "nwse-resize";
    case "move":
      return "move";
    default:
      return null;
  }
}

function applyHandleDrag(bbox, handle, dx, dy) {
  let [x1, y1, x2, y2] = bbox;
  switch (handle) {
    case "move":
      x1 += dx;
      y1 += dy;
      x2 += dx;
      y2 += dy;
      break;
    case "n":
      y1 += dy;
      break;
    case "s":
      y2 += dy;
      break;
    case "e":
      x2 += dx;
      break;
    case "w":
      x1 += dx;
      break;
    case "ne":
      y1 += dy;
      x2 += dx;
      break;
    case "nw":
      y1 += dy;
      x1 += dx;
      break;
    case "se":
      y2 += dy;
      x2 += dx;
      break;
    case "sw":
      y2 += dy;
      x1 += dx;
      break;
  }
  if (handle !== "move") {
    if (x2 - x1 < MIN_BBOX) {
      if (handle.includes("w")) x1 = x2 - MIN_BBOX;
      else x2 = x1 + MIN_BBOX;
    }
    if (y2 - y1 < MIN_BBOX) {
      if (handle.includes("n")) y1 = y2 - MIN_BBOX;
      else y2 = y1 + MIN_BBOX;
    }
  }
  return [Math.round(x1), Math.round(y1), Math.round(x2), Math.round(y2)];
}

// ---------- Canvas events ----------

canvas.addEventListener("mousedown", (e) => {
  if (!volatile.image) return;
  const pt = clientToImage(e);

  if (volatile.awaitingTemplate) {
    volatile.dragMode = "template";
    volatile.dragStart = pt;
    volatile.dragCurrent = pt;
    volatile.draggedEnough = false;
    e.preventDefault();
    return;
  }

  if (state.mode === "grid") {
    const hit = hitTestLine(pt);
    if (hit) {
      volatile.dragMode = "line";
      volatile.lineKind = hit.kind;
      volatile.lineIndex = hit.index;
      if (hit.kind === "x") {
        volatile.lineMin = hit.index === 0 ? 0 : state.xLines[hit.index - 1] + MIN_LINE_GAP;
        volatile.lineMax =
          hit.index === state.cols ? state.imageW : state.xLines[hit.index + 1] - MIN_LINE_GAP;
      } else {
        volatile.lineMin = hit.index === 0 ? 0 : state.yLines[hit.index - 1] + MIN_LINE_GAP;
        volatile.lineMax =
          hit.index === state.rows ? state.imageH : state.yLines[hit.index + 1] - MIN_LINE_GAP;
      }
      e.preventDefault();
      return;
    }
    // Click in grid mode just selects cell
    const cell = pointToCell(pt.x, pt.y);
    if (cell) selectCell(cell.row, cell.col);
    return;
  }

  // cat / text mode: try bbox hit-test on every cell's box of active kind
  const kind = activeBboxKind();
  const { sx } = imageScale();
  const threshold = BBOX_HANDLE_PX * sx;
  // Prefer selected cell's bbox first so handles win when overlapping
  const order = [];
  if (state.selected) order.push(cellKey(state.selected.row, state.selected.col));
  for (const k of Object.keys(state.cells)) if (!order.includes(k)) order.push(k);
  let hitKey = null;
  let handle = null;
  for (const k of order) {
    const bbox = cellBbox(k, kind);
    if (!bbox) continue;
    const h = hitTestBbox(bbox, pt, threshold);
    if (h) {
      hitKey = k;
      handle = h;
      break;
    }
  }
  if (hitKey) {
    const [r, c] = hitKey.split(",").map(Number);
    selectCell(r, c);
    volatile.dragMode = handle === "move" ? "bbox-move" : "bbox-edge";
    volatile.bboxCellKey = hitKey;
    volatile.bboxKind = kind;
    volatile.bboxHandle = handle;
    volatile.bboxStartCoords = cellBbox(hitKey, kind).slice();
    volatile.dragStart = pt;
    e.preventDefault();
    return;
  }
  // No bbox hit → select cell at point
  const cell = pointToCell(pt.x, pt.y);
  if (cell) selectCell(cell.row, cell.col);
});

canvas.addEventListener("mousemove", (e) => {
  const pt = clientToImage(e);
  if (volatile.dragMode === "template") {
    volatile.dragCurrent = pt;
    const dx = pt.x - volatile.dragStart.x;
    const dy = pt.y - volatile.dragStart.y;
    if (Math.abs(dx) > DRAG_THRESHOLD_PX || Math.abs(dy) > DRAG_THRESHOLD_PX) {
      volatile.draggedEnough = true;
    }
    draw();
    return;
  }
  if (volatile.dragMode === "line") {
    let v = volatile.lineKind === "x" ? pt.x : pt.y;
    v = Math.max(volatile.lineMin, Math.min(volatile.lineMax, v));
    if (volatile.lineKind === "x") state.xLines[volatile.lineIndex] = v;
    else state.yLines[volatile.lineIndex] = v;
    updateDetailPanel();
    draw();
    return;
  }
  if (volatile.dragMode === "bbox-move" || volatile.dragMode === "bbox-edge") {
    const dx = pt.x - volatile.dragStart.x;
    const dy = pt.y - volatile.dragStart.y;
    const newBbox = applyHandleDrag(
      volatile.bboxStartCoords,
      volatile.bboxHandle,
      dx,
      dy,
    );
    setCellBbox(volatile.bboxCellKey, volatile.bboxKind, newBbox);
    updateDetailPanel();
    draw();
    return;
  }

  // Hover: update cursor
  if (state.mode === "grid") {
    const hit = hitTestLine(pt);
    const prev = volatile.hoverLine;
    if (hit) {
      canvas.style.cursor = hit.kind === "x" ? "ew-resize" : "ns-resize";
      if (!prev || prev.kind !== hit.kind || prev.index !== hit.index) {
        volatile.hoverLine = hit;
        draw();
      }
    } else {
      canvas.style.cursor = "crosshair";
      if (prev) {
        volatile.hoverLine = null;
        draw();
      }
    }
    return;
  }
  // cat/text hover: bbox handles
  const kind = activeBboxKind();
  const { sx } = imageScale();
  const threshold = BBOX_HANDLE_PX * sx;
  let foundCursor = null;
  if (state.selected) {
    const k = cellKey(state.selected.row, state.selected.col);
    const bbox = cellBbox(k, kind);
    if (bbox) {
      const h = hitTestBbox(bbox, pt, threshold);
      if (h) foundCursor = cursorForHandle(h);
    }
  }
  if (!foundCursor) {
    for (const k of Object.keys(state.cells)) {
      const bbox = cellBbox(k, kind);
      if (!bbox) continue;
      const h = hitTestBbox(bbox, pt, threshold);
      if (h) {
        foundCursor = cursorForHandle(h);
        break;
      }
    }
  }
  canvas.style.cursor = foundCursor || "crosshair";
});

canvas.addEventListener("mouseup", (e) => {
  const pt = clientToImage(e);
  if (volatile.dragMode === "template") {
    const wasDrag = volatile.draggedEnough;
    const start = volatile.dragStart;
    volatile.dragMode = null;
    volatile.dragStart = null;
    volatile.dragCurrent = null;
    volatile.draggedEnough = false;
    volatile.awaitingTemplate = false;
    if (wasDrag) {
      const r = normalizedRect(start, pt);
      const cx = (r.x1 + r.x2) / 2;
      const cy = (r.y1 + r.y2) / 2;
      const cell = pointToCell(cx, cy);
      if (cell) {
        const b = cellBounds(cell.row, cell.col);
        const cw = b.x2 - b.x1;
        const ch = b.y2 - b.y1;
        const region = {
          x: Math.max(0, (r.x1 - b.x1) / cw),
          y: Math.max(0, (r.y1 - b.y1) / ch),
          w: Math.min(1, (r.x2 - r.x1) / cw),
          h: Math.min(1, (r.y2 - r.y1) / ch),
        };
        applyTemplate(state.mode, region);
        updateModeUi();
        setStatus(`${state.mode} template applied to all ${totalCells()} cells.`);
        saveState();
      }
    } else {
      setStatus("Template not changed (drag distance too small).");
    }
    draw();
    return;
  }
  if (volatile.dragMode === "line") {
    volatile.dragMode = null;
    volatile.lineKind = null;
    volatile.lineIndex = null;
    updateDetailPanel();
    saveState();
    draw();
    return;
  }
  if (volatile.dragMode === "bbox-move" || volatile.dragMode === "bbox-edge") {
    volatile.dragMode = null;
    volatile.bboxCellKey = null;
    volatile.bboxKind = null;
    volatile.bboxHandle = null;
    volatile.bboxStartCoords = null;
    volatile.dragStart = null;
    saveState();
    return;
  }
});

canvas.addEventListener("mouseleave", () => {
  if (volatile.dragMode) {
    volatile.dragMode = null;
    volatile.dragStart = null;
    volatile.dragCurrent = null;
    volatile.draggedEnough = false;
    saveState();
  }
  volatile.hoverLine = null;
  canvas.style.cursor = "crosshair";
  draw();
});

// ---------- UI events ----------

els.sheetInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) loadSheet(file);
});

els.rows.addEventListener("change", () => {
  const newRows = Math.max(1, parseInt(els.rows.value, 10) || 1);
  resizeAxis("y", newRows);
  state.rows = newRows;
  // Per-cell bboxes from old row count no longer make sense; clear them.
  state.cells = {};
  updateCellTotal();
  updateDetailPanel();
  updateModeUi();
  draw();
  saveState();
});

els.cols.addEventListener("change", () => {
  const newCols = Math.max(1, parseInt(els.cols.value, 10) || 1);
  resizeAxis("x", newCols);
  state.cols = newCols;
  state.cells = {};
  updateCellTotal();
  updateDetailPanel();
  updateModeUi();
  draw();
  saveState();
});

els.resetGrid.addEventListener("click", () => {
  resetGrid();
  state.cells = {};
  updateDetailPanel();
  draw();
});

for (const radio of els.modeRadios) {
  radio.addEventListener("change", () => {
    state.mode = radio.value;
    volatile.awaitingTemplate = false;
    updateModeUi();
    updateDetailPanel();
    draw();
    saveState();
  });
}

els.setTemplate.addEventListener("click", () => {
  if (state.mode === "grid") return;
  volatile.awaitingTemplate = true;
  setStatus(`Drag a rectangle inside any cell to set the ${state.mode} template (applies to every cell).`);
});

els.clearTemplate.addEventListener("click", () => {
  if (state.mode === "grid") return;
  clearTemplate(state.mode);
  updateModeUi();
  updateDetailPanel();
  draw();
  saveState();
});

els.resetCellBbox.addEventListener("click", () => {
  if (state.mode === "grid" || !state.selected) return;
  const key = cellKey(state.selected.row, state.selected.col);
  resetCellToTemplate(key, state.mode);
  updateDetailPanel();
  draw();
  saveState();
});

els.prevCell.addEventListener("click", () => nextCell(-1));
els.nextCell.addEventListener("click", () => nextCell(1));

els.englishOverride.addEventListener("change", () => {
  const key = ensureCell();
  if (!key) return;
  const val = els.englishOverride.value.trim();
  if (val) state.cells[key].english_override = val;
  else delete state.cells[key].english_override;
  pruneCell(key);
  saveState();
});

els.skipCell.addEventListener("change", () => toggleSkip(els.skipCell.checked));

document.addEventListener("keydown", (e) => {
  if (document.activeElement && document.activeElement.tagName === "INPUT") return;
  if (e.key === "g" || e.key === "G") setMode("grid");
  else if (e.key === "c" || e.key === "C") setMode("cat");
  else if (e.key === "t" || e.key === "T") setMode("text");
  else if (e.key === "ArrowRight") {
    nextCell(1);
    e.preventDefault();
  } else if (e.key === "ArrowLeft") {
    nextCell(-1);
    e.preventDefault();
  } else if (e.key === "s") {
    if (!state.selected) return;
    const key = cellKey(state.selected.row, state.selected.col);
    const cur = state.cells[key]?.skip || false;
    toggleSkip(!cur);
    updateDetailPanel();
  }
});

function setMode(mode) {
  state.mode = mode;
  const r = document.querySelector(`input[name="mode"][value="${mode}"]`);
  if (r) r.checked = true;
  volatile.awaitingTemplate = false;
  updateModeUi();
  updateDetailPanel();
  draw();
  saveState();
}

// ---------- Export / import ----------

function buildAnnotationsJson() {
  const cells = [];
  for (let r = 0; r < state.rows; r++) {
    for (let c = 0; c < state.cols; c++) {
      const ann = state.cells[cellKey(r, c)];
      if (!ann) continue;
      if (!ann.cat_bbox && !ann.text_bbox && !ann.english_override && !ann.skip) continue;
      const entry = { cell_number: cellNumberFor(r, c) };
      if (ann.cat_bbox) entry.cat_bbox = ann.cat_bbox;
      if (ann.text_bbox) entry.text_bbox = ann.text_bbox;
      if (ann.english_override) entry.english_override = ann.english_override;
      if (ann.skip) entry.skip = true;
      cells.push(entry);
    }
  }
  return {
    sheet_filename: state.sheetFilename,
    image_size: [state.imageW, state.imageH],
    top_category: els.topCat.value.trim(),
    sub_category: els.subCat.value.trim(),
    set_number: Number(els.setNum.value),
    grid: {
      rows: state.rows,
      cols: state.cols,
      x_lines: state.xLines.map((v) => Math.round(v)),
      y_lines: state.yLines.map((v) => Math.round(v)),
      ...(state.catRegion ? { cat_region: state.catRegion } : {}),
      ...(state.textRegion ? { text_region: state.textRegion } : {}),
    },
    cells,
  };
}

els.exportBtn.addEventListener("click", async () => {
  const data = buildAnnotationsJson();
  const json = JSON.stringify(data, null, 2);
  const defaultName = state.sheetFilename
    ? state.sheetFilename.replace(/\.[^.]+$/, "") + ".annotations.json"
    : "annotations.json";

  if ("showSaveFilePicker" in window) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: defaultName,
        types: [{ description: "JSON", accept: { "application/json": [".json"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(json);
      await writable.close();
      setStatus(`Exported ${data.cells.length} cell entries.`);
      return;
    } catch (err) {
      if (err.name === "AbortError") return;
      console.warn("showSaveFilePicker failed, falling back:", err);
    }
  }
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = defaultName;
  a.click();
  URL.revokeObjectURL(url);
  setStatus(`Exported ${data.cells.length} cell entries (downloaded).`);
});

els.loadAnnotBtn.addEventListener("click", async () => {
  let file;
  if ("showOpenFilePicker" in window) {
    try {
      const [handle] = await window.showOpenFilePicker({
        types: [{ description: "JSON", accept: { "application/json": [".json"] } }],
      });
      file = await handle.getFile();
    } catch (err) {
      if (err.name === "AbortError") return;
      console.warn("showOpenFilePicker failed:", err);
    }
  }
  if (!file) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,application/json";
    input.onchange = (e) => {
      const f = e.target.files[0];
      if (f) ingestAnnotationsFile(f);
    };
    input.click();
    return;
  }
  ingestAnnotationsFile(file);
});

function ingestAnnotationsFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result);
      applyAnnotationsJson(data);
      setStatus(`Loaded ${data.cells.length} cell entries from ${file.name}`);
    } catch (err) {
      setStatus(`Failed to parse ${file.name}: ${err.message}`);
    }
  };
  reader.readAsText(file);
}

function applyAnnotationsJson(data) {
  els.topCat.value = data.top_category || "";
  els.subCat.value = data.sub_category || "";
  els.setNum.value = data.set_number || 1;
  state.topCategory = data.top_category;
  state.subCategory = data.sub_category;
  state.setNumber = data.set_number;
  state.sheetFilename = data.sheet_filename || "";
  if (data.image_size) {
    state.imageW = data.image_size[0];
    state.imageH = data.image_size[1];
  }
  if (data.grid) {
    state.rows = data.grid.rows;
    state.cols = data.grid.cols;
    els.rows.value = state.rows;
    els.cols.value = state.cols;
    if (Array.isArray(data.grid.x_lines) && Array.isArray(data.grid.y_lines)) {
      state.xLines = data.grid.x_lines.slice();
      state.yLines = data.grid.y_lines.slice();
    } else if (data.grid.extent) {
      const { x1, y1, x2, y2 } = data.grid.extent;
      state.xLines = evenLines(x1, x2, state.cols);
      state.yLines = evenLines(y1, y2, state.rows);
    }
    state.catRegion = data.grid.cat_region || null;
    state.textRegion = data.grid.text_region || null;
  }
  state.cells = {};
  for (const cell of data.cells || []) {
    const num = cell.cell_number;
    const idx = num - 1;
    const row = Math.floor(idx / state.cols);
    const col = idx % state.cols;
    const key = cellKey(row, col);
    state.cells[key] = {};
    if (cell.cat_bbox) state.cells[key].cat_bbox = cell.cat_bbox;
    if (cell.text_bbox) state.cells[key].text_bbox = cell.text_bbox;
    if (cell.english_override) state.cells[key].english_override = cell.english_override;
    if (cell.skip) state.cells[key].skip = true;
  }
  updateCellTotal();
  updateCellInfo();
  updateDetailPanel();
  updateModeUi();
  draw();
  saveState();
}

function setStatus(msg) {
  els.status.textContent = msg;
}

// ---------- Init ----------

loadState();
updateCellTotal();
updateCellInfo();
updateDetailPanel();
updateModeUi();
draw();
