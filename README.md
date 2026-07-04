# EU-Sovereign Real-Estate Due-Diligence Pipeline

An agentic document pipeline for **cross-border (ES–FR) real-estate transaction due
diligence**: it ingests the messy, multilingual document dump of a property deal
(land-registry extracts, commercial leases, rent rolls, diagnostics), runs
EU-sovereign OCR + schema-driven extraction with **source citations (page +
bounding box + verbatim text span)**, reconciles across documents, applies a
statutory red-flag rules engine (title charges, ILC/ILAT indexation, LAU deposit
minimums, EPC/EPBD trajectories) and produces an **audit-ready DD report** where
every conclusion links back to the exact source clause — logged in an immutable,
hash-chained audit trail engineered to **EU AI Act Article 12/26** standards.

```
[Upload / data-room ZIP]
  → Ingestion (SHA-256 dedup, MIME sniff)         → object storage + Postgres
  → OCR (Mistral OCR 4 | offline pdfplumber)      → markdown + blocks + bboxes + confidence
  → Classification (schema registry lookup)
  → Cited extraction (guided JSON, per-field provenance, abstention over hallucination)
  → Cross-document reconciliation (rent roll ↔ lease ↔ title ↔ surfaces)
  → Red-flag rules engine (deterministic statutory rules + EPC/EPBD tables)
  → Cited DD report (HTML / PDF / DOCX) + split-screen human review UI
  → Append-only hash-chained audit log at every step
```

## Quickstart (offline — zero API keys, zero external services)

```bash
make setup        # venv + backend install
make test         # 15 backend tests
make eval         # gold-set eval harness (P/R/F1 + citation accuracy, CI-gating)
make seed         # end-to-end synthetic demo deal → 14 findings, verifiable audit chain
make api          # FastAPI on :8000 (starts in-process queue worker)
make web          # React UI on :5173  (separate terminal)
```

Open http://localhost:5173 — the seeded *Iberia-Occitanie Portfolio* deal shows the
full flow: deal dashboard → findings with citations → split-screen review (click a
field, the PDF scrolls and highlights the source clause) → report export.

Docker (Postgres + MinIO + API + worker + web): `make docker-up` → UI at :8080.

## Provider modes — sovereignty as a config change

The model layer is abstracted behind one interface (`api/app/providers/base.py`),
so switching deployment mode is `DD_PROVIDER=` in `.env`, not a rewrite:

| Mode | OCR | Extraction | When |
|---|---|---|---|
| `local` (default) | pdfplumber (digital-text PDFs, real line bboxes) | deterministic label-anchored extraction | dev, demos, CI, eval |
| `mistral` | Mistral OCR 4 (`/v1/ocr`, blocks + confidence, pixel→point normalised) | Mistral Large 3 guided-JSON with mandatory per-field `text_span` provenance | POC/design partners — **La Plateforme: EU data residency by default, Zero Data Retention, DPA; not subject to the US CLOUD Act** |
| self-host (phase 3) | Mistral OCR container | vLLM + xgrammar guided decoding on Scaleway GPU (Paris) | when a design partner contractually requires in-tenant processing — the `MistralProvider` uses raw HTTP request shapes that point at a vLLM endpoint by changing `base_url` |

## Repository layout

```
packages/schemas/   Schema registry (core IP): doc-type field definitions with
                    multilingual label anchors, classification keywords, and the
                    EPC/EPBD rule tables (FR DPE ban calendar, ES CEE validity,
                    configurable EPBD MEPS thresholds with 'pending' status)
api/app/
  providers/        local + mistral providers behind one Protocol; citation
                    recovery (fuzzy span→block matching)
  services/         ingestion, pipeline (idempotent stage DAG), reconciliation,
                    red flags, report generator, durable job queue
  routers/          deals, documents, findings (review w/ mandatory reason),
                    reports, audit (chain verification endpoint)
  audit.py          hash-chained append-only audit log (Art. 12/26)
web/                React + TS: deal dashboard, split-screen review with
                    react-pdf + bbox overlay, finding cards, report links
scripts/            synthetic document generator (gold truth) + demo seed
eval/               eval harness: per-doc-type precision/recall/F1, citation
                    accuracy, abstention correctness; fails CI on regression
workers/            standalone queue worker process
infra/              docker-compose (Postgres 16 + MinIO + api + worker + web)
```

## Registered document types (Phase 2 priority set)

1. **Nota simple registral (ES)** — registry IDs, description, titularidad, cargas,
   notas marginales. Red flags: subsisting charges (hipoteca/embargo/afección),
   titleholder ≠ landlord, extract older than 3 months, VPO regimes.
2. **Contrato de arrendamiento LAU (ES)** — parties, rent, indexation, fianza vs
   the LAU art. 36 two-month minimum, break clauses, IBI allocation.
3. **Bail commercial 3/6/9 (FR)** — ILC/ILAT vs **ICC (void-clause risk since loi
   Pinel)**, Pinel L.145-40-2 charge inventory, 9-year minimum, triennial breaks,
   mandatory diagnostics (ERP/DPE/amiante), DPE class → EPC rules.
4. **Rent roll / tenancy schedule** — per-unit rows + WAULT/occupancy totals;
   arrears and vacancy flags; the anchor for cross-document reconciliation.

Cross-document rules: rent-roll rent ↔ lease rent (2% tolerance), titleholder ↔
landlord (fuzzy identity match, jurisdiction-scoped, catastral-ref paired),
surfaces (10% divergence), break dates. Unknown/exotic documents are **abstained
and routed to human review — never guessed** (tiered-confidence design).

## Proof of Oversight (anti-automation-bias UX)

Disclaimers ("please verify AI output") don't change behavior — automation
complacency is the most-replicated failure mode in human-factors research, and
EU AI Act Art. 14(4)(b) explicitly requires guarding against it. This platform
engineers vigilance instead of requesting it:

- **Verification is one click** — every field/finding highlights its exact
  source clause (checking must be cheaper than trusting).
- **Absence has a UI** — abstained fields say "I don't know" instead of guessing.
- **Spot-checks** — the system deterministically samples its own
  *high-confidence* extractions (the answers nobody would re-check) and asks
  the reviewer to verify them against the highlighted source; a mismatch
  auto-escalates to a high-severity finding, and the per-deal agreement rate
  becomes a measured oversight metric.
- **The artifact carries the oversight state** — reports export stamped
  **DRAFT — n findings await human review** (page 1 + every footer) until every
  finding is adjudicated and spot-checks are done; then they export
  **HUMAN-REVIEWED** with named reviewers and the agreement rate. Social
  accountability, not warnings.
- **Human oversight record** — a report section auditors can read: findings
  adjudicated, spot-check agreement, reviewers, status.

## Compliance engineering (the sales moat)

This DD use case is very likely **not** Annex III high-risk (professional
analytical tool, not credit scoring of natural persons) — but the platform is
engineered to high-risk logging standards anyway as a differentiator for
regulated buyers (DORA-covered financial entities, funds, notaries):

- **Article 12** — every OCR run, LLM call, classification, extraction, human
  review and export writes an `audit_events` row with model + prompt versions,
  input/output refs and a **SHA-256 hash chain** (`hash = SHA-256(prev_hash ‖
  canonical(payload))`). `GET /api/audit/verify` re-walks and re-hashes the whole
  chain; tampering with any historical event is detectable (tested).
- **Article 26(6)** — log retention is configurable with a hard-coded
  **6-month floor** (`AUDIT_LOG_RETENTION_DAYS`, values below 183 are ignored).
- **Article 14 human oversight** — accepting/overriding a finding requires a
  **mandatory reason + actor**, written to both the finding and the audit chain.
- Reports end with an audit annex (model versions, prompt versions, overrides).

## Eval methodology

`make eval` runs the local provider against a synthetic gold set (template-built
PDFs with known ground truth — no client PII) and reports, per doc type:
field-level **precision / recall / F1**, **citation accuracy** (does the cited
block actually contain the span), **abstention correctness** (fields the gold set
requires the extractor to refuse) and classification accuracy. CI fails below
F1 ≥ 0.90 / citation ≥ 0.95. Extend the gold set with real (anonymised) documents
per doc type as design partners come on board; freeze it and re-run on every
prompt/model version bump.

## Deliberate deviations from the v1.0 spec (and why)

- **Job queue**: a small Postgres/SQLite-backed durable queue (`services/jobs.py`)
  instead of Hatchet — same required semantics (durability across restarts,
  exponential-backoff retries, dead-letter queue, fan-out/fan-in barrier) with
  zero extra infrastructure for a solo-founder POC. Swap-in point is documented
  in the class docstring.
- **Agent orchestration**: the per-document flow is an explicit **idempotent
  stage DAG** checkpointed in `stage_runs`, keyed by `(document_id, stage,
  model_version, prompt_version)` exactly as specced — re-runs are cached,
  version bumps re-run. LangGraph adds value once branching agentic loops
  (self-check/verifier passes) land; the checkpoint keys are already compatible.
- **UUIDs as 36-char strings / JSON columns** — identical model runs on Postgres
  and SQLite (zero-infra dev + CI).
- **fpdf2 + pdfplumber synthetic fixtures** — the offline provider makes the full
  pipeline (including citations and bbox highlights) genuinely testable in CI
  without any model calls; that is also the regression bed for prompt changes.

## Roadmap to the spec's remaining phases

- **Schema expansion** (spec §3.1): escritura, CEE, IBI, catastro (ES); acte de
  vente, état hypothécaire, DPE, diagnostics, KBIS (FR) — add a `DocSchema` per
  type; classification/extraction/eval pick it up automatically.
- **Mistral phase hardening**: batch OCR, self-consistency sampling (N=3–5) on
  low-confidence fields, verifier pass on red-flag findings.
- **DPA/ZDR**: enable Zero Data Retention on the Mistral org and sign the DPA
  before processing any real client document.
- **Report parity**: install `api[reports]` extras (WeasyPrint/python-docx) or use
  the Docker image (deps included) for PDF/DOCX export.
- ~~AuthN/Z~~: **done** — accounts (salted PBKDF2-SHA256, httpOnly session
  cookies) and GitHub-style per-deal collaboration: deals have members with
  roles (owner / editor / reviewer / viewer), every route is access-scoped,
  review + spot-check identity comes from the session (never typed), and
  granting/revoking access is itself a hash-chained audit event. Legacy deals
  with no members are claimed (audited) by the first user to open them.
  **Still needed before a real pilot**: TLS everywhere (set the session
  cookie's `secure` flag), email verification, rate limiting on login,
  SSO/2FA for enterprise buyers.
