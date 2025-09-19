# Context Layer Protocol (CLP)

Here’s a single, self-contained doc you can hand to other AIs (and humans) to understand and iterate on the vision. It’s concise, normative where helpful, and includes concrete data shapes.

# Context Layer Protocol (CLP) — Overview & Starter Spec v0.2

## 0) Purpose

Build a **context-aware data layer** that returns answers **with their limits and causes attached**. CLP treats context, provenance, resolution limits, and policy as first-class. It is **format-agnostic** (works with PDFs, DOCX, Markdown) and **database-agnostic** (works with SQLite/Postgres + vector/graph indices).

## 1) Problem (why this exists)

- **Context loss**: data travels; meaning doesn’t.
- **Over-precision**: systems claim distinctions beyond evidence (no resolution guardrails).
- **Opaque power**: policies/roles curve outputs invisibly.
- **Human bandwidth**: explanations must fit attention budgets.

## 2) Four-Axis Design Lens

- **Resources** (constraint): compute, storage, time.
- **Cognition** (constraint): human/model attention & verification capacity.
- **Context** (field condition): frames, lineage, semantics that create coherence.
- **Power** (curvature/gradient): policies/roles/incentives that bend outcomes.

CLP encodes all four across data, queries, planning, and governance.

---

## 3) Core Object: ContextBundle (CB)

Portable unit coupling **content** with **frame**, **lineage**, **policy**, **semantics**, **resolution limits**, and **explain**.

**Minimal JSON (canonical form)**

```json
{
  "id": "urn:cb:ulid",
  "version": "1.0",
  "frame": "domain.subdomain",               // e.g. "news.report", "finance.invoice"
  "content": {},                              // typed payload or reference
  "lineage": {
    "origin": {"uri": "s3://...|file://...|http://...", "ts": "2025-09-18T00:00:00Z"},
    "parents": ["urn:cb:..."],                // if derived
    "transforms": [{"fn":"ocr@sha256:...", "ts":"..."}]
  },
  "policy": {
    "read": [{"roles":["auditor"], "conds":["pii:masked"]}],
    "write": [{"roles":["etl.bot"]}],
    "purpose": ["verify","reconcile"],
    "expiry": null
  },
  "semantics": {
    "keywords": ["invoice","shipment"],
    "embedding": {"model":"text-embedding", "handle":"vector://index/123"}
  },
  "resolution": { "min_separation": 0.20, "min_support": 3, "confidence": 0.90 },
  "explain": { "reason": "symbolic+vector+lineage", "unresolved": false },
  "refs": { "content_hash":"sha256:...", "content_ref":"s3|file|http URI" }
}

```

**Frames (namespacing & validation)**

```yaml
# Frame Registry unit
name: finance.invoice
version: 1.2
required_fields: [invoice_id, amount, currency, issued_at, vendor_name]
validators:
  - field: currency
    rule: one_of
    args: ["USD","EUR","GBP"]
defaults:
  resolution: { min_separation: 0.20, min_support: 25, confidence: 0.90 }
  policy.read: [{ roles: ["finance.ap","auditor"] }]

```

---

## 4) Storage Model (where things “live”)

### A) With/Near the File (portable)

- **Sidecar** (recommended): `mydoc.ormd.json` next to any payload (PDF/DOCX/MD).
- Holds the CB subset needed to open/understand offline: `id`, `frame`, `refs.content_hash`, short `lineage.origin`, `semantics.keywords`, optional `embedding.handle`.

### B) Registries (shared receipts; auditable)

Small **append-only** stores for slow-moving, verifiable metadata:

1. **Lineage Ledger** — signed events about bundles (created, transformed, derivedFrom, linkedTo, attestedBy, redacted).
2. **Frame Registry** — versioned frame definitions & validators.
3. **Policy/Trust Registry** — public keys, grants/roles, revocations.
4. **Resolver** — maps bundle IDs/hashes → candidate URIs.

> Registries are not data lakes. They hold hashes, pointers, events, and signatures. Content stays in files/stores you control. Registries can be local, team-scoped, or mirrored publicly; they federate by syncing events (no blockchain, no consensus).
> 

**Lineage Event (JSONL schema)**

```json
{
  "event_id": "ulid",
  "type": "created|transformed|derivedFrom|linkedTo|attestedBy|redacted",
  "object": "urn:cb:ulid",          // bundle id or content hash urn:sha256:...
  "refs": ["urn:cb:parent", "urn:cb:claim"],  // depends on type
  "by": "did:key:z6Mk...",          // signer
  "at": "2025-09-18T20:21:00Z",
  "payload": { "fn":"ocr@sha256:...", "note":"ocr→ner" },
  "sig": "base64-ed25519"
}

```

### C) Index Fabric (fast but disposable)

- **Relational** (SQLite/Postgres) for CB projections.
- **Vector** index for semantic recall (Annoy/FAISS/pgvector).
- **Graph** edges for lineage & `supports|refutes|derives`.

Indexes rebuild from files + registry when needed.

---

## 5) Query Model (Intention-Aware)

Requests declare **intent**, **frame scope**, **resolution limits**, and **attention budget**. Response returns **rows + EXPLAIN + telemetry**.

**Request**

```json
{
  "intent": "verify event claims",
  "frame": ["news.report","claim"],
  "filters": {"keyword":"earthquake","date_gte":"2025-09-01"},
  "resolution": {"min_support":3, "confidence":0.95},
  "attention_budget": "low",               // "low" | "medium" | "high"
  "evidence": ["symbolic","vector","lineage"],
  "policy_view": "effective"               // "effective" | "raw" (admin)
}

```

**Response**

```json
{
  "rows": [ { "id":"urn:cb:...", "frame":"claim", "content":{...} } ],
  "explain": [
    {
      "row_id":"urn:cb:...",
      "why":["filter.frame","filter.keyword","vector.k=50","supports.depth=1"],
      "evidence":{"support_count":3,"diversity":2,"vector_score":0.88},
      "policy":[{"rule":"pii:mask","effect":"applied"}],
      "resolution_status":"met"
    }
  ],
  "telemetry": {
    "coherence_score": 0.82,
    "unresolved_clusters": [ { "key":"urn:cb:...", "reason":"support<3 (1)" } ],
    "redaction_rate": 0.22,
    "power_curvature": {
      "dominant_policies": ["pii:mask","role:auditor"],
      "centralization_index": 0.61
    },
    "attention_used_ms": 150
  }
}

```

---

## 6) Broker Behavior (normative)

The **Context Broker** composes sub-plans across SQL + vector + graph and enforces guardrails:

1. **Resolution floors** (Rayleigh/CFAR):
    
    If `min_support`/`min_separation` unmet → **do not guess**. Return **unresolved** clusters or degrade to coarser bins; annotate `resolution_status`.
    
2. **Policy membranes** (least-privilege):
    
    Apply row/field redaction. Emit **explainable denial** entries without leaking protected content.
    
3. **Exploration floor** (resilience):
    
    Maintain 5–10% exploratory recall to avoid brittle certainty; tag exploratory steps in `explain.why`.
    
4. **Attention budget**:
    
    Bound EXPLAIN verbosity and trace depth (“low” ≤ 2–3 lines per row).
    
5. **Coherence scoring (operational, not truth)**:
    
    Combine agreement across evidence channels; expose score and inputs.
    

**Deployment modes**

- Library (direct function call from scripts/tests).
- Local agent (HTTP endpoints for desktop/VS Code viewer).
- Team service (shared queries/telemetry). All read the same files/registries.

---

## 7) Sidecar Format (portable, editor-friendly)

- **`.ormd.json`** (recommended alongside any payload)

```json
{
  "id":"urn:cb:ulid",
  "frame":"news.article",
  "refs":{"content_hash":"sha256:...", "content_ref":"file://...|http://..."},
  "semantics":{"keywords":["quake","cityX"], "embedding":{"handle":"vector://..."}},
  "lineage":{"origin":{"uri":"http://...", "ts":"..."}}  // short form
}

```

Editors update the payload; a CLI or watcher updates the sidecar and writes **events** to the Lineage Ledger.

---

## 8) Registries (APIs & layout)

**File layout (local project)**

```
my-workspace/
  .clp/
    lineage.log.jsonl      # append-only events (signed)
    frames/                # YAML frame defs (versioned)
    resolver.json          # id/hash -> URIs
    keys/                  # your public keys

```

**Tiny Registry APIs (FastAPI/Flask)**

- `POST /events` (append; verify signature)
- `GET /events?object=urn:cb:...`
- `GET /events?since=ulid` (sync/mirror)
- `GET /frames` / `GET /frames/{name}@{ver}`
- `GET /resolve/{bundle_id}` → `[{"uri":"..."}]`

**Sync**

- Pull-based. Deduplicate by `(event_id, sig)`. Publish only non-sensitive fields; keep payload private.

---

## 9) UI/UX Primitives (beyond terminal)

- **Bundle Cards**: frame pill, key fields, **2-line EXPLAIN**; expand to full trace.
- **Unresolved Tray**: items below resolution floors with reasons (e.g., `support<3`).
- **Query Composer**: intent, frames, filters; sliders for resolution & attention.
- **Bundle Inspector**: sidecar & payload preview, lineage graph, relations, signatures.
- **Telemetry Panel**: coherence trend, unresolved %, redaction rate, power-curvature.

(Desktop via Tauri + local agent; or small web app via FastAPI + HTMX/React. No Docker required.)

---

## 10) Implementation Path (no-Docker, staged)

### Milestone A — CLP-Mini (1–2 weeks)

- **SQLite** for CB tables; **Annoy/FAISS** for vectors; simple graph via tables.
- **CLI**: `record`, `attest`, `link`, `query`.
- **Examples**: 6 bundles (1 claim, 3 supports, 1 refute, 1 thin).
- **Broker**: frame-scoped search, min_support check, EXPLAIN, unresolved.

### Milestone B — Registries (1–2 weeks)

- `.clp/lineage.log.jsonl` + signing (ed25519).
- Tiny Registry API (append/get/since/frames/resolve).
- Broker includes event ids & frame version in EXPLAIN.

### Milestone C — Policy & Review (2–3 weeks)

- Field redaction for one frame (e.g., PII mask). EXPLAINable denial.
- “Unresolved Review” queue; decisions update thresholds.

(Upgrade to Postgres + pgvector + RLS when multi-user concurrency and policy at scale are needed.)

---

## 11) Acceptance Tests (copyable)

1. **Frame scoping**: queries never return objects outside requested frames.
2. **Resolution enforcement**: `min_support` unmet → item appears in `unresolved_clusters`, not `rows`.
3. **Explain determinism**: same data/query → same ordered `why` steps.
4. **Attention budget**: `"low"` → ≤ 3 explain lines per row.
5. **Diversity**: multiple supports from *same* domain count as 1 (prevent echo chambers).
6. **Provenance surface**: each row EXPLAIN cites event ids and frame version used.

---

## 12) Non-Goals

- No blockchain/consensus/tokens.
- No universal truth adjudication.
- No global ontology requirement.
- No ultra-low-latency trading paths (use a fast path without EXPLAIN if needed).

---

## 13) Glossary

- **Frame**: named domain lens that defines what “context” means (schema + defaults).
- **ContextBundle (CB)**: content + context (lineage, policy, semantics, resolution, explain).
- **Registry**: signed, append-only receipts for lineage/frames/policies; small and auditable.
- **Index Fabric**: SQL + vector + graph built from files/registries for fast query.
- **Broker**: planner that enforces resolution/policy and returns EXPLAIN + telemetry.
- **Unresolved**: an honest “we don’t know yet” result state (feature, not bug).

---

## 14) Two Ready-to-Run Examples

**A) Verify an event claim**

```json
{
  "intent":"verify event claims",
  "frame":["news.report","claim"],
  "filters":{"keyword":"earthquake"},
  "resolution":{"min_support":3,"confidence":0.95},
  "attention_budget":"low",
  "evidence":["lineage","vector","symbolic"]
}

```

*Expected*: one claim row with ≥3 independent supports; casualty detail flagged in `unresolved_clusters` if support<3.

**B) Reconcile shipments ↔ invoices (toy)**

```json
{
  "intent":"reconcile invoices to shipments",
  "frame":["finance.invoice","ops.shipment"],
  "filters":{"date_gte":"2025-08-01"},
  "resolution":{"min_separation":0.20,"min_support":25,"confidence":0.90},
  "attention_budget":"low"
}

```

*Expected*: matched pairs with EXPLAIN (symbolic join + vector similarity + lineage hop), and unresolved pairs under support/CI thresholds.

---

### Hand-off

This document is sufficient for another AI to:

- implement a minimal broker & registries,
- define 1–2 frames,
- ingest a few ContextBundles (from PDFs/MD via sidecars),
- run the acceptance tests,
- and iterate on coherence/resolution heuristics.

If you want, I can also generate a starter repo layout (folders, stub code, and sample bundles) tailored to your preferred language/runtime.