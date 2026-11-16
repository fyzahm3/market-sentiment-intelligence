.PHONY: setup test lint fmt typecheck check demo leak-suite

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
