# Fire AI Take-Home Assignment

Two projects demonstrating rule-based, statistical, and LLM-based approaches to real-world data problems.

---

## Projects

### Project A — Indian Income Tax Engine
A service that tells a salaried person in India how much income tax they owe under the **old** and **new** regimes, which regime to choose, and exactly why. Users describe themselves in plain English or Hinglish.

Three implementations are compared:
1. **Hand-coded rules** — deterministic Python, fully auditable, ~1 ms latency
2. **LLM at query time** — Gemini Flash answers each query with full rule text in prompt
3. **LLM-compiled rules** — LLM generates the rule code once; runtime is pure Python

### Project B — Data Quality Engine
A pipeline that detects 12 categories of data-quality problems in tabular datasets (validated on 2023 NYC 311 data). Three detector families — rule-based, statistical, and LLM — are benchmarked for detection rate, false-alarm rate, and cost.

---

## Prerequisites

- **Python 3.10+**
- A `GOOGLE_API_KEY` environment variable (required for all LLM features)
  ```bash
  # Windows PowerShell
  $env:GOOGLE_API_KEY = "your-key-here"

  # Linux / macOS
  export GOOGLE_API_KEY="your-key-here"
  ```
- Get a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey)

---

## Installation

```bash
# Clone or download the repository, then:

pip install -r project_a/requirements.txt
pip install -r project_b/requirements.txt
```

---

## Quick Start — Reproduce All Results

```bash
python run_all.py
```

This runs both benchmark suites and prints a consolidated summary. Exit code `0` means all tests passed.

---

## Project A Usage

```bash
cd project_a

# See all options
python main.py --help

# Interactive mode (natural-language input)
python main.py

# Batch benchmark (all 3 implementations × 222 test cases)
python benchmark.py

# Apply FY 2025-26 rules and re-benchmark
python benchmark.py --fy 2025-26
```

### Example interaction

```
Enter your details: I earn 12 lakh per year, pay 15k rent in Mumbai, invest 1.5L in ELSS

Parsing input... done.
Clarification needed: What is your basic salary component? (needed for HRA calculation)
> 7 lakh

─────────────────────────────────────────────
  OLD REGIME          NEW REGIME
  Taxable: ₹7,54,000  Taxable: ₹10,45,000
  Tax:     ₹93,288    Tax:     ₹1,04,000
─────────────────────────────────────────────
  ✅ Old regime saves you ₹10,712 this year.
─────────────────────────────────────────────
```

---

## Project B Usage

```bash
cd project_b

# Run full pipeline on sample data (included)
python pipeline.py

# Run pipeline on a custom CSV
python pipeline.py --input path/to/data.csv

# Run only the LLM detectors (requires GOOGLE_API_KEY)
python pipeline.py --detectors llm

# Benchmark all detectors
python benchmark.py
```

---

## Project Structure

```
FireAi/
├── run_all.py                    ← Single command to reproduce all results
├── README.md                     ← This file
├── RESULTS_A.md                  ← Project A benchmark results & recommendation
├── RESULTS_B.md                  ← Project B benchmark results & scale design
├── DECISION_MATRIX.md            ← Component-by-component design decisions
├── AI_USAGE.md                   ← Honest disclosure of AI tool usage
│
├── project_a/
│   ├── main.py                   ← Interactive CLI entry point
│   ├── parser.py                 ← NLP parser (Gemini)
│   ├── benchmark.py              ← Runs all 3 engines on test suite
│   ├── tax_law_fy2526.py         ← FY 2025-26 rule update module
│   ├── requirements.txt
│   ├── implementations/
│   │   ├── hand_coded_rules.py   ← Deterministic rule engine
│   │   ├── llm_at_query_time.py  ← LLM answers each query
│   │   └── llm_compiled_rules.py ← LLM-generated static code
│   └── tests/
│       ├── test_cases.py         ← 222 structured test cases (including official IT portal refs)
│       └── plain_language_inputs.py  ← 50 NL input test cases
│
└── project_b/
    ├── pipeline.py               ← Main quality pipeline
    ├── benchmark.py              ← Detector benchmark harness
    ├── requirements.txt
    ├── detectors/
    │   ├── rule_based.py         ← Schema, null, date, bbox, and constraint checks
    │   ├── statistical.py        ← z-score, TF-IDF, distribution shifts
    │   └── llm_detector.py       ← PII, semantic mismatch review
    └── data/
        └── nyc311_sample.csv     ← Sample data for quick testing
```

---

## Results Summary

| | Project A | Project B |
|---|---|---|
| Best accuracy | Hand-coded rules: **100%** | Rule checks: **100%** (schema/null/date) |
| Best cost | Hand-coded rules: **$0/req** | Rule checks: **$0/M rows** |
| Best for NLP | LLM parser: **94% field extraction** | LLM detectors: **93.7% PII detection** |
| Scale (100 K users / 50 M rows/day) | Rule engine handles it comfortably | Full pipeline: ~$21/day, < 45 min |

See [`RESULTS_A.md`](RESULTS_A.md), [`RESULTS_B.md`](RESULTS_B.md), and [`DECISION_MATRIX.md`](DECISION_MATRIX.md) for full details.
