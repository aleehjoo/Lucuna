# Lacuna — Scoring & Aggregation Methodology

This document describes the model that produces the `gap_score` and its associated validity outputs. It is written for a reader who wants to understand the math before trusting a result, or who wants to tune the correctness knobs in `config/advanced.yaml`.

---

## 1. What We Are Measuring

Lacuna estimates how underserved a book niche is. "Underserved" means: readers are paying attention (demand), existing books on the shelf are comparatively scarce or weak (supply scarcity), and reviewers are expressing unresolved dissatisfaction with what exists (unmet need). All three components must co-exist for a gap to be real. The score combines them in a way that reflects that logic.

The output is a **hypothesis**, not a finding. Confidence is explicit on every score, and every result carries provenance.

---

## 2. Raw Component Derivation

Before normalization, the three components are derived as follows:

- **`demand`** — drawn from `demand_signals`: bestseller weeks (NYT), ratings counts (Google Books), read counts and review velocity (Hardcover). These are combined per BISAC bucket into a single unnormalized demand index.
- **`supply_scarcity`** — the inverse of supply volume: `supply_scarcity` is high when `supply_signals.title_count` (from Open Library / Google Books) is low relative to the cohort. A saturated shelf produces low supply scarcity.
- **`unmet_need`** — derived from the aspect clusters: `sum(reviewer_count * helpful_weight)` over a candidate's clusters. This rewards complaints that many distinct reviewers raised and that others found helpful — it penalizes lonely one-off gripes.

These values are tunable at the source: the target BISAC, subject filter, and recency window in `config/default.yaml` determine which data enters the computation.

---

## 3. Rank/Percentile Normalization

Each component — `demand`, `supply_scarcity`, and `unmet_need` — is normalized to **[0, 1]** using **rank/percentile normalization** computed within the cohort (all candidates in a project run).

```
normalized(x) = rank(x) / (N - 1)    # 0 = lowest, 1 = highest in cohort
```

This is deliberately **outlier-robust**: a single mega-bestseller with 500k ratings cannot compress every other title toward zero the way a min-max stretch would. The normalization is **cohort-level** — values are meaningless across different project runs or niche targets; only within-run comparisons are valid.

**Edge case — n = 1:** when a cohort contains exactly one candidate, rank normalization is undefined. In this case, each component is set to **0.5** (neutral) and `confidence` is penalized accordingly. This prevents a single title from appearing spuriously perfect or broken.

---

## 4. Missing ≠ Zero Rule

This is the most important invariant in the scoring model. A failed or absent data layer must **never** be treated as a zero. The distinction is between *absent data* and *genuinely low values*.

Applied before any multiplication:

| Situation | Treatment |
|---|---|
| **`demand` absent** (fetch failed, no signal at all) | **Withhold** the score entirely. Set `gap_score = null`, `incomplete = true`. Demand is the gate; a score without it is not meaningful. |
| **`supply_scarcity` absent** | **Impute** to the BISAC/category median. Apply a confidence penalty. Set `incomplete = true`. |
| **`unmet_need` absent** | **Impute** to the BISAC/category median. Apply a confidence penalty. Set `incomplete = true`. |
| **Genuine zero** (e.g. a truly saturated shelf → `supply_scarcity = 0`) | **Propagate** as-is. A real zero is a real result. |

Imputation uses the median of the same BISAC cohort, not a global constant, to preserve relative scale within the niche.

---

## 5. Soft Demand Gate

Demand gates the score, but it does so **softly** — a low-demand niche appears in results, flagged, rather than being erased.

```
demand_gate = max(epsilon, sigmoid(k * (demand - d0)))
```

Parameters (from `config/advanced.yaml`):

| Parameter | Value | Meaning |
|---|---|---|
| `epsilon` (`demand_gate_floor_epsilon`) | 0.05 | Minimum gate value — no niche scores absolute zero |
| `k` (`demand_gate_steepness_k`) | 8 | Sigmoid steepness — controls how sharply demand gates the score |
| `d0` (`demand_gate_midpoint_d0`) | 0.4 | Midpoint — demand below 0.4 (normalized) is substantially dampened |

At `demand = 0`: `demand_gate ≈ epsilon = 0.05`. At `demand = 1`: `demand_gate ≈ 1.0`. The gate is a continuous curve, not a binary threshold — this is intentional. A near-zero demand niche should score near-zero; it should not score exactly zero and disappear from the output.

---

## 6. Weighted Geometric Mean Core

The core gap signal combines `supply_scarcity` and `unmet_need` via a **weighted geometric mean**:

```
core = (supply_scarcity^w_s * unmet_need^w_u)^(1 / (w_s + w_u))
```

Parameters (from `config/advanced.yaml`):

| Parameter | Value |
|---|---|
| `w_s` (`geomean_weight_supply`) | 1.0 |
| `w_u` (`geomean_weight_unmet`) | 1.0 |

With equal weights this simplifies to the geometric mean: `core = sqrt(supply_scarcity * unmet_need)`.

**Why geometric mean, not arithmetic?** The arithmetic mean lets a strong signal on one axis rescue a weak one on the other. A niche with enormous unmet complaints but a fully saturated shelf is not a good opportunity — the geometric mean penalizes that asymmetry while still keeping a weak-but-real signal from fully cancelling a strong one. It goes to zero only on a genuine zero (handled by the missing≠zero rule in §4).

---

## 7. Final Composition

```
gap_score = core * demand_gate
```

Both `core` and `demand_gate` are in [0, 1], so `gap_score` is in [0, 1]. Higher means more underserved. The score is stored in `scores.gap_score` and exported verbatim; it is not rescaled after composition.

---

## 8. Time-Skew Guard

A gap that was real eighteen months ago may be closing today. If post-2023 title counts show a rush of new supply:

```
if (recent_title_count / title_count) > recent_supply_surge_threshold:
    recent_supply_surge = true
    gap_score = gap_score * recent_supply_surge_downweight
```

Parameters (from `config/advanced.yaml`):

| Parameter | Value | Meaning |
|---|---|---|
| `recent_supply_surge_threshold` | 0.30 | More than 30% of all titles published post-corpus-cutoff signals a surge |
| `recent_supply_surge_downweight` | 0.70 | Multiply gap_score by 0.7 when the flag is set |

`recent_supply_surge = true` is always surfaced in the validity outputs and the export — the user can see when a result has been downweighted and why.

---

## 9. Confidence Formula

```
confidence = clamp01(
    min(1, sample_size / min_sample_gate)
    * (0.7 ** imputed_layer_count)
    * (0.85 if single_platform else 1.0)
    * crosswalk_conf
)
```

Where:

| Term | Meaning |
|---|---|
| `min(1, sample_size / min_sample_gate)` | Linear ramp from 0 to 1 up to `min_sample_gate` reviews; flat at 1 above it |
| `min_sample_gate` | 20 (from `config/advanced.yaml`) |
| `0.7 ** imputed_layer_count` | Each imputed layer (supply_scarcity or unmet_need) multiplies confidence by 0.7 |
| `0.85 if single_platform` | Single-platform signal is inherently less trustworthy |
| `crosswalk_conf` | Confidence of the BISAC crosswalk mapping for this candidate (from `taxonomy_crosswalk.confidence`) |
| `clamp01` | Hard clamp to [0, 1] |

Confidence is **always written** to the `scores` table and always present in the export. It is a primary sort criterion for the export instructions to the user's LLM.

---

## 10. Cross-Platform Aggregation

The two sentiment text sources — the Amazon corpus (deep historical) and Hardcover (fresh live) — are kept on separate tracks until the aggregation step.

**Step 1 — Per-platform rating normalization (mandatory, before any merge):**
Ratings are z-scored within each platform independently. Amazon and Hardcover have different rating cultures — Amazon skews high, Hardcover skews differently — so a naive average of raw ratings is explicitly disallowed and would produce silently wrong results. Normalization happens in `lacuna/aggregation/cross_platform.py` before any values cross platform boundaries.

**Step 2 — Cluster merge by embedding similarity:**
Aspect clusters from both platforms are merged when their label embeddings exceed a cosine similarity threshold:

```
merge if cosine(embed(cluster_a.label), embed(cluster_b.label)) >= cluster_merge_similarity
```

`cluster_merge_similarity = 0.75` (from `config/advanced.yaml`). Clusters below this threshold remain platform-specific and are labeled as such in the output.

**Step 3 — Cross-platform agreement as credibility signal:**
When a cluster merges across platforms, `cross_platform = true` is set and both platform names are recorded in `aspect_clusters.platforms`. The **`cross_platform_agreement_pct`** — the share of a candidate's top complaints confirmed on more than one platform — is computed and included in the export provenance block. Higher agreement raises confidence. A single-platform complaint is retained but its confidence contribution is multiplied by 0.85 (the single-platform penalty above).

---

## 11. Approved Build-Time Assumptions (Gaps the PRD Left Open)

The PRD specified the architecture and the invariants but left some specific values as implementation decisions. The following were resolved during the build and are documented here because they are load-bearing for reproducibility. All are tunable in `config/advanced.yaml`; changing them changes results.

| Assumption | Value in `advanced.yaml` | Notes |
|---|---|---|
| Recent supply surge threshold | `recent_supply_surge_threshold = 0.30` | Trigger when >30% of shelf titles are post-cutoff |
| Recent supply surge downweight | `recent_supply_surge_downweight = 0.70` | Multiply gap_score by 0.7 on trigger |
| Cluster merge similarity | `cluster_merge_similarity = 0.75` | Cosine threshold for cross-platform aspect cluster merging |
| Confidence formula | See §9 above | Linear sample ramp × 0.7-per-imputed-layer × 0.85-single-platform × crosswalk_conf |
| Works trigram tie-break threshold | `works_trigram_threshold = 0.6` | Min Jaccard trigram similarity to merge same-author editions in works grouping (§6.3 of PRD) |
| Crosswalk auto-reject threshold | `crosswalk_auto_reject = 0.55` | BISAC cosine below 0.55 → auto-reject; range [0.55, 0.85) enters the unmapped queue |
| Raw component derivation | demand from `demand_signals` aggregated per BISAC; `supply_scarcity = inverse of supply_signals.title_count`; `unmet_need = sum(reviewer_count * helpful_weight)` over a candidate's clusters | See §2 above |

---

## 12. NLP Stack and Local Boundary

All bulk text processing is local and free. No raw review text is sent to any external LLM API at any point in the pipeline.

- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU), pinned revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- **Zero-shot aspect labeling:** `facebook/bart-large-mnli`, pinned revision `d7645e127eaf1aefc7862fd59a17a5aa8558b8ce`.
- **Clustering:** HDBSCAN in cosine space via `hdbscan` + `scikit-learn`.

The optional Anthropic API call (for a narrative draft in the export) receives only the already-aggregated cluster labels and summary statistics — never raw review text. The export is fully functional with `ANTHROPIC_API_KEY` unset, at $0 runtime cost.

Revision hashes are dynamically resolved, validated, and written to `config/advanced.yaml` at build time by `scripts/pin_revisions.py`. A build fails loudly if any revision cannot be verified.

---

## 13. Hardcover API Resolution (Discovered at Build Time)

The PRD assumed a straightforward title→reviews lookup against Hardcover. The live API (a Hasura/GraphQL front end, confirmed 2026-06-17 against the G0 gate) differs in two ways that forced the adapter's shape:

1. **`_ilike` is blocked server-side** ("ilike and related operations are not permitted on this server"). Fuzzy title matching by SQL operator is impossible. Bare-title `_eq` is permitted but only matches empty *edition stubs* (0 reads/ratings), not the canonical work. **Resolution:** title→id goes through Hardcover's Typesense-backed `search(query, query_type:"Book")` query; the adapter picks the hit with the highest `users_read_count` as canonical.
2. **There is no `reviews` relationship on `books`.** Live reviews live in the **`user_books`** table (`where: {book_id:{_eq:$id}, has_review:{_eq:true}}`), where the review text is the `review_raw` column and the date is `reviewed_at`. `HardcoverReview.from_user_book()` maps that shape onto our model.

The G0 gate passes against this path: sample title "Atomic Habits" resolves to the canonical edition (3,125 readers) and returns 50 live reviews. This is a request-shape adaptation only — the architecture (Hardcover as the fresh live-sentiment platform, kept on a separate track until cross-platform aggregation) is unchanged.

## 14. Corpus Loading & Seed Integration (Discovered/Decided at Build Time)

**Corpus loading — `datasets` 5.x dropped dataset scripts.** `load_dataset("McAuley-Lab/Amazon-Reviews-2023", "raw_review_Books", …)` now raises `RuntimeError: Dataset scripts are no longer supported, but found Amazon-Reviews-2023.py` — the repo ships a loading *script* the current library refuses to execute. **Resolution:** `lacuna/adapters/corpus.py` streams the underlying raw JSONL files directly from the Hub via `HfFileSystem` at the **pinned revision** (`raw/review_categories/Books.jsonl`, `raw/meta_categories/meta_Books.jsonl`), parsing one line at a time so memory stays flat over the multi-GB file. Same data, no script, revision pinning (PRD §15) preserved.

**Seed integration (`run_seed` / `build_seed_plan`) — approved defaults.** The seed was the PRD-deferred integration entrypoint; it is now implemented as a pure `build_seed_plan` (offline-tested) + async `persist_seed_plan`.
- **Bounded scan.** The McAuley corpus is only linearly scannable when streamed, so a first seed is bounded: `meta_limit=200_000`, `review_limit=1_000_000`, `max_works=60` (all CLI-overridable). Niche subjects (e.g. stoicism) yield proportionally fewer matches under a bounded scan; raise the limits for fuller coverage. Bounds are logged in `analysis_runs.counts`.
- **Subject filter.** Works are matched by case-insensitive keyword (`subject_filter.keywords`) over the Amazon title + categories + description. Amazon category strings are *not* BISAC; canonical BISAC mapping is the taxonomy crosswalk's job (Workstream E), so the seed uses keyword matching as the practical first-pass filter.
- **Editions keyed by `parent_asin`.** `raw_meta_Books` rows are per-product (keyed by `parent_asin`, no `asin`), so each meta row becomes one edition with `asin := parent_asin`; the 3-pass grouping then merges editions of the same work across parents by normalized title+author. Reviews join back by `parent_asin`.
- **Sentiment proxy.** With no text leaving the machine, per-review sentiment is a documented rating proxy: `clamp((rating − 3) / 2, −1, 1)` (1★→−1, 3★→0, 5★→+1).
- **`--rebuild` only.** A full recompute deletes the project's works (FK `ON DELETE CASCADE` clears editions/reviews/clusters) and reinserts; `--reconcile` raises `NotImplementedError` (PRD §6.4).

**$0 corpus-only distill→score→export.** `lacuna export` / `lacuna sweep` read the seeded works+clusters, score the cohort (F), fuse clusters (G), and emit the Context Pack (H) with `ANTHROPIC_API_KEY` unset and no external keys. In this path the demand/supply signals (NYT/Google/Hardcover/OpenLibrary) are absent, so those scoring components are correctly **withheld** and candidates are flagged `incomplete` — the honest state until those signals are seeded. The fresh single-title path (`lacuna analyze`) needs a live Hardcover token and is wired for the post-credentials phase.

**Repository hygiene.** `.env.example` was committed with real API keys and has been purged from all git history (`git-filter-repo`); it is now an untracked, local-only placeholder, and `.env` + `.env.example` are both git-ignored. The exposed Hardcover/Google Books/NYT keys were rotated.

## 15. Seed Selection by Clusterable Critical Mass (Documented §6.5 Deviation)

The seed clusters **only critical reviews** (rating ≤ 3) per work, but work selection originally ranked by **total** review count (all ratings). The two sets diverge sharply: a work with 60 total reviews may carry only 2 critical ones, and the §6.5 long-tail floor deliberately admitted very-low-volume works (≈1 critical review each). The result was ~1.4 critical reviews per selected work — below HDBSCAN's `min_cluster_size = 2` floor — so the clustering pass produced **zero** aspect clusters: the seed's entire distilled product was empty.

**Fix (`orchestrator.py`, `min_critical_per_work` in `advanced.yaml`, default 5):** selection now ranks works by **critical-review count**, and a work is **ineligible** unless it has at least `min_critical_per_work` critical reviews. Reviews therefore concentrate on works that can actually form a cluster, instead of smearing thinly across many that cannot.

**Deviation from PRD §6.5 (approved, deliberate).** §6.5 instructs the seed to "deliberately include the long tail" of low-review works to keep survivorship bias from re-entering at ingestion. Excluding works below the critical-review floor **narrows** that tail — the very-thinnest works are dropped. The justification: a work with fewer than `min_critical_per_work` critical reviews yields **no cluster at all**, only orphaned HDBSCAN noise, so including it adds nothing to the distilled output while diluting the review budget away from clusterable works. The long-tail floor (`longtail_share`) still operates **within** the eligible (clusterable) band — works in `[min_critical_per_work, min_sample_gate)` are the long tail now — so the §6.5 intent (do not select by popularity alone) is preserved among works that can produce signal. The floor is **never** lowered to manufacture clusters; if too few works qualify, the correct response is to scan more review rows (`--review-limit`), not to admit unclusterable works.
