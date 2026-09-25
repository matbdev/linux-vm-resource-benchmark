# Figures

The primary figures in this directory are generated from the **600 measured per-second samples** in `data/processed/analysis.csv`.

Regenerate everything with:

```bash
python3 scripts/prepare_analysis.py
python3 scripts/analyze_results.py
```

The analysis script generates:

- boxplots by distribution;
- mean ± standard-deviation bar charts;
- histograms for the two main frequency-distribution variables;
- temporal profiles across sample positions 1–10.

Legacy run-level figure names from the previous 60-observation analysis are removed automatically to avoid mixing the two statistical units.
