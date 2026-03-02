# Product Identification System — Cloud Function Architecture

> **See [WORKFLOW.md](../docs/WORKFLOW.md) for full end-to-end documentation.**

## Overview
Serverless product identification that normalizes distributor invoice items into internal catalog naming.

Target: Google Cloud Functions. Stateless request → deterministic pipeline. Philosophy: **Research → Facts → Catalog**.

---

## System Goals
1. Accept invoice line items.
2. Research product facts (manual, DuckDuckGo, or Perplexity).
3. Transform facts → catalog (Judge).
4. Learn over time via vendor cache.
5. No recursive AI agent loops.
6. Single function invocation per line.

---

## Pipeline (Current)

Invoice Line → [1] Vendor Cache → [2] Research (Fact Sheet) → [3] Judge → [4] Formatter → [5] Persist Learning → Response

---

## Core Design Principles

### No Autonomous Agents
Do NOT use ReAct or recursive agent loops.

### Separation of Responsibilities
- Research Worker → gathers evidence
- Judge Model → makes decision
- Formatter → enforces naming
- Cache → reduces future compute

### Controlled Research Budget
MAX_SEARCHES = 2

### Self-Learning System
Every successful resolution improves future performance.

---

## Cloud Function Structure

identify_product/
 ├── main.py
 ├── cache.py
 ├── research.py
 ├── judge.py
 ├── formatter.py
 ├── models.py
 ├── requirements.txt
 └── PRODUCT_IDENTIFICATION_ARCHITECTURE.md

---

## Cloud Function Entry Point (main.py)

def identify_product(request):

    vendor_notation = request.json["vendor_notation"]

    result = check_vendor_cache(vendor_notation)
    if result:
        return result

    knowledge = get_variant_knowledge(vendor_notation)

    if not knowledge:
        knowledge = run_research_worker(vendor_notation)

    decision = run_judge_model(
        vendor_notation,
        knowledge
    )

    final = format_output(decision)

    save_learning(vendor_notation, final, knowledge)

    return final

---

## Vendor Cache

Table: vendor_mapping

Fields:
- vendor_notation STRING
- product STRING
- variant STRING
- confidence FLOAT
- updated_at TIMESTAMP

Expected hit rate after training: 60–80%.

---

## Variant Knowledge Cache

Table: album_variant_knowledge

Fields:
- artist STRING
- album STRING
- variants ARRAY<STRING>
- last_verified TIMESTAMP

Example:
AMPERS&ONE | ONE HEARTED | ["KIWEE VER.", "POSTCARD VER.", "RANDOM"]

Purpose:
Eliminate repeated web searches.

---

## Research Worker (research.py)

Responsibilities:
- Discover album variants
- Collect supporting evidence
- Never choose SKU

Execution Rules:
- Maximum 2 searches
- Deterministic queries
- Structured output only

Example:

def run_research_worker(vendor_notation):

    queries = [
        vendor_notation,
        f"{vendor_notation} album versions"
    ]

    results = []

    for q in queries[:2]:
        results.append(web_search(q))

    return extract_variants(results)

Output Example:

{
  "album": "ONE HEARTED",
  "variants_found": [
    "KIWEE VER.",
    "POSTCARD VER.",
    "RANDOM"
  ]
}

---

## Judge Model (judge.py)

Responsibilities:
- Interpret research evidence
- Select canonical product
- Decide variant
- Produce structured JSON

Restrictions:
- No web search
- No tool access

Prompt:

"You are a product normalization judge.
Using vendor notation and research evidence,
determine canonical product and variant.
Return ONLY JSON."

Output:

{
  "product": "AMPERS&ONE - ONE HEARTED (2ND SINGLE ALBUM)",
  "variant": "RANDOM VER.",
  "confidence": 0.88
}

---

## Naming Formatter (formatter.py)

Convention:
product: {artist} - {album} ({extra_info})
variant: {variant}

Example:
Product: AMPERS&ONE - ONE HEARTED (2ND SINGLE ALBUM)
Variant: RANDOM VER.

---

## Learning Persistence

After successful resolution:
- Store vendor mapping
- Store variant knowledge

save_learning(vendor_notation, result, knowledge)

---

## Execution Flow Summary

Request
 ↓
Vendor Cache Hit?
 ├─ YES → Return
 └─ NO
      ↓
Variant Knowledge Exists?
 ├─ YES → Judge
 └─ NO
      ↓
Research Worker (max 2 searches)
      ↓
Judge Model
      ↓
Formatter
      ↓
Persist Learning
      ↓
Response

---

## Confidence Routing

≥ 0.80 → Auto accept
0.50–0.79 → Human review
< 0.50 → Retry research

---

## Expected System Evolution

Early Stage:
- Frequent web search
- Lower cache hit rate

Mature Stage:
- Majority resolved from cache
- Minimal web research
- Faster responses
- Lower LLM cost

---

## Final Principle

Research gathers facts.
Judgment makes decisions.
Caching builds intelligence.
