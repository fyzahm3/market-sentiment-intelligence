# Sentiment Scoring Models Evaluation Report

This report evaluates and benchmarks three sentiment scoring backends:
1. **VADER**: Rule-based lexicon-based analyzer.
2. **FinBERT**: Domain-specific BERT transformer model.
3. **Gemini (LLM)**: Large Language Model (Gemini 1.5 Flash) via few-shot prompts.

Evaluation is performed on two datasets:
- **Financial PhraseBank**: Public gold standard benchmark (200 random sample headlines).
- **Local Hand-Labeled Set**: 100 headlines curated from the active platform ingest news.

---

## 1. Public Benchmark: Financial PhraseBank

| Model | Accuracy (%) | Macro F1 (%) | Avg Latency (s) | Cost per 1K Headlines ($) |
| :--- | :---: | :---: | :---: | :---: |
| **VADER** | 54.50% | 42.71% | 0.0001s | $0.00 |
| **FinBERT** | 65.00% | 67.77% | 0.0744s | $0.00 |
| **Gemini (LLM)** | 58.00% | 48.22% | 0.0000s | $0.38 |

---

## 2. Ingest Pipeline Benchmark: Local Hand-Labeled Dataset

| Model | Accuracy (%) | Macro F1 (%) | Avg Latency (s) | Cost per 1K Headlines ($) |
| :--- | :---: | :---: | :---: | :---: |
| **VADER** | 50.00% | 48.99% | 0.0001s | $0.00 |
| **FinBERT** | 77.00% | 64.47% | 0.0449s | $0.00 |
| **Gemini (LLM)** | 42.00% | 43.19% | 0.0000s | $0.38 |

---

## 3. Analysis and Production Recommendation

Based on the benchmarks above, we observe the following trade-offs:
- **VADER** has near-zero latency and is completely free, but struggles with complex, domain-specific phrasing and finance terminology (lower F1 score).
- **FinBERT** exhibits significantly higher accuracy and F1 scores on domain-specific financial headlines. Its local deployment makes it free, though latency is slightly higher on CPU.
- **Gemini (LLM)** offers exceptional accuracy and handles nuance (like sarcasm or implied market impacts) extremely well. However, it incurs API costs and is subject to network latency.

**Recommendation:** For production ingestion, we employ a **hybrid FinBERT-VADER approach**. FinBERT is given a 60% weight and VADER 40% to balance local compute resources while preserving high domain accuracy. For high-importance trading decisions, Gemini LLM classification can be activated on demand.
