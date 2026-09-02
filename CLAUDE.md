# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

AI Intelligence — a compounding intelligence pipeline for AI research signal, powering both a SaaS digest product and a consulting practice from shared infrastructure.

Full architecture: [ai-intelligence-architecture.md](ai-intelligence-architecture.md) (diagram: [ai-intelligence-architecture.svg](ai-intelligence-architecture.svg)). Read it before making structural decisions — this file only summarizes what's needed day-to-day.

**Status:** pre-code. No stack, framework, or repo layout has been chosen yet. When that's decided, record it here.

## The five layers

1. **Sources** — raw pipes (lab blogs/RSS, arXiv, GitHub signals, community/policy). No transformation.
2. **Collection & Storage** — crawlers, normalize/dedupe into a canonical item schema, Postgres + vector DB. No LLM calls here — keep this layer cheap so it can scan volume.
3. **Intelligence layer** — relevance model, feature engineering, explanation (XAI) layer. This is the strategic moat: it's infrastructure, not a user-facing product. Users should experience its effects (better digests, earlier alerts), never see raw scores.
4. **Synthesis** — Claude, in two deliberately separate roles:
   - *Digest writer* — high-volume, cheap, frequent summarization.
   - *Analyst* — cross-item reasoning for consulting deliverables, expensive, on-demand.
   Don't collapse these into one prompt/mode — they have different cost profiles and serve different revenue streams.
5. **Delivery** — digest UI, consulting workspace, alerts/weak signals.

A feedback loop crosses all layers: delivery-layer interactions (reads, clicks, dwell time, annotations) flow back as training signal for the relevance model.

## Design principles to preserve

- **Keep layers 1–2 LLM-free.** Expensive model calls only happen on items that already passed relevance filtering.
- **Relevance model stays infrastructure.** Don't build UI that exposes raw scores/rankings as the product surface.
- **Keep the two Claude roles separate** (digest writer vs. analyst) — different prompts, different cost tiers, don't merge them for convenience.
- **Consulting workspace is a peer of the SaaS product**, not a bolt-on — both draw on the same collection/intelligence infrastructure.
- Explanations (XAI) are a trust/product feature, not a debug tool — evidence-backed, human-readable, not raw SHAP dumps.

## Build order

Follow the staged approach in the architecture doc rather than building the full five-layer system up front:

1. Layers 1, 2, and a basic version of 4 — digest tool with keyword/topic filters + Claude as synthesizer.
2. Replace keyword filtering with a basic relevance model (embedding similarity + recency weighting). Start collecting feedback signal immediately.
3. Run consulting engagements on the early system to learn what the analyst role needs.
4. Build the explanation layer once there's enough model data/feedback to explain.
5. Add weak signal detection and longitudinal tracking last — most data-hungry, most ambitious.

Default to whatever stage the codebase is actually at; don't scaffold later-stage abstractions (e.g. a full relevance-model training pipeline) while still in stage 1.

## Working conventions

_To be filled in as the project takes shape: language/framework choices, test commands, lint/build commands, directory layout._
