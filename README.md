# meowphosis

A growing catalog of AI-generated cat avatars, organized by theme (mythology, geography, science, academia, food, …) and browsable as a static website. For domain vocabulary (logo, sheet, set, …), see [`CONTEXT.md`](CONTEXT.md).

## Setup

```bash
uv sync                   # Python deps
( cd web && npm install ) # frontend deps
```

## Running locally

Two dev servers — a FastAPI tools server (annotate / review / visibility editors + API) on `:5180`, and the Vue/Vite public site on `:5173`.

```bash
scripts/servers.sh start    # start both
scripts/servers.sh status   # health check
scripts/servers.sh logs     # tail logs
scripts/servers.sh stop     # stop both
```

Then open <http://localhost:5180/> for the editing tools and <http://localhost:5173/meowphosis/> for the public site.

## Layout

```
raw/                       sheet PNGs (input)
local/<top_category>/      per-sheet annotations + records JSON, bucketed by top category; gitignored
public/                    site-served assets; logos + catalog shards; gitignored
data/meowphosis.db         SQLite catalog DB; gitignored
scripts/                   pipeline (prep / validate / finalize / upscale / build_manifest / visibility / servers)
tools/
  annotate/                annotation editor (static + served by tools/server.py)
  review/                  review/fix editor
  visibility/              hide/show top + sub categories
  server.py                FastAPI dev server for all tools
  realesrgan/              realesrgan-ncnn-vulkan binary + anime model (gitignored; one-time setup)
web/                       Vue/Vite public site
docs/                      pipeline guide + ADRs + agent docs
.claude/skills/            invocable skills (process-cell, process-annotations)
CONTEXT.md                 domain glossary
```

## Docs

- [`docs/pipeline.md`](docs/pipeline.md) — end-to-end sheet processing (annotate → identify → review → publish)
- [`docs/adr/`](docs/adr/) — architecture decisions
- [`docs/agents/`](docs/agents/) — backlog, triage labels, agent conventions
- [`CONTEXT.md`](CONTEXT.md) — domain glossary

## Feedback

Backlog and bug reports → [GitHub Issues](https://github.com/czczc/meowphosis/issues) (triage labels in [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md)).
Open-ended feedback and ideas → [GitHub Discussions](https://github.com/czczc/meowphosis/discussions).
