from pathlib import Path
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
