.PHONY: setup test lint fmt typecheck check demo leak-suite report-momentum \
	ledger-record ledger-score ledger-verify

setup:
	uv sync --all-extras

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

check: lint typecheck test

demo:
	uv run sigaudit demo

leak-suite:
	uv run sigaudit leak-suite

report-momentum:
	uv run sigaudit audit --signal momentum --universe universes/us_sector_etfs.txt --start 2000-01-01 --end 2026-10-31 --top-k 3 --permutations 500 --seed 0 --n-trials 1 --out reports

# The same commands the daily Ledger workflow runs (.github/workflows/ledger.yml).
# They need network access and write to records/.
ledger-record:
	uv run sigaudit ledger record --signal momentum --universe universes/us_sector_etfs.txt
	uv run sigaudit ledger record --signal random --universe universes/us_sector_etfs.txt

ledger-score:
	uv run sigaudit ledger score

ledger-verify:
	uv run sigaudit ledger verify
