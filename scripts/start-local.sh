#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e '.[dev]'

if [[ ! -f .env ]]; then
  python -m app.cli init
fi

python -m app.cli doctor
printf '\nOpen http://127.0.0.1:8765 after the server starts.\n'
printf 'Paste FCC_ADMIN_TOKEN from .env into the sign-in screen.\n\n'
python -m app.cli serve

