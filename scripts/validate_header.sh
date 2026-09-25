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
