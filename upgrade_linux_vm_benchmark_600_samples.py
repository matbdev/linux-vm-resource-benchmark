#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PREPARE_ANALYSIS = r"""from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

PROCESSED.mkdir(parents=True, exist_ok=True)

EXPECTED = {
    "debian": {"family": "debian", "distribution": "debian", "vm": "debian"},
    "ubuntu": {"family": "debian", "distribution": "ubuntu", "vm": "ubuntu"},
    "arch": {"family": "arch", "distribution": "arch-linux", "vm": "arch"},
    "endeavouros": {
        "family": "arch",
        "distribution": "endeavouros",
        "vm": "endeavouros",
    },
    "fedora": {"family": "fedora", "distribution": "fedora", "vm": "fedora"},
    "bazzite": {"family": "fedora", "distribution": "bazzite", "vm": "bazzite"},
}

RAW_SAMPLE_COLUMNS = [
    "elapsed_s",
    "process_cpu_percent",
    "system_cpu_percent",
    "process_rss_mb",
    "system_memory_used_mb",
    "system_memory_percent",
    "logical_read_mb",
    "logical_write_mb",
    "logical_read_rate_mb_s",
    "logical_write_rate_mb_s",
    "storage_read_mb",
    "storage_write_mb",
    "threads",
    "load_1m",
]

ALL_SAMPLE_COLUMNS = [
    "sample_id",
    "family",
    "distribution",
    "vm",
    "run",
    "sample",
    "started_at_utc",
    "input_sha256",
    "ffmpeg_exit_code",
    *RAW_SAMPLE_COLUMNS,
]

IO_COLUMNS = [
    "logical_read_mb",
    "logical_write_mb",
    "logical_read_rate_mb_s",
    "logical_write_rate_mb_s",
    "storage_read_mb",
    "storage_write_mb",
]

ANALYSIS_COLUMNS = [
    "sample_id",
    "family",
    "distribution",
    "vm",
    "run",
    "sample",
    "started_at_utc",
    "elapsed_s",
    "process_cpu_percent",
    "system_cpu_percent",
    "process_rss_mb",
    "system_memory_used_mb",
    "system_memory_percent",
    "threads",
    "load_1m",
]

MAIN_METRICS = [
    "process_cpu_percent",
    "system_cpu_percent",
    "process_rss_mb",
    "system_memory_used_mb",
    "system_memory_percent",
    "threads",
    "load_1m",
]

QUICK_METRICS = [
    "process_cpu_percent",
    "system_cpu_percent",
    "process_rss_mb",
    "system_memory_used_mb",
]


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    sys.exit(1)


def coefficient_of_variation(series: pd.Series) -> float:
    mean = series.mean()
    if mean == 0:
        return float("nan")
    return series.std(ddof=1) / mean * 100


run_frames = []
sample_frames = []
reference_summary_columns = None
reference_sample_columns = None
input_hashes = set()

print("=== VALIDATING COLLECTION ===\n")

for folder, expected in EXPECTED.items():
    distro_root = RAW / folder
    summary_path = distro_root / "summary.csv"

    if not summary_path.exists():
        fail(f"Missing file: {summary_path}")

    summary = pd.read_csv(summary_path)

    if len(summary) != 10:
        fail(f"{folder}: expected 10 measured runs, found {len(summary)}")

    summary_columns = list(summary.columns)
    if reference_summary_columns is None:
        reference_summary_columns = summary_columns
    elif summary_columns != reference_summary_columns:
        fail(f"{folder}: summary.csv schema differs from the other distributions")

    expected_runs = list(range(1, 11))
    actual_runs = sorted(summary["run"].astype(int).tolist())
    if actual_runs != expected_runs:
        fail(
            f"{folder}: invalid run sequence. "
            f"Expected {expected_runs}, found {actual_runs}"
        )

    if not (summary["ffmpeg_exit_code"] == 0).all():
        fail(f"{folder}: at least one FFmpeg execution failed")

    if not (summary["samples"] == 10).all():
        fail(f"{folder}: every measured run must contain exactly 10 samples")

    if summary["family"].nunique() != 1 or summary["family"].iloc[0] != expected["family"]:
        fail(f"{folder}: invalid family label")

    if (
        summary["distribution"].nunique() != 1
        or summary["distribution"].iloc[0] != expected["distribution"]
    ):
        fail(f"{folder}: invalid distribution label")

    if summary["vm"].nunique() != 1 or summary["vm"].iloc[0] != expected["vm"]:
        fail(f"{folder}: invalid VM label")

    distro_hashes = summary["input_sha256"].dropna().unique()
    if len(distro_hashes) != 1:
        fail(f"{folder}: expected exactly one input SHA-256")
    input_hashes.add(distro_hashes[0])

    run_frames.append(summary)

    distro_samples = []

    for run in expected_runs:
        run_path = distro_root / "runs" / f"run_{run:02d}.csv"
        if not run_path.exists():
            fail(f"Missing file: {run_path}")

        samples = pd.read_csv(run_path)

        if list(samples.columns) != RAW_SAMPLE_COLUMNS:
            fail(f"{run_path}: unexpected sample schema")

        if reference_sample_columns is None:
            reference_sample_columns = list(samples.columns)
        elif list(samples.columns) != reference_sample_columns:
            fail(f"{run_path}: sample schema differs from the other runs")

        summary_row = summary.loc[summary["run"] == run]
        if len(summary_row) != 1:
            fail(f"{folder}: summary row for run {run} not found")

        expected_samples = int(summary_row["samples"].iloc[0])
        if len(samples) != expected_samples:
            fail(
                f"{run_path}: expected {expected_samples} samples, "
                f"found {len(samples)}"
            )

        samples.insert(0, "sample", range(1, len(samples) + 1))
        samples.insert(0, "run", run)
        samples.insert(0, "vm", expected["vm"])
        samples.insert(0, "distribution", expected["distribution"])
        samples.insert(0, "family", expected["family"])
        samples.insert(
            0,
            "sample_id",
            [
                f"{expected['distribution']}-r{run:02d}-s{sample:02d}"
                for sample in range(1, len(samples) + 1)
            ],
        )
        samples.insert(
            6,
            "started_at_utc",
            summary_row["started_at_utc"].iloc[0],
        )
        samples.insert(
            7,
            "input_sha256",
            summary_row["input_sha256"].iloc[0],
        )
        samples.insert(
            8,
            "ffmpeg_exit_code",
            int(summary_row["ffmpeg_exit_code"].iloc[0]),
        )

        distro_samples.append(samples[ALL_SAMPLE_COLUMNS])

    distro_frame = pd.concat(distro_samples, ignore_index=True)

    if len(distro_frame) != 100:
        fail(f"{folder}: expected 100 measured samples, found {len(distro_frame)}")

    print(f"{folder}: 10 runs, {len(distro_frame)} measured samples")
    sample_frames.append(distro_frame)


all_runs = pd.concat(run_frames, ignore_index=True)
all_samples = pd.concat(sample_frames, ignore_index=True)

print("\n=== GLOBAL VALIDATION ===")

if len(all_runs) != 60:
    fail(f"Expected 60 measured runs, found {len(all_runs)}")

if len(all_samples) != 600:
    fail(f"Expected 600 measured samples, found {len(all_samples)}")

if len(input_hashes) != 1:
    fail("Multiple benchmark input SHA-256 hashes found")

comparable_numeric = [
    "elapsed_s",
    "process_cpu_percent",
    "system_cpu_percent",
    "process_rss_mb",
    "system_memory_used_mb",
    "system_memory_percent",
    "threads",
    "load_1m",
]

nulls = all_samples[comparable_numeric].isna().sum()
problematic = nulls[nulls > 0]
if not problematic.empty:
    fail(f"Null values found in comparable sample metrics:\n{problematic}")

print(f"Measured runs:    {len(all_runs)}")
print(f"Measured samples: {len(all_samples)}")
print(f"Samples/distro:   {all_samples.groupby('distribution').size().to_dict()}")
print(f"Unique SHA-256:   {next(iter(input_hashes))}")
print("FFmpeg exit codes: all 0")

print("\n=== I/O ===")
for column in IO_COLUMNS:
    print(f"{column}: {all_samples[column].isna().sum()} missing values")

print(
    "\nI/O columns are preserved in all_samples.csv. "
    "They are excluded from analysis.csv because terminal-sample "
    "coverage is not equivalent across all environments."
)

all_runs_path = PROCESSED / "all_runs.csv"
all_runs.to_csv(all_runs_path, index=False)

all_samples_path = PROCESSED / "all_samples.csv"
all_samples.to_csv(all_samples_path, index=False)

analysis = all_samples[ANALYSIS_COLUMNS].copy()

analysis_path = PROCESSED / "analysis.csv"
analysis.to_csv(analysis_path, index=False)

records = []

for distribution, group in analysis.groupby("distribution", sort=False):
    family = group["family"].iloc[0]

    for metric in MAIN_METRICS:
        values = group[metric]
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)

        records.append(
            {
                "family": family,
                "distribution": distribution,
                "metric": metric,
                "n": values.count(),
                "mean": values.mean(),
                "median": values.median(),
                "variance": values.var(ddof=1),
                "std": values.std(ddof=1),
                "cv_percent": coefficient_of_variation(values),
                "min": values.min(),
                "q1": q1,
                "q3": q3,
                "max": values.max(),
                "range": values.max() - values.min(),
                "iqr": q3 - q1,
            }
        )

descriptive = pd.DataFrame(records)
descriptive_path = PROCESSED / "descriptive_by_distribution.csv"
descriptive.to_csv(descriptive_path, index=False)

quick = (
    analysis.groupby(["family", "distribution"])[QUICK_METRICS]
    .agg(["mean", "std", "min", "max"])
)
quick.columns = [
    f"{metric}_{stat}"
    for metric, stat in quick.columns.to_flat_index()
]
quick = quick.reset_index().round(3)

quick_path = PROCESSED / "quick_summary.csv"
quick.to_csv(quick_path, index=False)

print("\n=== OUTPUT ===")
print(f"Run summaries:          {all_runs_path}")
print(f"All measured samples:   {all_samples_path}")
print(f"Primary analysis data:  {analysis_path}")
print(f"Descriptive statistics: {descriptive_path}")
print(f"Quick summary:          {quick_path}")

print("\nPrimary analysis now uses the 600 raw measured samples.")
print("Validation completed successfully.")
"""

ANALYZE_RESULTS = r"""from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "results" / "figures"

FIGURES.mkdir(parents=True, exist_ok=True)

LEGACY_RUN_LEVEL_FIGURES = [
    "boxplot_process_cpu_mean_percent.png",
    "boxplot_process_rss_mean_mb.png",
    "boxplot_system_cpu_mean_percent.png",
    "boxplot_system_memory_used_mean_mb.png",
    "mean_process_cpu_mean_percent.png",
    "mean_process_rss_mean_mb.png",
    "mean_system_cpu_mean_percent.png",
    "mean_system_memory_used_mean_mb.png",
]

for filename in LEGACY_RUN_LEVEL_FIGURES:
    path = FIGURES / filename
    if path.exists():
        path.unlink()

df = pd.read_csv(PROCESSED / "analysis.csv")

ORDER = [
    "debian",
    "ubuntu",
    "arch-linux",
    "endeavouros",
    "fedora",
    "bazzite",
]

LABELS = {
    "debian": "Debian",
    "ubuntu": "Ubuntu",
    "arch-linux": "Arch Linux",
    "endeavouros": "EndeavourOS",
    "fedora": "Fedora",
    "bazzite": "Bazzite",
}

METRICS = {
    "process_cpu_percent": "FFmpeg CPU usage (%)",
    "system_cpu_percent": "System CPU usage (%)",
    "process_rss_mb": "FFmpeg RSS memory (MB)",
    "system_memory_used_mb": "System memory usage (MB)",
}

HISTOGRAM_METRICS = [
    "process_cpu_percent",
    "system_memory_used_mb",
]

PROFILE_METRICS = [
    "process_cpu_percent",
    "system_memory_used_mb",
]


def coefficient_of_variation(series: pd.Series) -> float:
    mean = series.mean()
    if mean == 0:
        return float("nan")
    return series.std(ddof=1) / mean * 100


if len(df) != 600:
    raise ValueError(f"Expected 600 sample observations, found {len(df)}")

counts = df.groupby("distribution").size().reindex(ORDER)
if not (counts == 100).all():
    raise ValueError(
        "Expected 100 sample observations per distribution, found:\n"
        f"{counts}"
    )

records = []

for distribution in ORDER:
    group = df[df["distribution"] == distribution]

    for metric, label in METRICS.items():
        values = group[metric]
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)

        records.append(
            {
                "distribution": LABELS[distribution],
                "metric": label,
                "n": values.count(),
                "mean": values.mean(),
                "median": values.median(),
                "variance": values.var(ddof=1),
                "std": values.std(ddof=1),
                "cv_percent": coefficient_of_variation(values),
                "min": values.min(),
                "q1": q1,
                "q3": q3,
                "max": values.max(),
                "range": values.max() - values.min(),
                "iqr": q3 - q1,
            }
        )

descriptive = pd.DataFrame(records)
descriptive.to_csv(
    PROCESSED / "descriptive_main_metrics.csv",
    index=False,
)

summary = (
    df.groupby("distribution")[list(METRICS)]
    .agg(["mean", "median", "std", "min", "max"])
    .reindex(ORDER)
)
summary.columns = [
    f"{metric}_{stat}"
    for metric, stat in summary.columns.to_flat_index()
]
summary = summary.reset_index()
summary.insert(
    1,
    "distribution_label",
    summary["distribution"].map(LABELS),
)
summary.to_csv(PROCESSED / "summary_table.csv", index=False)

print("\n=== SAMPLE-LEVEL SUMMARY (n=600) ===\n")
print(summary.round(2).to_string(index=False))

for metric, ylabel in METRICS.items():
    values = [
        df.loc[df["distribution"] == distro, metric]
        for distro in ORDER
    ]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.boxplot(
        values,
        tick_labels=[LABELS[distro] for distro in ORDER],
    )
    ax.set_title(f"{ylabel} by distribution — 100 samples each")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Distribution")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(
        FIGURES / f"boxplot_{metric}.png",
        dpi=200,
    )
    plt.close(fig)

for metric, ylabel in METRICS.items():
    grouped = (
        df.groupby("distribution")[metric]
        .agg(["mean", "std"])
        .reindex(ORDER)
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(
        [LABELS[distro] for distro in ORDER],
        grouped["mean"],
        yerr=grouped["std"],
        capsize=5,
    )
    ax.set_title(f"{ylabel} — mean ± standard deviation")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Distribution")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(
        FIGURES / f"mean_{metric}.png",
        dpi=200,
    )
    plt.close(fig)

for metric in HISTOGRAM_METRICS:
    ylabel = METRICS[metric]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df[metric], bins="sturges")
    ax.set_title(f"Frequency distribution — {ylabel}")
    ax.set_xlabel(ylabel)
    ax.set_ylabel("Frequency")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(
        FIGURES / f"histogram_{metric}.png",
        dpi=200,
    )
    plt.close(fig)

for metric in PROFILE_METRICS:
    ylabel = METRICS[metric]

    profile = (
        df.groupby(["distribution", "sample"])[metric]
        .mean()
        .unstack("distribution")
        .reindex(columns=ORDER)
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    for distribution in ORDER:
        ax.plot(
            profile.index,
            profile[distribution],
            marker="o",
            label=LABELS[distribution],
        )

    ax.set_title(f"Mean temporal profile — {ylabel}")
    ax.set_xlabel("Sample within run")
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(1, 11))
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(
        FIGURES / f"profile_{metric}.png",
        dpi=200,
    )
    plt.close(fig)

print()
print(f"Figures generated in: {FIGURES}")
print("Analysis uses all 600 measured samples.")
"""

VALIDATE = r"""#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"

DISTROS=(
  arch
  bazzite
  debian
  endeavouros
  fedora
  ubuntu
)

TOTAL_SAMPLES=0

for distro in "${DISTROS[@]}"; do
    echo "========== $distro =========="

    RUNS="$(find "$RAW/$distro/runs" -maxdepth 1 -name 'run_*.csv' -type f | wc -l)"
    WARMUPS="$(find "$RAW/$distro/warmups" -maxdepth 1 -name 'warmup_*.csv' -type f | wc -l)"
    SUMMARY_ROWS="$(( $(wc -l < "$RAW/$distro/summary.csv") - 1 ))"
    SAMPLES="$(
      find "$RAW/$distro/runs" -maxdepth 1 -name 'run_*.csv' -type f -print0 |
      sort -z |
      xargs -0 -I{} sh -c 'echo $(( $(wc -l < "$1") - 1 ))' _ {} |
      awk '{ total += $1 } END { print total + 0 }'
    )"

    echo "runs:          $RUNS"
    echo "warmups:       $WARMUPS"
    echo "summary rows:  $SUMMARY_ROWS"
    echo "valid samples: $SAMPLES"

    [[ "$RUNS" -eq 10 ]] || { echo "ERROR: expected 10 runs"; exit 1; }
    [[ "$WARMUPS" -eq 2 ]] || { echo "ERROR: expected 2 warmups"; exit 1; }
    [[ "$SUMMARY_ROWS" -eq 10 ]] || { echo "ERROR: expected 10 summary rows"; exit 1; }
    [[ "$SAMPLES" -eq 100 ]] || { echo "ERROR: expected 100 measured samples"; exit 1; }

    TOTAL_SAMPLES=$((TOTAL_SAMPLES + SAMPLES))
    echo
done

echo "Checking for empty CSV files..."

EMPTY_FILES="$(
    find "$RAW" \
      \( \
        -path '*/runs/*.csv' \
        -o -path '*/warmups/*.csv' \
        -o -name 'summary.csv' \
      \) \
      -type f \
      -empty
)"

if [[ -n "$EMPTY_FILES" ]]; then
    echo "ERROR: empty files found:"
    echo "$EMPTY_FILES"
    exit 1
fi

[[ "$TOTAL_SAMPLES" -eq 600 ]] || {
    echo "ERROR: expected 600 measured samples, found $TOTAL_SAMPLES"
    exit 1
}

echo "No empty measurement files found."
echo "Measured sample total: $TOTAL_SAMPLES"
echo "Validation completed successfully."
"""

VALIDATE_HEADER = r"""#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"

DISTROS=(
  arch
  bazzite
  debian
  endeavouros
  fedora
  ubuntu
)

REFERENCE_SAMPLE=""
REFERENCE_SUMMARY=""

for distro in "${DISTROS[@]}"; do
    SUMMARY_FILE="$RAW/$distro/summary.csv"
    SUMMARY_HEADER="$(head -n 1 "$SUMMARY_FILE")"

    if [[ -z "$REFERENCE_SUMMARY" ]]; then
        REFERENCE_SUMMARY="$SUMMARY_HEADER"
    elif [[ "$SUMMARY_HEADER" != "$REFERENCE_SUMMARY" ]]; then
        echo "ERROR: summary.csv header mismatch detected in $distro"
        exit 1
    fi

    for file in "$RAW/$distro"/runs/run_*.csv; do
        HEADER="$(head -n 1 "$file")"

        if [[ -z "$REFERENCE_SAMPLE" ]]; then
            REFERENCE_SAMPLE="$HEADER"
        elif [[ "$HEADER" != "$REFERENCE_SAMPLE" ]]; then
            echo "ERROR: sample header mismatch detected in $file"
            exit 1
        fi
    done
done

echo "All summary.csv files use the same schema."
echo "All measured run CSV files use the same sample schema."
"""

README = r"""# Linux VM Resource Benchmark

A controlled statistical experiment comparing resource consumption across six Linux distributions running the same workload under identical virtual machine configurations.

The project was developed for a statistical data analysis study. The primary analysis dataset uses the raw per-second measurements collected during the measured benchmark runs.

## Objective

The experiment investigates how different Linux distributions behave when executing the same CPU-intensive workload under controlled virtualization conditions.

| Family | Distribution |
|---|---|
| Debian-based | Debian |
| Debian-based | Ubuntu |
| Arch-based | Arch Linux |
| Arch-based | EndeavourOS |
| Fedora-based | Fedora |
| Fedora-based | Bazzite |

The goal is not to establish a universal performance ranking between Linux distributions, but to describe and compare resource-use patterns under the specific conditions of this experiment.

## Experimental Environment

Host operating system:

- Pop!_OS

Virtualization stack:

- KVM
- QEMU
- libvirt
- virt-manager

Each VM used the same virtual hardware configuration:

| Resource | Configuration |
|---|---|
| vCPU | 4 |
| Memory | 8 GiB |
| Storage | 80 GiB QCOW2 |
| Firmware | UEFI |
| Disk interface | VirtIO |
| Network interface | VirtIO |
| Network | libvirt NAT |
| CPU mode | host-passthrough |

Only one VM was benchmarked at a time to reduce direct contention for host resources.

## Workload

FFmpeg with libx264 was used as the benchmark workload. Every distribution processed the same synthetic video input.

SHA-256:

```text
cb08f335d0e96a41e967f8d19eb99c4db4b4ac9cb6ffaa228641776b6e82dcb3
```

## Collection Method

Each distribution executed:

```text
2 warm-up runs
10 measured runs
10 samples per measured run
1 sample per second
```

The warm-up runs are preserved in the raw data but excluded from the primary statistical analysis.

Primary sample size:

```text
6 distributions × 10 measured runs × 10 samples = 600 measured samples
```

The experiment also contains 60 measured run summaries:

```text
6 distributions × 10 measured runs = 60 run summaries
```

A measured run therefore contributes 10 raw time-series observations to the primary dataset and one secondary run-level summary.

The columns `run` and `sample` are retained in the processed dataset so the nested structure of the measurements remains explicit.

## Statistical Unit Used in This Repository

For the course analysis, the primary dataset is the set of **600 per-second measurements**.

This differs from the earlier version of the repository, which used the 60 run-level summaries as the main analysis table.

The 60 summaries are still preserved in `data/processed/all_runs.csv` because they are useful for reproducibility and secondary checks, but descriptive statistics, frequency distributions and figures are generated from the 600 raw measurements.

The measurements inside the same run are sequential observations from the same execution. This dependence should be kept in mind when interpreting results or applying inferential methods.

## Collected Sample Metrics

### CPU

- FFmpeg process CPU usage;
- total system CPU usage.

### Memory

- FFmpeg RSS memory;
- total system memory usage;
- system memory percentage.

### Execution context

- elapsed seconds within the run;
- sample number;
- thread count;
- 1-minute load average.

### I/O

Logical and storage I/O metrics are preserved in `all_samples.csv`.

They are not part of the primary comparison because terminal-sample coverage is not equivalent across all environments.

## Data Validation

The validation pipeline checks:

- 6 distributions;
- 10 measured runs per distribution;
- 2 warm-up runs per distribution;
- 10 samples per measured run;
- 100 measured samples per distribution;
- 600 measured samples in total;
- consistent schemas;
- no empty measurement files;
- identical benchmark input SHA-256;
- FFmpeg exit code `0` for all measured runs.

The raw data is preserved without modification under `data/raw/`.

## Repository Structure

```text
.
├── benchmark/
│   ├── benchmark.py
│   └── benchmark_input.sha256
├── scripts/
│   ├── prepare_analysis.py
│   ├── analyze_results.py
│   ├── validate.sh
│   ├── validate_content.sh
│   └── validate_header.sh
├── data/
│   ├── raw/
│   └── processed/
│       ├── all_runs.csv
│       ├── all_samples.csv
│       ├── analysis.csv
│       ├── descriptive_by_distribution.csv
│       ├── descriptive_main_metrics.csv
│       ├── quick_summary.csv
│       └── summary_table.csv
├── results/
│   └── figures/
└── experiment/
    └── metodologia_experimento_vms.docx
```

## Reproducibility

Generate the benchmark input:

```bash
python3 benchmark/benchmark.py prepare-input
```

Example benchmark execution:

```bash
python3 benchmark/benchmark.py run \
  --family debian \
  --distribution debian \
  --vm debian
```

Other distributions:

```bash
python3 benchmark/benchmark.py run --family debian --distribution ubuntu --vm ubuntu
python3 benchmark/benchmark.py run --family arch --distribution arch-linux --vm arch
python3 benchmark/benchmark.py run --family arch --distribution endeavouros --vm endeavouros
python3 benchmark/benchmark.py run --family fedora --distribution fedora --vm fedora
python3 benchmark/benchmark.py run --family fedora --distribution bazzite --vm bazzite
```

## Prepare the 600-Sample Dataset

Run:

```bash
python3 scripts/prepare_analysis.py
```

Generated files:

- `all_runs.csv`: the 60 run-level summaries;
- `all_samples.csv`: all 600 raw measured samples, including I/O fields;
- `analysis.csv`: the 600 samples with the comparable variables used in the primary analysis;
- `descriptive_by_distribution.csv`: sample-level descriptive statistics;
- `quick_summary.csv`: compact sample-level comparison by distribution.

## Generate Analysis and Figures

Run:

```bash
python3 scripts/analyze_results.py
```

This creates sample-level descriptive tables and several figure types:

- boxplots by distribution;
- mean ± standard-deviation bar charts;
- histograms for frequency distributions;
- temporal profiles across the 10 samples of each run.

## Important Detail About the Final Sample

The last measurement of a run can capture the FFmpeg process finishing. For that reason, the final raw sample may contain a much lower process CPU value, fewer threads, or `0` MB of process RSS.

These observations are not removed from the 600-sample dataset. The course analysis is intended to use the raw measurements, so all ten measured samples from every valid run are retained.

## Methodological Limitation

The 600 observations are not 600 independent benchmark executions.

They are 10 sequential measurements nested inside each of 60 measured runs, and those 60 runs are repeated measurements of one VM installation per distribution.

This structure is appropriate for the requested descriptive analysis, but it must be considered before making inferential or broadly generalizable claims.

## Technologies

- Linux
- Python
- psutil
- pandas
- matplotlib
- FFmpeg
- KVM
- QEMU
- libvirt
- virt-manager

## Status

Data collection: **complete**

```text
600 measured samples
60 measured benchmark runs
12 warm-up runs
6 Linux distributions
```

Primary descriptive analysis: **sample-level (n = 600)**
"""

FIGURES_README = r"""# Figures

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
"""

MAKEFILE = r""".PHONY: all validate prepare analyze

all: validate prepare analyze

validate:
	bash scripts/validate_header.sh
	bash scripts/validate.sh

prepare:
	python3 scripts/prepare_analysis.py

analyze:
	python3 scripts/analyze_results.py
"""


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[write] {relative}")


def run(cmd: list[str], root: Path) -> None:
    print(f"[run] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=root, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate linux-vm-resource-benchmark to primary n=600 sample-level analysis."
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the repository root (default: current directory).",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Only write files; do not run validation/analysis.",
    )
    args = parser.parse_args()

    root = Path(args.repo).resolve()

    required = [
        root / "data" / "raw",
        root / "scripts",
        root / "benchmark",
    ]
    if not all(path.exists() for path in required):
        raise SystemExit(
            "This does not look like the linux-vm-resource-benchmark repository root. "
            "Run from the repo or pass --repo /path/to/repo."
        )

    write(root, "scripts/prepare_analysis.py", PREPARE_ANALYSIS)
    write(root, "scripts/analyze_results.py", ANALYZE_RESULTS)
    write(root, "scripts/validate.sh", VALIDATE)
    write(root, "scripts/validate_header.sh", VALIDATE_HEADER)
    write(root, "README.md", README)
    write(root, "results/figures/README.md", FIGURES_README)
    write(root, "Makefile", MAKEFILE)

    (root / "scripts" / "validate.sh").chmod(0o755)
    (root / "scripts" / "validate_header.sh").chmod(0o755)

    if not args.no_run:
        run(["bash", "scripts/validate_header.sh"], root)
        run(["bash", "scripts/validate.sh"], root)
        run(["python3", "scripts/prepare_analysis.py"], root)
        run(["python3", "scripts/analyze_results.py"], root)

    print("\nMigration complete.")
    print("Review with: git status && git diff --stat")
    print('Commit suggestion: git commit -am "refactor: analyze all 600 raw samples"')


if __name__ == "__main__":
    main()
