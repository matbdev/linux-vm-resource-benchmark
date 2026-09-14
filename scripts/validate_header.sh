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

REFERENCE=""

for distro in "${DISTROS[@]}"; do
    FILE="$RAW/$distro/summary.csv"
    HEADER="$(head -n 1 "$FILE")"

    echo "$distro:"
    echo "$HEADER"
    echo

    if [[ -z "$REFERENCE" ]]; then
        REFERENCE="$HEADER"
    elif [[ "$HEADER" != "$REFERENCE" ]]; then
        echo "ERROR: header mismatch detected in $distro"
        exit 1
    fi
done

echo "All summary.csv files use the same schema."
