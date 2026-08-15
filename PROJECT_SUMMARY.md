# Project Summary

## Purpose

The E-commerce Search & Recommendation Platform is a portfolio project for Search/Recommendation MLE work. It combines a Marketplace keyword-intelligence web application with a reproducible offline recommendation benchmark.

## Marketplace application

- Expands Amazon- and TikTok Shop-oriented product queries across supported markets, languages, intent modifiers, and long-tail forms.
- Collects bounded public suggestion/search evidence and preserves source query, provider, URL, region, language, and source type.
- Accepts pasted text and CSV, TSV, TXT, XLS, or XLSX reports.
- Extracts, categorizes, deduplicates, and feature-ranks keywords, phrases, hashtags, and Chinese sequences.
- Exports CSV, source audit data, and an XLSX workbook with keyword, summary, analysis, and real-trend sheets.
- Never represents its internal `Weight` as search volume or invents official heat, sales, GMV, reviews, or growth.

## Recommendation benchmark

- Generates deterministic synthetic catalog, user, session, event, and experiment data.
- Implements Popularity, item-item Collaborative, TF-IDF Content, and three-signal Hybrid recommendation.
- Selects candidate sizes and Hybrid weights on an earlier temporal validation period, then evaluates on a frozen later target set.
- Reports offline ranking, coverage, retrieval, sparse-history, paired statistical, and A/B evidence.
- Reproduces the full benchmark with `make recsys` and validates it with `make test` and `make verify-docs`.

The synthetic product schema reflects Marketplace keyword/category concepts, but live Marketplace collection output is not used in the reported RecSys metrics. See `README.md`, `ARCHITECTURE.md`, and `RESUME_EVIDENCE.md` for full evidence and limitations.
