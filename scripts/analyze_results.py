from pathlib import Path

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
