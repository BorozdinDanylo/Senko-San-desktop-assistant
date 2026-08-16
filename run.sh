#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LD_LIBRARY_PATH="$PROJECT_DIR/.venv/lib/python3.14/site-packages/nvidia/cublas/lib:$PROJECT_DIR/.venv/lib/python3.14/site-packages/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$PROJECT_DIR"

exec uv run python -m listener.main