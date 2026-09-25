# Linux VM Resource Benchmark

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
