from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "results" / "figures"

FIGURES.mkdir(parents=True, exist_ok=True)

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
    "process_cpu_mean_percent": "Mean FFmpeg CPU usage (%)",
    "system_cpu_mean_percent": "Mean system CPU usage (%)",
    "process_rss_mean_mb": "Mean FFmpeg memory usage (MB)",
    "system_memory_used_mean_mb": "Mean system memory usage (MB)",
}


def coefficient_of_variation(series: pd.Series) -> float:
    return series.std(ddof=1) / series.mean() * 100


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
    df.groupby("distribution")
    [
        [
            "process_cpu_mean_percent",
            "system_cpu_mean_percent",
            "process_rss_mean_mb",
            "system_memory_used_mean_mb",
        ]
    ]
    .agg(["mean", "median", "std", "min", "max"])
    .reindex(ORDER)
)

summary.to_csv(PROCESSED / "summary_table.csv")

print("\n=== SUMMARY ===\n")
print(summary.round(2))

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

    ax.set_title(f"{ylabel} by distribution")
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

print()
print(f"Figures generated in: {FIGURES}")
