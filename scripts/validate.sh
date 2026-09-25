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
