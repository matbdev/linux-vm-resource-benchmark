#!/usr/bin/env bash

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

for distro in "${DISTROS[@]}"; do
    echo "========== $distro =========="

    echo -n "runs: "
    find "$RAW/$distro/runs" \
        -maxdepth 1 \
        -name 'run_*.csv' \
        -type f | wc -l

    echo -n "warmups: "
    find "$RAW/$distro/warmups" \
        -maxdepth 1 \
        -name 'warmup_*.csv' \
        -type f | wc -l

    echo -n "summary rows: "
    echo $(( $(wc -l < "$RAW/$distro/summary.csv") - 1 ))

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

echo "No empty measurement files found."
