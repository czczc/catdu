# ADR-0001: Per-strip Claude Code vision via subscription

## Status

Accepted — 2026-05-24.

## Context

Meowphosis extracts ~70 cat-avatar logos from each input [[Sheet]] (1–3 sheets/day, ~200 logos/day target). Per-logo extraction needs:

- Chinese OCR of stylized labels
- Entity resolution (Chinese name → canonical English name → English Wikipedia URL)
- Visual iconography (e.g. "lightning bolt + scepter" for Zeus)
- Logo bounding boxes for cropping
- Tolerance for sheet-to-sheet layout variability (label-below vs label-left, varying grid dims)

Hard constraint: the user has a **Claude.ai subscription, not a separate Anthropic API key.**

## Decision

Run extraction as a **Claude Code skill** that uses the running Claude Code instance as the vision LLM (billed under the subscription, not via API).

Within each sheet, process **strips of cells** (not full-sheet, not per-cell):

1. **One full-sheet read** per [[Sheet]] → classify (top, sub) category, match against existing [[Set]] taxonomy or propose a new one, detect grid dimensions and layout type, produce `style_description`.
2. **One read per strip** — a row for label-below layouts (e.g. `myth-greek.png`), a column for label-left layouts (e.g. `myth-norse.png`). Each strip returns 6 cells' worth of `chinese_name`, `english_name`, `wiki_url`, `iconography`, `confidence`, `cell_number`.
3. **Python (deterministic)** does cell cropping, label-text masking with the sheet's cream background color, tight-bbox via connected components on non-background pixels, and 200×200 letterbox normalization.

## Alternatives considered

| Option | Why rejected |
|---|---|
| External Anthropic API + Python script | Requires a separate API key and billing relationship. User has subscription only. (Spike script `spike.py` preserved as the future migration path if subscription throughput is ever outgrown.) |
| Full-sheet vision call (one per sheet) | Spike-tested 2026-05-24: at 993×1583 with ~70 cells, Chinese labels are ~20px tall and the model degrades to iconography-based inference. Unreliable. |
| Per-cell vision call (one per cell) | Works — spike confirmed clean Chinese reads at 165×130 (Greek) and 228×95 (Norse) cell crops — but ~70 reads × 3 sheets/day burns Claude Code session tool budget. |
| Open-source vision via Ollama (Qwen2.5-VL etc.) | Possible later via the `SheetExtractor` interface. Skipped initially because (a) no infra setup needed for subscription path, (b) Qwen quality on stylized Chinese labels unvalidated on this dataset. |
| Heuristic-only image processing (Tesseract + classical CV) | Off-the-shelf OCR struggles with stylized fonts in the source PNGs. Spike showed Claude's vision handles them comfortably after strip cropping. |

## Consequences

**Enables**
- No API billing setup; project runs on the existing subscription.
- Layout variability handled by the model, not by per-sheet-style layout code.
- Iconography extracted alongside name resolution in the same read (no separate pass).
- Roughly 25 vision reads/day after strip batching (1 sheet-level + 6–12 strips × 3 sheets) — comfortably inside a Claude Code session.

**Costs**
- Throughput capped by Claude Code session limits and subscription rate limits. Fine at ~3 sheets/day; would not scale linearly to ~30 sheets/day without revisiting.
- Initial workflow is interactive (user invokes the skill); headless mode (`claude -p`) is the path to scripted batches.

**Reversibility**
- `SheetExtractor` is an interface; swapping implementations (API, Ollama, hybrid) means writing a new class. DB schema, image processing, website, and JSON shards are unaffected.
