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

FAMILY_ORDER = ["debian", "arch", "fedora"]
FAMILY_LABELS = {
    "debian": "Debian",
    "arch": "Arch",
    "fedora": "Fedora",
}

METRICS = {
    "process_cpu_percent": "Uso de CPU do FFmpeg (%)",
    "system_cpu_percent": "Uso de CPU do sistema (%)",
    "process_rss_mb": "Memória RSS do FFmpeg (MB)",
    "system_memory_used_mb": "Memória utilizada pelo sistema (MB)",
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


def descriptive_by_group(
    data: pd.DataFrame,
    group_column: str,
    metric: str,
    order: list[str],
    labels: dict[str, str],
) -> pd.DataFrame:
    """Return descriptive statistics for one metric grouped by a categorical field."""
    records = []

    for group_value in order:
        values = data.loc[data[group_column] == group_value, metric]
        records.append(
            {
                group_column: group_value,
                f"{group_column}_label": labels[group_value],
                "n": values.count(),
                "mean": values.mean(),
                "median": values.median(),
                "std": values.std(ddof=1),
                "cv_percent": coefficient_of_variation(values),
                "min": values.min(),
                "max": values.max(),
            }
        )

    return pd.DataFrame(records)


def save_mean_std_bar(
    stats: pd.DataFrame,
    label_column: str,
    title: str,
    ylabel: str,
    filename: str,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(
        stats[label_column],
        stats["mean"],
        yerr=stats["std"],
        capsize=5,
    )
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Distribuição" if label_column == "distribution_label" else "Família")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / filename, dpi=200)
    plt.close(fig)


if len(df) != 600:
    raise ValueError(f"Esperadas 600 observações, encontradas {len(df)}")

counts = df.groupby("distribution").size().reindex(ORDER)
if not (counts == 100).all():
    raise ValueError(
        "Esperadas 100 observações por distribuição; encontrado:\n"
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

print("\n=== RESUMO DAS 600 OBSERVAÇÕES ===\n")
print(summary.round(2).to_string(index=False))

# -----------------------------------------------------------------------------
# Gráficos da análise principal — todos os textos visíveis em português
# -----------------------------------------------------------------------------
for metric, ylabel in METRICS.items():
    values = [
        df.loc[df["distribution"] == distro, metric]
        for distro in ORDER
    ]

    fig, ax = plt.subplots(figsize=(10, 6))
    boxplot_labels = [LABELS[distro] for distro in ORDER]
    try:
        ax.boxplot(values, tick_labels=boxplot_labels)
    except TypeError:
        # Compatibilidade com Matplotlib 3.7 e 3.8.
        ax.boxplot(values, labels=boxplot_labels)
    ax.set_title(f"{ylabel} por distribuição — 100 amostras por sistema")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Distribuição")
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
    ax.set_title(f"{ylabel} — média ± desvio padrão")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Distribuição")
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
    ax.set_title(f"Distribuição de frequência — {ylabel}")
    ax.set_xlabel(ylabel)
    ax.set_ylabel("Frequência")
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

    ax.set_title(f"Perfil temporal médio — {ylabel}")
    ax.set_xlabel("Amostra dentro da execução")
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(1, 11))
    ax.legend(title="Distribuição")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(
        FIGURES / f"profile_{metric}.png",
        dpi=200,
    )
    plt.close(fig)

# -----------------------------------------------------------------------------
# ANÁLISES FINAIS
# Duas análises com filtro/subconjunto + uma análise com agregação.
# -----------------------------------------------------------------------------

# Filtro comum às análises 1 e 2:
# remove a 10ª amostra de cada execução, pois ela representa a fase de
# encerramento do FFmpeg. O subconjunto resultante contém 540 observações.
active = df[df["sample"] <= 9].copy()

if len(active) != 540:
    raise ValueError(
        f"Esperadas 540 observações no subconjunto ativo, encontradas {len(active)}"
    )

# Análise 1 — filtro/subconjunto: CPU do FFmpeg durante a fase ativa.
active_cpu = descriptive_by_group(
    active,
    group_column="distribution",
    metric="process_cpu_percent",
    order=ORDER,
    labels=LABELS,
)
active_cpu.to_csv(
    PROCESSED / "subset_active_cpu_by_distribution.csv",
    index=False,
)
save_mean_std_bar(
    active_cpu,
    label_column="distribution_label",
    title="Uso de CPU do FFmpeg na fase ativa — amostras 1 a 9",
    ylabel="Uso de CPU do FFmpeg (%)",
    filename="filtered_active_process_cpu_percent.png",
)

# Análise 2 — filtro/subconjunto: memória do sistema durante a fase ativa.
active_memory = descriptive_by_group(
    active,
    group_column="distribution",
    metric="system_memory_used_mb",
    order=ORDER,
    labels=LABELS,
)
active_memory.to_csv(
    PROCESSED / "subset_active_memory_by_distribution.csv",
    index=False,
)
save_mean_std_bar(
    active_memory,
    label_column="distribution_label",
    title="Memória do sistema na fase ativa — amostras 1 a 9",
    ylabel="Memória utilizada pelo sistema (MB)",
    filename="filtered_active_system_memory_used_mb.png",
)

# Análise 3 — agregação: memória do sistema agrupada por família Linux.
family_memory = descriptive_by_group(
    df,
    group_column="family",
    metric="system_memory_used_mb",
    order=FAMILY_ORDER,
    labels=FAMILY_LABELS,
)
family_memory.to_csv(
    PROCESSED / "aggregate_system_memory_by_family.csv",
    index=False,
)
save_mean_std_bar(
    family_memory,
    label_column="family_label",
    title="Memória utilizada pelo sistema por família Linux",
    ylabel="Memória utilizada pelo sistema (MB)",
    filename="aggregate_system_memory_by_family.png",
)

print("\n=== ANÁLISES FINAIS ===\n")
print("Filtro aplicado às análises 1 e 2: sample <= 9")
print(f"Observações no subconjunto ativo: {len(active)}")
print("\n1) CPU do FFmpeg por distribuição — subconjunto ativo")
print(active_cpu.round(2).to_string(index=False))
print("\n2) Memória do sistema por distribuição — subconjunto ativo")
print(active_memory.round(2).to_string(index=False))
print("\n3) Memória do sistema agregada por família Linux")
print(family_memory.round(2).to_string(index=False))

print("\nArquivos adicionais gerados:")
print(f"- {PROCESSED / 'subset_active_cpu_by_distribution.csv'}")
print(f"- {PROCESSED / 'subset_active_memory_by_distribution.csv'}")
print(f"- {PROCESSED / 'aggregate_system_memory_by_family.csv'}")
print(f"- {FIGURES / 'filtered_active_process_cpu_percent.png'}")
print(f"- {FIGURES / 'filtered_active_system_memory_used_mb.png'}")
print(f"- {FIGURES / 'aggregate_system_memory_by_family.png'}")

print()
print(f"Figuras geradas em: {FIGURES}")
print("A análise principal utiliza as 600 amostras medidas.")
