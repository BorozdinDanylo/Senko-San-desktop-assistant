#!/usr/bin/env bash

export LD_LIBRARY_PATH="$PWD/.venv/lib/python3.14/site-packages/nvidia/cublas/lib:$PWD/.venv/lib/python3.14/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH"

uv run src/whisper/main.py