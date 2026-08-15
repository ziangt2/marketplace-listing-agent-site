# E-commerce Search & Recommendation Platform

> Marketplace keyword retrieval, multi-signal ranking, behavioral recommendation, and reproducible offline experimentation.

This repository combines two implemented systems: a Node.js web application for public-source marketplace keyword intelligence and a Python recommendation benchmark for candidate retrieval and Hybrid ranking. The shared theme is evidence-driven search and recommendation: collect observable signals, distinguish retrieval from ranking, preserve data provenance, and evaluate with leakage-controlled temporal splits.

The systems are related conceptually but not joined by live production data. The offline recommender uses deterministic **synthetic** product metadata modeled after the Marketplace Agent's keyword/category feature schema; live marketplace data is not used in the reported recommendation metrics.

## Highlights

- Expands marketplace queries across public suggestion sources, market/language variants, and intent modifiers, then collects them concurrently with deterministic limits.
- Extracts and deduplicates unigram, phrase, hashtag, and Chinese-character keyword candidates before rule-based category assignment and feature-based ranking.
- Preserves a strict data policy: absent real uploaded measurements, search volume, official heat, GMV, sales, reviews, and growth fields remain blank.
- Retrieves recommendation candidates independently from Collaborative, Content, and Popularity sources before normalized Hybrid ranking.
- Tunes Hybrid configuration on 4,580 inner temporal validation targets and reserves 3,954 later targets as a frozen final test.
- Reconstructs published metrics from paired per-user outcomes and reports bootstrap confidence intervals, McNemar tests, paired randomization tests, and failure analysis.
- Rebuilds the synthetic benchmark, SQL analytics, recommenders, statistical audit, and evidence files with one command.

## Architecture

```text
Marketplace Search / Keyword Intelligence

Marketplace Query
      ↓
Query Expansion (market, language, intent, long tail)
      ↓
Public Suggestions / Public Sources + Uploaded Reports
      ↓
Deduplication → Keyword Extraction → Rule Categories
      ↓
Feature-Based Keyword Ranking
      ↓
CSV / XLSX / Source Audit

Recommendation Benchmark

Synthetic User Events → Temporal Training History
                           ├─ Collaborative Top-100 ─┐
                           ├─ Content Top-100 ───────┼─ Candidate Union
                           └─ Popularity Top-10 ─────┘
                                                      ↓
                                      Per-user Min-Max Normalization
                                                      ↓
                                  Hybrid Score (0.6 / 0.1 / 0.3)
                                                      ↓
                                             Top-K Offline Evaluation
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation boundaries, API flow, provenance, and limitations.

## Marketplace Search & Ranking

The web application supports Amazon- and TikTok Shop-oriented keyword research using accessible public sources and user-uploaded reports. It does **not** represent either marketplace's internal search system.

### Ingestion and query expansion

`api/marketplace-collect.js` builds keyword seeds and modifiers for US, UK, Canada, Australia, Germany, multiple Spanish-language markets, and a US/Spain/Mexico bundle. English, German, and Spanish locale parameters are propagated to public providers; several common product phrases also receive explicit Spanish seed variants. Collection runs with concurrency 8, a 4.5-second fetch timeout, and bounded query counts.

The implemented providers are Bing and Google public search suggestions. Amazon mode can additionally use bounded DuckDuckGo public search results. TikTok Shop mode currently prioritizes public suggestion queries: direct public-page and general-search execution limits are set to zero for reliability, so this project does not claim comprehensive TikTok product-page crawling.

Collected records retain source query, provider, URL, region, language, and source type. Normalized URL/title keys remove duplicates before the frontend converts source text into candidate terms.

### Extraction, categories, and Weight

The browser extracts English-style tokens, 2–4 token phrases, hashtags, and 2–4 character Chinese sequences. Candidates are assigned rule-based roles such as core keyword, audience, material, specification, variant, use case, functional feature, pain point, content scene, hashtag, or uploaded-report term.

Final keyword `Weight` is an internal 1–100 priority score:

- log-scaled observed frequency: up to 45 points;
- source-query coverage: up to 15 points;
- source-type coverage: up to 10 points;
- real uploaded trend heat, when present: up to 15 points;
- category/intent weighting and long-tail specificity: remaining contribution.

Ties use observed count and then lexical order. **Weight is not marketplace search volume, official heat, sales, or demand.** Uploaded trend/volume/growth values affect output only when a real report contains those fields.

### Reports and exports

Users can paste text or upload CSV, TSV, TXT, XLS, and XLSX reports. The server includes a dependency-free XLSX ZIP/XML reader and writer. Exports include the keyword template, summary, agent analysis, and a real-trend sheet; CSV and plain-text source audits are also available.

## Personalized Recommendation

The RecSys module generates a seeded implicit-feedback event stream with views, clicks, add-to-carts, and purchases weighted 1, 2, 4, and 6. It evaluates:

- **Popularity:** globally summed pre-cutoff interaction weight.
- **Collaborative:** log-scaled sparse user-item histories and item-item cosine similarity.
- **Content:** L2-normalized TF-IDF product vectors and weighted training-only user profiles.
- **Hybrid:** explicit candidate union followed by normalized weighted scoring.

Content features include synthetic title, category, subcategory, keywords, tags, price bucket, use case, audience, and attributes. Singleton terms are excluded from TF-IDF so a unique synthetic token cannot become a product identifier. Products already seen in training are filtered from every recommendation list.

## Dataset

The deterministic seed-2027 benchmark contains 15,000 users, 600 products, 10 categories, 58,591 sessions, and 330,270 events. Of those events, 267,536 occur before the final cutoff and form 163,208 distinct training user-product interactions. Recommendation behavior, product content, and the simulated experiment are synthetic; no collected marketplace record enters these metrics.

## Evaluation Protocol

The recommender uses two temporal boundaries:

1. **Inner training and validation:** 175,589 earlier events train candidate sources; 4,580 unseen later targets select candidate size and Hybrid weights through a deterministic 198-configuration grid.
2. **Frozen final test:** models are rebuilt on all 267,536 pre-final events and evaluated once on the same 3,954 unseen targets. Final labels never enter selection or normalization.

Every model shares the identical user population, target checksum, cutoff, seen-item exclusion, and metric implementation. Automated checks verify temporal isolation, profile construction, candidate deduplication, configuration provenance, per-user aggregate reconstruction, and population equality. The full methodology is in [recsys/EXPERIMENT_AUDIT.md](recsys/EXPERIMENT_AUDIT.md).

## Results

Authoritative source: [recsys/results/model_comparison.csv](recsys/results/model_comparison.csv).

| Model | Recall@5 | NDCG@5 | Recall@10 | NDCG@10 | Coverage@10 |
|---|---:|---:|---:|---:|---:|
| Popularity | 0.0273 | 0.0165 | 0.0539 | 0.0248 | 0.0300 |
| Collaborative | 0.1624 | 0.1036 | 0.2597 | 0.1349 | 0.5433 |
| Content | 0.0610 | 0.0352 | 0.1222 | 0.0547 | 1.0000 |
| Hybrid | 0.1651 | 0.1052 | 0.2658 | 0.1374 | 0.5050 |

Hybrid's observed Recall@10 delta over Collaborative is +0.00607 and its NDCG@10 delta is +0.00249. These are modest mean improvements, not established overall statistical superiority: Recall@10 has paired-bootstrap 95% CI `[0.00000, 0.01214]` and exact McNemar `p=0.06694`; NDCG@10 has CI `[0.00003, 0.00495]` and paired-randomization `p=0.05099`.

## Hybrid Analysis

The selected validation configuration is Collaborative Top-100, Content Top-100, Popularity Top-10, per-user candidate min-max normalization, and weights α=0.6, β=0.1, γ=0.3. Its validation candidate union averages 134.08 products, retrieves 83.91% of validation targets, and has 56.88% mean Collaborative/Content Jaccard overlap. Content uniquely recovers 4.74% of validation union hits.

On the final test, Hybrid retrieves 86.17% of targets but ranks only 26.58% in Top-10. Of 3,954 targets, 547 are not retrieved and 2,356 are retrieved but ranked below ten. Ranking is therefore the larger measured bottleneck. Hybrid also trades breadth for ranking concentration: Coverage@10 falls 3.83 percentage points below Collaborative.

## Sparse-History Analysis

Among 518 users with 3–5 prior products, Hybrid Recall@10 is 0.21815 versus 0.19498 for Collaborative, a +0.02317 absolute difference; paired CI is `[0.00579, 0.04054]`. NDCG@10 increases from 0.09616 to 0.10534 with CI `[0.00267, 0.01614]`. This is an exploratory lower-history result, not evidence that the system solves cold start; every evaluated user has at least three prior products.

## A/B Experiment

The pipeline also implements deterministic user-level random assignment and a two-proportion test for whether a user purchased at least once. Treatment conversion is 32.94% versus 31.83% for control, an observed +1.12 percentage-point difference with 95% CI `[-0.38, 2.61]` percentage points and `p=0.1445`. The result is non-significant and demonstrates experiment implementation, not product impact.

## APIs / Web Application

The Node server serves the static frontend and these primary keyword routes:

- `POST /api/marketplace-collect` — expand and collect public-source keyword evidence;
- `POST /api/parse-upload` — convert uploaded XLSX content to auditable text;
- `POST /api/export-keyword-xlsx` — create a multi-sheet XLSX workbook.

The repository retains optional image/video experiment routes, but they are outside the reported search and recommendation benchmark. Vercel rewrites preserve `/api/*` handlers and route other requests to the frontend.

## Reproducing Results

Python 3.9+ with NumPy and SciPy is required for RecSys. Node.js runs the dependency-free Marketplace app.

```bash
python3 -m pip install -r recsys/requirements.txt
make recsys       # rebuild data, SQL analyses, models, statistical audit, and evidence
make test         # run all RecSys tests
make verify-docs  # confirm README values match result artifacts
```

Run the web application separately:

```bash
npm run dev
# http://127.0.0.1:8066
```

API keys are optional for keyword functionality. Keep real keys in ignored `.env.local` or managed deployment variables; never commit them.

## Tests

The final suite contains 20 tests covering event integrity, assignment consistency, temporal leakage, Content profiles, seen-item exclusion, deterministic metrics, candidate retrieval, normalization, validation/final separation, configuration provenance, paired bootstrap reproducibility, McNemar counts, population equality, per-user metric reconstruction, result ranges, and documentation consistency.

## Data Integrity & Limitations

- Public suggestions and accessible public pages are discovery evidence, not official marketplace metrics.
- Search volume, official platform heat, ABA values, GMV, sales, reviews, and growth are never fabricated; absent real uploads, those fields stay blank.
- The recommendation benchmark and A/B treatment are synthetic and use one deterministic seed.
- The project has no proprietary Amazon/TikTok data, online recommender test, production traffic, distributed serving, or real-time feature store.
- Offline ranking metrics and the non-significant synthetic A/B result do not establish online business impact.
- The keyword ranker is feature-based code, not a learned-to-rank or NLP model; the recommender is lightweight sparse/TF-IDF modeling, not a neural or deep recommender.

## Repository Structure

```text
api/                         Node/Vercel keyword, upload, export, and auxiliary APIs
app.js, index.html, styles.css
                             Browser application and keyword ranking
collector-server.js          Local static/API server
recsys/src/                  Data, SQL, models, evaluation, statistical audit
recsys/results/              Compact reproducible evidence artifacts
recsys/tests/                End-to-end and methodology tests
ARCHITECTURE.md              Detailed system boundaries and data flow
RESUME_EVIDENCE.md           Claim-by-claim recruiting evidence
INTERVIEW_NOTES.md           Technical talking points
```
