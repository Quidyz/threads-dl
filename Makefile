.PHONY: help install lint format type security complexity test clean check

help:
	@echo "make install / lint / format / type / security / complexity / test / check / clean"

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

type:
	uv run mypy .

security:
	uv run bandit -r .

complexity:
	uv run radon cc -s .
	uv run radon mi -h .

test:
	uv run pytest -v --cov=src

check: lint type security
	@echo "All checks passed"

clean:
	@powershell -Command "Get-ChildItem -Recurse -Include __pycache__,.pytest_cache,.mypy_cache,.ruff_cache | Remove-Item -Recurse -Force"