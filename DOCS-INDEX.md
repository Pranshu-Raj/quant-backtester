# Documentation Index

> **Reading order:** start here, then `ARCHITECTURE.md` → `FEATURES.md` → `SPRINTS.md` → `ROADMAP.md` → `API.md`.
> All docs live in the project root (`C:\Users\prans\Desktop\Projects\claude-projects\`). The research HTML is the companion market/landscape reference.

| Doc | What it contains | Use it when… |
|-----|------------------|-------------|
| **`backtester-research-spike.html`** | Market/landscape research (A: engine patterns, B: tearsheet & data guardrails, C: business models, D: OSS landscape & roadmap) + Research Log | you want *why* we chose this direction |
| **`backtester-architecture.md`** | Backend-only deep dive: module boundaries, data contracts, no-look-ahead enforcement, infra layer, build order (v0.1) | you need engine internals / the guarantee detail |
| **`ARCHITECTURE.md`** | **Full project**: database (two-store), backend service/API, frontend SPA, cross-cutting, end-to-end flow, phasing, open decisions (E1–E6) | you want the whole-system picture |
| **`FEATURES.md`** | Epic-by-epic feature catalog with phase tags + **Done when** acceptance tests | you're scoping or writing tests |
| **`SPRINTS.md`** | v0.1 sprint-by-sprint (S0–S9) with goals/deliverables/done-when + later-phase themes + dependency graph | you're planning the build or a sprint |
| **`ROADMAP.md`** | Phased plan v0.1→v0.5→v1.0→v2.0 with vision, must-haves, launch triggers, risks, strategic principles | you're aligning on direction / milestones |
| **`API.md`** | Exact public Python API (config/data/strategy/run/analytics/audit), CLI, HTTP API summary, determinism contract | you're writing or calling code |

---

## How the docs relate
```
research HTML (why)
      │
      ▼
ARCHITECTURE.md (whole system: DB + backend + frontend)
      │
      ├─ backtester-architecture.md (engine deep-dive, superseded view)
      ├─ FEATURES.md  (what we build, with acceptance)
      ├─ SPRINTS.md   (when/how we build it)
      ├─ ROADMAP.md   (the phased destination + triggers)
      └─ API.md       (the exact interfaces)
```

## Conventions
- **Phase tags:** `[v0.1]` build-now · `[v0.5]` launch wedge · `[v1.0]` community · `[v2.0]` business.
- **Open decisions:** `D1–D5` (MVP settings) and `E1–E6` (expanded-scope stack) — see `ARCHITECTURE.md` §8 and `ROADMAP.md`.
- **Non-negotiables:** no-look-ahead by default (architecturally enforced); pure runs; hybrid engine; everything pluggable; mandatory audit on every result.
