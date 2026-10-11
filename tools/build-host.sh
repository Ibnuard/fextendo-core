#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build-host
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -Wno-deprecated-declarations -DFXP_TEST \
  -Iinclude -Ithird_party source/core.cpp source/update.cpp source/ui.cpp tests/host.cpp \
  -lcrypto -lcurl -o build-host/driver
python3 -m unittest discover -s tests -p 'test_*.py' -v
