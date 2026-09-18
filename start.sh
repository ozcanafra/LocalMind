#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if [ -x ".venv/bin/streamlit" ]; then
  exec .venv/bin/streamlit run app.py
fi

if [ -x "venv/bin/streamlit" ]; then
  exec venv/bin/streamlit run app.py
fi

exec python3 -m streamlit run app.py
