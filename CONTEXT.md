# Meowphosis — Domain Context

A collection of AI-generated **cat logos**, organized by theme, browsable on a static website, and consumable as avatars by other projects (e.g. `~/Code/dunecat/`).

## Glossary

### Logo

A single AI-generated cat avatar representing one character or concept (e.g., a "Zeus cat"). The atomic unit of the collection. Every logo belongs to exactly one [[Category]] and has exactly one canonical [[Name]].

### Sheet

A single PNG file in `raw/` containing many [[Logo]]s in a grid layout (~70+ logos per sheet). Sheets are the raw input to the extraction pipeline; the pipeline cuts each sheet into individual [[Logo]] images plus metadata.

**Layout varies across sheets** — both the grid dimensions and the relative position of the text label vary:

- _Label-below_ layout (e.g. `myth-greek.png`, `game-league-of-legends.png`): label sits beneath each cat, cells are taller.
- _Label-left_ layout (e.g. `myth-norse.png`): label (number + Chinese text) sits to the left of each cat, cells are shorter and wider.

Every cell has an explicit sequential number printed in it (e.g. `01`, `02`, …, `72`), which the pipeline uses to verify cell completeness and recover from drops. Background is a uniform cream color, sampled per-sheet from a corner pixel.

### Normalized logo

The output form of a [[Logo]] after extraction: a square **200×200** PNG with the cat content occupying ~90% of the frame (uniform small margin on all sides), letterbox-padded with the sheet's cream background color where needed. Cat content is centered. This normalization makes logos uniformly substitutable as avatars across consumer projects.

### Category

A thematic grouping of [[Logo]]s. Each [[Sheet]] corresponds to exactly one Category (filename convention `<category>-<theme>.png`, e.g. `myth-greek.png` → category "Greek mythology"). Examples so far: Greek mythology, Norse mythology, Japanese mythology, League of Legends, Arknights.

### Name

Every [[Logo]] has two names:

- **English name** (canonical): used for filenames, default UI display, and English Wikipedia lookups. e.g. `Zeus`.
- **Chinese name** (source of truth from the [[Sheet]] label, optional in UI): preserved alongside the English name. e.g. `宙斯`.

**Convention:** English-first throughout — filenames, default UI language, primary wiki link target. Chinese is kept as a parallel field, exposed on demand (e.g. tooltip, detail view). Primary audience is Western users.
