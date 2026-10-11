#!/usr/bin/env bash
set -euo pipefail
export DEVKITPRO="${DEVKITPRO:-/opt/devkitpro}"
export PATH="$DEVKITPRO/tools/bin:$DEVKITPRO/devkitA64/bin:$PATH"
cd "$(dirname "$0")/.."
make -j"${JOBS:-4}"
