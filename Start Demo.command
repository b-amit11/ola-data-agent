#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ -x .venv/bin/python ]]; then
  demo_python="$PWD/.venv/bin/python"
elif [[ -x ../../work/ola-venv/bin/python ]]; then
  demo_python="$PWD/../../work/ola-venv/bin/python"
else
  echo 'Create the Python environment using README.md, then run this launcher again.'
  read
  exit 1
fi
if curl -fsS http://127.0.0.1:8502/_stcore/health >/dev/null 2>&1; then
  echo 'The demo is running. Open http://127.0.0.1:8502'
  read
  exit 0
fi
echo 'Open http://127.0.0.1:8502. Press Ctrl+C here to stop.'
"$demo_python" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
