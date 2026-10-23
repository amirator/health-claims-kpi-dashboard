.PHONY: all venv test clean
all: ; python run.py
venv: ; python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
test: ; python -m pytest -q
clean: ; rm -f data/claims.duckdb
