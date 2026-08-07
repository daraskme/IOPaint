#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${1:-$(git describe --tags --always --dirty)}"
VERSION="${VERSION#v}"

docker build \
  --file docker/GPUDockerfile \
  --tag "iopaint-ng:${VERSION}-cuda" \
  .

docker build \
  --file docker/CPUDockerfile \
  --tag "iopaint-ng:${VERSION}-cpu" \
  .

echo "Built iopaint-ng:${VERSION}-{cuda,cpu}"
