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
    echo "===== $distro ====="
    cat "$RAW/$distro/summary.csv"
    echo
done
