from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

PROCESSED.mkdir(parents=True, exist_ok=True)

EXPECTED = {
    "debian": {
        "family": "debian",
        "distribution": "debian",
    },
    "ubuntu": {
        "family": "debian",
        "distribution": "ubuntu",
    },
    "arch": {
        "family": "arch",
        "distribution": "arch-linux",
    },
    "endeavouros": {
        "family": "arch",
        "distribution": "endeavouros",
    },
    "fedora": {
        "family": "fedora",
        "distribution": "fedora",
    },
    "bazzite": {
        "family": "fedora",
        "distribution": "bazzite",
    },
}

IO_COLUMNS = [
    "logical_read_total_mb",
    "logical_write_total_mb",
    "storage_read_total_mb",
    "storage_write_total_mb",
]

ANALYSIS_COLUMNS = [
    "family",
    "distribution",
    "vm",
    "run",
    "started_at_utc",
    "elapsed_s",
    "samples",
    "process_cpu_mean_percent",
    "process_cpu_peak_percent",
    "system_cpu_mean_percent",
    "system_cpu_peak_percent",
    "process_rss_mean_mb",
    "process_rss_peak_mb",
    "system_memory_used_mean_mb",
    "system_memory_used_peak_mb",
    "threads_mean",
    "threads_peak",
]

MAIN_METRICS = [
    "process_cpu_mean_percent",
    "process_cpu_peak_percent",
    "system_cpu_mean_percent",
    "system_cpu_peak_percent",
    "process_rss_mean_mb",
    "process_rss_peak_mb",
    "system_memory_used_mean_mb",
    "system_memory_used_peak_mb",
    "threads_mean",
    "threads_peak",
]

CONTROL_METRICS = [
    "elapsed_s",
    "samples",
]


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    sys.exit(1)


def coefficient_of_variation(series: pd.Series) -> float:
    mean = series.mean()

    if mean == 0:
        return float("nan")

    return series.std(ddof=1) / mean * 100


frames = []
reference_columns = None

print("=== VALIDATING COLLECTION ===\n")

for folder, expected in EXPECTED.items():
    path = RAW / folder / "summary.csv"

    if not path.exists():
        fail(f"Missing file: {path}")

    df = pd.read_csv(path)

    print(f"{folder}: {len(df)} runs")

    if len(df) != 10:
        fail(
            f"{folder}: expected 10 measured runs, "
            f"found {len(df)}"
        )

    columns = list(df.columns)

    if reference_columns is None:
        reference_columns = columns
    elif columns != reference_columns:
        fail(f"{folder}: CSV schema differs from the other distributions")

    expected_runs = list(range(1, 11))
    actual_runs = sorted(df["run"].tolist())

    if actual_runs != expected_runs:
        fail(
            f"{folder}: invalid run sequence. "
            f"Expected {expected_runs}, found {actual_runs}"
        )

    families = df["family"].dropna().unique()

    if len(families) != 1 or families[0] != expected["family"]:
        fail(
            f"{folder}: invalid family. "
            f"Expected '{expected['family']}', found {families}"
        )

    distributions = df["distribution"].dropna().unique()

    if (
        len(distributions) != 1
        or distributions[0] != expected["distribution"]
    ):
        fail(
            f"{folder}: invalid distribution. "
            f"Expected '{expected['distribution']}', "
            f"found {distributions}"
        )

    if not (df["ffmpeg_exit_code"] == 0).all():
        fail(f"{folder}: at least one FFmpeg execution failed")

    if df["samples"].isna().any():
        fail(f"{folder}: null values found in 'samples'")

    if not (df["samples"] == 10).all():
        print(
            f"[WARNING] {folder}: not every run contains exactly "
            "10 samples"
        )

    numeric_columns = [
        column
        for column in ANALYSIS_COLUMNS
        if column not in {
            "family",
            "distribution",
            "vm",
            "started_at_utc",
        }
    ]

    nulls = df[numeric_columns].isna().sum()
    problematic = nulls[nulls > 0]

    if not problematic.empty:
        fail(
            f"{folder}: null values found in comparable metrics:\n"
            f"{problematic}"
        )

    frames.append(df)


all_runs = pd.concat(frames, ignore_index=True)

print("\n=== GLOBAL VALIDATION ===")

if len(all_runs) != 60:
    fail(f"Expected 60 observations, found {len(all_runs)}")

hashes = all_runs["input_sha256"].dropna().unique()

if len(hashes) != 1:
    fail(
        "Multiple benchmark input SHA-256 hashes found:\n"
        + "\n".join(hashes)
    )

print(f"Valid observations: {len(all_runs)}")
print(f"Unique input SHA-256: {hashes[0]}")
print("FFmpeg exit codes: all 0")

print("\n=== I/O ===")

for column in IO_COLUMNS:
    null_count = all_runs[column].isna().sum()
    print(f"{column}: {null_count} missing values")

print(
    "\nI/O metrics are preserved in all_runs.csv but excluded "
    "from analysis.csv because Debian and Ubuntu did not produce "
    "comparable values."
)

all_runs_path = PROCESSED / "all_runs.csv"
all_runs.to_csv(all_runs_path, index=False)

analysis = all_runs[ANALYSIS_COLUMNS].copy()

analysis_path = PROCESSED / "analysis.csv"
analysis.to_csv(analysis_path, index=False)

records = []

for distribution, group in analysis.groupby("distribution"):
    family = group["family"].iloc[0]

    for metric in MAIN_METRICS + CONTROL_METRICS:
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

summary = (
    analysis.groupby(["family", "distribution"])
    [
        [
            "process_cpu_mean_percent",
            "system_cpu_mean_percent",
            "process_rss_mean_mb",
            "system_memory_used_mean_mb",
        ]
    ]
    .agg(["mean", "std", "min", "max"])
    .round(3)
)

summary_path = PROCESSED / "quick_summary.csv"
summary.to_csv(summary_path)

print("\n=== OUTPUT ===")
print(f"Complete dataset:      {all_runs_path}")
print(f"Analysis dataset:      {analysis_path}")
print(f"Descriptive statistics:{descriptive_path}")
print(f"Quick summary:         {summary_path}")

print("\n=== DISTRIBUTIONS ===")
print(analysis.groupby(["family", "distribution"]).size())

print("\nValidation completed successfully.")
