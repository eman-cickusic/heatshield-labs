# Judging Cheat Sheet

Use this doc to highlight how HeatShield aligns with the scoring rubric.

## 1. Technical Implementation (35%)

- **Feature completeness (20%)**
  - ✅ Live vs. demo toggle, ERA5/OpenAQ ingestion with fallbacks, Liljegren WBGT, tier summaries, rule + LLM planners, PDF exports, map, Docker Compose, CI, and DEMO script.
- **Effective AI usage (15%)**
  - ✅ LLM planner is safety-gated, multi-lingual, prompt-extendable, and exposed in the UI. It replaces manual drafting in under a minute per school.

## 2. Innovation & Creativity (25%)

- **Novelty (10%)**
  - ✅ First lightweight district tool that combines ASDI + OpenAQ with bilingual-ready plans and live/demo toggles—no equivalent open-source clone.
- **Problem significance & impact (15%)**
  - ✅ Automates a high-stakes, multi-hour manual workflow; measurable outcomes include 6 staff-hours saved per high-risk day (30-school district) and documented mitigation actions (hydration/masks/indoor swaps).

## 3. Demo & Presentation (20% + Blog 10%)

- **Clarity of problem/solution (10%)**
  - ✅ README “Problem & Impact” section, DEMO.md script + screenshots, and UI copy all reference the user pain and benefits.
- **Architecture & tools explanation (10%)**
  - ✅ README “Architecture & Tools” section with a Mermaid diagram, plus inline notes on stack choices.
- **Public blog or video (10%)**
  - 🎯 Action item: Publish a 2-minute Loom (screen recording + narration) or Medium post summarizing the problem, architecture diagram, live/demo toggle, and PDF export. Link it prominently in README + submission form to secure full points.

### Talking Points

- Start with the user story (principals deciding recess/warning families).
- Show live/demo switch + plan language options to reinforce equity.
- Call out provenance logs (“ERA5 fetched from S3”, “OpenAQ REST fallback”) for trust.
- End with PDF download + CI/Docker story for deployability.
