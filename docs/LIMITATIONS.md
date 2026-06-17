# Lacuna — Limitations & Credibility

This document exists to prevent misuse. Read it before acting on any Lacuna output. The tool finds signal; it does not find truth.

---

## 1. Deep Corpus Ends September 2023

The primary sentiment source — the McAuley Amazon Reviews 2023 dataset — covers reviews published up to **September 2023**, on **US amazon.com**, in **English only**. This is not a streaming feed; it is a fixed historical snapshot.

Implications:
- Books published after September 2023 have no Amazon corpus reviews in this dataset. Their gaps are invisible to the deep layer.
- Reader sentiment that has shifted since late 2023 is not reflected.
- Non-English-language books, non-US editions, and titles without a US Amazon presence are absent.
- The "fresh" layer (Hardcover) supplements but does not replace the corpus. It is thinner in volume, particularly on niche titles, and unevenly distributed across genres.

Any Lacuna output should be read as "what readers were saying, as of late 2023, about US Amazon books in English" — plus whatever Hardcover adds for more recent signal.

---

## 2. The Fresh Layer (Hardcover) Has Thinner Volume

Hardcover is a smaller platform than Amazon. For popular titles it provides useful fresh signal. For niche or backlist titles it may have single-digit reviews, or none at all.

When a candidate's sentiment comes predominantly or entirely from Hardcover with low review counts, `confidence` will be low and `sample_size` will be small. These fields are in every output. A low-confidence Hardcover-only result is a weak signal, not a finding.

---

## 3. Demand Is a Popularity Proxy, Not Unit Sales

Lacuna has no access to Amazon sales rank (BSR), publisher sell-through data, or any actual sales figures. The demand score is constructed from:
- NYT bestseller presence and weeks (a high bar — most books never appear)
- Google Books ratings counts (a volume proxy)
- Hardcover read counts and review velocity

These are **correlates of reader attention**, not direct measurements of revenue or market size. A book can be intensely discussed without selling in volume. A book can sell in volume without generating review activity. These proxies are informative but imperfect, and they are labeled as such in the export.

Do not treat `demand_score` as a market-size estimate or a sales forecast.

---

## 4. Survivorship Bias — Unwritten Books Leave No Trace

This is the hardest limitation to reason about. The tool can only surface dissatisfaction with books that exist. If a topic is so underserved that no book has been written on it, there are no reviews to mine, no ratings to count, and no clusters to find.

**Thin data can mean two opposite things:**
- The niche is underserved and represents a real opportunity (a true gap).
- The niche has been tried repeatedly, failed to attract readers, and the attempts left little trace (a dead end).

Lacuna cannot distinguish these. Thin data sets `blind_spot = true` on the score. A `blind_spot` flag is an invitation to do additional research — it is not a green light.

---

## 5. Dissatisfaction Is Not Demand

A reader who complains that a book is outdated, too advanced, or badly structured is expressing dissatisfaction with the execution — not necessarily expressing a desire to buy a different version. Some complaints reflect unmet demand for a better book. Others reflect that the reader was the wrong audience, or that the topic is inherently difficult to cover. The tool cannot tell the difference.

The `instructions_to_model` field in the Context Pack is explicit: do not infer demand from dissatisfaction alone; demand must come from the demand fields. This document reinforces that. A cluster of complaints is a hypothesis about what a better book might address, not evidence that readers would buy it.

---

## 6. Per-Book Volume Variance

Review counts vary enormously by title. A popular book might have thousands of reviews in the corpus; an obscure backlist title might have three. HDBSCAN clustering requires a minimum cluster density — below a threshold it cannot form meaningful clusters, and results are unreliable or absent.

The `sample_size` field in every score output reflects the review count available. Scores with `sample_size < 20` (the `min_sample_gate` in `config/advanced.yaml`) are linearly down-weighted in confidence. Scores with very low sample sizes should be treated as directional at best.

---

## 7. Platform Rating-Culture Biases

Amazon and Hardcover have different rating cultures. Amazon reviews historically skew high (average published ratings tend to cluster in the 4–5 range). Hardcover has its own distribution. A 3-star Amazon review and a 3-star Hardcover review are not the same signal.

Lacuna normalizes ratings **per platform** (z-score within platform) before any aggregation. This corrects for mean and variance differences between platforms. It does not correct for self-selection effects (who reviews on each platform), genre biases (some genres over-review on one platform vs. another), or temporal trends in how ratings are distributed. Cross-platform agreement is a credibility signal precisely because these biases differ — when Amazon and Hardcover agree on a complaint cluster, the signal survives two different rating cultures.

---

## 8. Legal Mosaic

### Amazon Customer Reviews Terms of Use

The Amazon review text used in Lacuna comes from the McAuley Amazon Reviews 2023 public research dataset, distributed via Hugging Face. This dataset is made available under the terms of the Amazon Customer Reviews research license. Key constraints:

- **Ship the fetch script; never redistribute the text.** The seed pipeline downloads the corpus at runtime from Hugging Face. Raw review text is never committed to the repository, never included in exports, and never sent to an external API. Only paraphrased cluster labels and summary statistics leave the machine.
- The dataset is licensed for academic and research use. Commercial use requires review against Amazon's current terms.
- Users of Lacuna are responsible for ensuring their use of the derived outputs complies with applicable terms.

### Hardcover Developer Guidelines

Hardcover provides API access under developer guidelines available at hardcover.app. Key constraints:

- Rate limit: **60 requests per minute**. The Hardcover adapter enforces this limit with exponential backoff and jitter on 429 responses.
- Tokens expire yearly. A stale token produces authentication errors, not wrong data — the adapter fails loud.
- Hardcover data (reviews, ratings, read counts) is sourced from the Hardcover platform. Review the current developer guidelines before any production or commercial use.

### Google Books and NYT APIs

Google Books and NYT data are accessed under their respective developer terms. Both require API keys and enforce daily quotas. These quotas are enforced by the adapters (Google Books ≈ 1,000/day; NYT ≈ 4,000/day at ≈10/min). Usage beyond free tiers may require paid plans.

---

## 9. What This Tool Is Not

- It is not a sales forecasting tool.
- It is not a competitive intelligence tool based on real-time data.
- It is not a replacement for talking to readers, agents, or editors.
- It is not a predictor of publishing success.

It is a hypothesis generator over historical and recent reader sentiment, gated by imperfect demand proxies, with explicit confidence and provenance on every output. Treat every candidate as a hypothesis that requires external validation before acting on it.

## 10. Bounded Seed Scan & Corpus-Only Incompleteness

The seed streams the McAuley corpus under a **bounded linear scan** (default 200k meta / 1M review rows). The corpus has no server-side subject filter, so niche targets (e.g. stoicism) surface proportionally fewer works than common ones, and a work's reviews only count if they fall inside the scanned review window. A thin or empty result is a **scan-coverage artifact, not a market signal** — raise `--meta-limit`/`--review-limit` for fuller coverage. Coverage bounds are recorded in `analysis_runs.counts`.

A **corpus-only run** (`lacuna export`/`sweep` with no external keys) carries no demand or supply signals, so those scoring components are *withheld*, not zeroed — every candidate is flagged `incomplete` and its `gap_score` is held back rather than fabricated. This is by design (missing ≠ zero); demand/supply enter once the NYT/Google/Hardcover/Open Library signals are seeded.
