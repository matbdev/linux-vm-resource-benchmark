# Linux VM Resource Benchmark

A controlled statistical experiment comparing resource consumption across six Linux distributions running the same workload under identical virtual machine configurations.

The project was developed as part of a statistical data analysis study focused on collecting reproducible computational resource measurements.

## Objective

The experiment investigates how different Linux distributions behave when executing the same CPU-intensive workload under controlled virtualization conditions.

The evaluated distributions are grouped into three Linux families:

| Family | Distribution |
|---|---|
| Debian-based | Debian |
| Debian-based | Ubuntu |
| Arch-based | Arch Linux |
| Arch-based | EndeavourOS |
| Fedora-based | Fedora |
| Fedora-based | Bazzite |

The goal is not to establish a universal performance ranking between Linux distributions, but to compare their behavior under the specific controlled conditions of this experiment.

## Experimental Environment

Host operating system:

- Pop!_OS

Virtualization stack:

- KVM
- QEMU
- libvirt
- virt-manager

Each virtual machine uses the same virtual hardware configuration:

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

Only one VM was benchmarked at a time in order to minimize resource contention on the host.

## Workload

FFmpeg was selected as the benchmark workload because video encoding creates a reproducible computational task involving:

- CPU usage
- memory usage
- multithreading
- disk activity

All distributions processed the same synthetic video input.

The SHA-256 hash of the benchmark input was:

```text
cb08f335d0e96a41e967f8d19eb99c4db4b4ac9cb6ffaa228641776b6e82dcb3
```

This ensures that every VM processed exactly the same input data.

## Collection Method

Each distribution executed:

```text
2 warm-up runs
10 measured runs
```

The warm-up executions were not included in the statistical sample.

Therefore:

```text
6 distributions × 10 measured runs = 60 valid observations
```

Additionally:

```text
6 distributions × 2 warm-ups = 12 warm-up executions
```

Total executions performed:

```text
72
```

Resource measurements were sampled once per second.

Each measured run produced:

- one detailed time-series CSV;
- one summarized observation in `summary.csv`.

## Collected Metrics

The benchmark collected metrics including:

### CPU

- mean FFmpeg process CPU usage;
- peak FFmpeg process CPU usage;
- mean system CPU usage;
- peak system CPU usage.

### Memory

- mean FFmpeg RSS memory;
- peak FFmpeg RSS memory;
- mean total system memory usage;
- peak total system memory usage.

### Execution

- elapsed time;
- number of samples;
- thread count;
- FFmpeg exit code.

### I/O

Logical and storage I/O metrics were also collected.

However, I/O instrumentation did not produce equivalent data for Debian and Ubuntu. These metrics are therefore preserved in the raw dataset but excluded from the primary comparative analysis.

## Data Validation

The collected dataset was validated before analysis.

The validation confirmed:

- 6 distributions;
- 10 valid executions per distribution;
- 2 warm-up executions per distribution;
- 60 valid observations;
- identical CSV schemas;
- no empty measurement files;
- identical input SHA-256 across every execution;
- FFmpeg exit code `0` for every measured run.

The raw data is preserved without modification under `data/raw/`.

## Repository Structure

```text
.
├── benchmark/
│   ├── benchmark.py
│   └── benchmark_input.sha256
│
├── scripts/
│   ├── prepare_analysis.py
│   ├── analyze_results.py
│   └── validation scripts
│
├── data/
│   ├── raw/
│   └── processed/
│
├── results/
│   └── figures/
│
└── docs/
```

## Reproducibility

The benchmark input can be generated using:

```bash
python3 benchmark.py prepare-input
```

A benchmark execution can then be performed with:

```bash
python3 benchmark.py run \
  --family debian \
  --distribution debian \
  --vm debian
```

The default experiment configuration performs:

```text
2 warm-up runs
10 measured runs
1 sample per second
```

Examples for the other distributions:

```bash
python3 benchmark.py run --family debian --distribution ubuntu --vm ubuntu

python3 benchmark.py run --family arch --distribution arch-linux --vm arch

python3 benchmark.py run --family arch --distribution endeavouros --vm endeavouros

python3 benchmark.py run --family fedora --distribution fedora --vm fedora

python3 benchmark.py run --family fedora --distribution bazzite --vm bazzite
```

## Dataset Preparation

After collecting the results, the datasets can be validated and consolidated with:

```bash
python scripts/prepare_analysis.py
```

This generates:

```text
all_runs.csv
analysis.csv
descriptive_by_distribution.csv
quick_summary.csv
```

`all_runs.csv` preserves all collected metrics.

`analysis.csv` contains only metrics considered directly comparable across all six environments.

## Preliminary Analysis

Initial descriptive analysis indicates that repeated executions were highly stable.

The six distributions showed relatively small differences in CPU utilization, while larger differences were observed in total system memory consumption.

These observations are preliminary and should not be interpreted as universal Linux distribution performance rankings.

Further statistical analysis will be performed separately.

## Methodological Limitation

The ten executions of each distribution are repeated measurements of a single VM installation.

They are not ten independent physical machines or ten independently installed systems.

Therefore, conclusions apply to the experimental environment used in this study and should not be generalized to all systems running these distributions.

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
60 valid benchmark executions
12 warm-up executions
6 Linux distributions
```

Statistical analysis: **in progress**
