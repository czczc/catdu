# Meowphosis — Domain Context

A growing collection of AI-generated **cat logos**, organized by theme, browsable on a static website, and consumable as avatars by other projects (e.g. `~/Code/dunecat/`). New logos arrive in batches of ~200/day.

## Glossary

### Logo

A single AI-generated cat avatar representing one character or concept (e.g., a "Zeus cat"). The atomic unit of the [[Catalog]]. Every logo belongs to exactly one [[Set]], has one canonical [[Name]], a list of [[Iconography]] cues, and is delivered as a [[Normalized logo]] (200×200 PNG).

### Iconography

Short list of visual cues present in the cat illustration that connect the avatar to the character it represents — e.g., for `Zeus`: `["lightning bolt", "scepter"]`; for `Loki`: `["black coat", "snake"]`; for `Demeter`: `["wheat sheaf"]`.

Captured per-[[Logo]] from the same vision read that extracts the name. Used for: search/filtering ("cats holding weapons"), alt-text / accessibility, detecting label-vs-logo mismatches (low confidence when label and iconography disagree), and as a hint when classifying which [[Set]] a new [[Sheet]] belongs to (consistent iconography style across cells suggests same set).

### Sheet

A single PNG file (initially placed in `raw/`) containing many [[Logo]]s in a grid layout (~70+ logos per sheet). Sheets are the raw input to the extraction pipeline; the pipeline cuts each sheet into individual [[Logo]] images plus metadata.

**`raw/` is transient.** Filenames are arbitrary — the pipeline derives category, set, and per-logo metadata from the *content* of each sheet via a vision model, not the filename. After successful processing, sheets are moved to `raw/.processed/<date>/` as a short-lived safety window and can be cleaned up periodically.

**Layout varies across sheets** — both the grid dimensions and the relative position of the text label vary:

- _Label-below_ layout (e.g. `myth-greek.png`, `game-league-of-legends.png`): label sits beneath each cat, cells are taller.
- _Label-left_ layout (e.g. `myth-norse.png`): label (number + Chinese text) sits to the left of each cat, cells are shorter and wider.

Every cell has an explicit sequential number printed in it (e.g. `01`, `02`, …, `72`), which the pipeline uses to verify cell completeness and recover from drops. Background is a uniform cream color, sampled per-sheet from a corner pixel.

One [[Sheet]] corresponds to exactly one ([[Category]], [[Set]]) pair.

### Category

A two-level hierarchy: a **top category** containing one or more **sub-categories**. Examples:

- `mythology` → `greek`, `norse`, `japanese`
- `games` → `arknights`, `league-of-legends`

Both levels have a slug (URL-safe) and a display name. Both are proposed by the vision model when a [[Sheet]] is processed; the pipeline reuses existing slugs when the model identifies a match, and only creates a new sub-category when the content is genuinely new.

The hierarchy is fixed at two levels — deeper nesting is not supported.

### Set

A numbered visual-style batch within a sub-[[Category]]. Every (top, sub) pair has its own independent sequence starting at `1`: `mythology/greek/1`, `mythology/greek/2`, `games/arknights/1`, … A set typically corresponds to one generator/prompt/style (e.g. "pixel-art", "watercolor"), but the set number is the only identifier in URLs and IDs. Each set additionally carries a human-readable `display` name, a one-sentence `style_description`, and optional `generator` annotation — all surface in UI, none of them appear in URLs.

When a new [[Sheet]] is processed, the vision model is given the existing sets under the inferred (top, sub) and decides whether the sheet matches one or starts a new one. New sets get the next sequential number.

### Name

Every [[Logo]] has two names:

- **English name** (canonical): used for filenames, default UI display, and English Wikipedia lookups. e.g. `Zeus`.
- **Chinese name** (source of truth from the [[Sheet]] label, surfaced on demand): e.g. `宙斯`.

**Convention:** English-first throughout — filenames, default UI language, primary wiki link target. Primary audience is Western users. Chinese is preserved as a parallel field, exposed in tooltips/detail views.

### Normalized logo

The output form of a [[Logo]] after extraction: a square **200×200** PNG with the cat content occupying ~90% of the frame (uniform small margin on all sides), letterbox-padded with the [[Sheet]]'s cream background color where needed. Cat content is centered. This normalization makes logos uniformly substitutable as avatars across consumer projects.

Final file path: `<top>/<sub>/<set-number>/<english-slug>.png` (e.g. `mythology/greek/1/zeus.png`).

### Catalog

The full collection of [[Logo]]s and the structure around them: [[Category]] hierarchy, [[Set]] metadata, and per-[[Logo]] records (names, wiki links, image paths, source provenance). Source of truth lives in the project's database; the static website and external consumers (e.g. `dunecat`) read derived per-sub-category manifests.

### Within-set logo identity

Within a single [[Set]], a [[Logo]] is uniquely identified by its English-name slug. Re-extracting a [[Logo]] that already exists in a set is treated as an **upsert** (newer wins, image and metadata overwritten, source provenance refreshed) rather than a new entry. Alternate styles or variants should live in a different [[Set]].
